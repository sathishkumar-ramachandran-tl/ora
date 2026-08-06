import logging
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..core.extensions import db
from ..auth.models import User
from ..organizations.models import Organization, OrganizationMember
from . import service
from .models import Plan, Subscription, PlanOverride, PromoCode

logger = logging.getLogger(__name__)
billing_bp = Blueprint('billing', __name__)


def require_platform_admin(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        user = db.session.get(User, user_id)
        if not user or not user.is_platform_admin:
            return jsonify({"error": "Platform admin access required"}), 403
        return fn(*args, **kwargs)
    return wrapper


def _resolve_subscription_for_request(user_id: str, organization_id: str = None) -> Subscription:
    if organization_id:
        member = OrganizationMember.query.filter_by(
            organization_id=organization_id, user_id=user_id
        ).first()
        if not member:
            return None
        sub = service.get_subscription(organization_id=organization_id)
        if not sub:
            sub = service.create_trial_subscription(organization_id=organization_id)
        return sub

    sub = service.get_subscription(user_id=user_id)
    if not sub:
        sub = service.create_trial_subscription(user_id=user_id)
    return sub


# ---------------------------------------------------------------------------
# Self-serve
# ---------------------------------------------------------------------------

@billing_bp.route('/plans', methods=['GET'])
def list_plans():
    plans = Plan.query.filter_by(is_active=True).order_by(Plan.sort_order.asc()).all()
    return jsonify([{
        "id": p.id,
        "key": p.key,
        "name": p.name,
        "description": p.description,
        "scope": p.scope,
        "priceMonthlyUsd": p.price_monthly_usd,
        "priceYearlyUsd": p.price_yearly_usd,
        "includedSeats": p.included_seats,
        "perSeatPriceUsd": p.per_seat_price_usd,
        "limits": p.limits,
    } for p in plans])


@billing_bp.route('/subscription', methods=['GET'])
@jwt_required()
def get_subscription_status():
    user_id = get_jwt_identity()
    organization_id = request.args.get('organization_id') or request.args.get('organizationId')

    sub = _resolve_subscription_for_request(user_id, organization_id)
    if not sub:
        return jsonify({"error": "Not a member of this organization"}), 403

    if service.is_trial_expired(sub) and sub.status == "trialing":
        sub.status = "expired"
        db.session.commit()

    return jsonify({
        "id": sub.id,
        "planKey": sub.plan.key,
        "planName": sub.plan.name,
        "status": sub.status,
        "trialEndsAt": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
        "currentPeriodEnd": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "seats": sub.seats,
        "limits": service.get_effective_limits(sub),
        "usage": service.get_current_usage(sub),
    })


@billing_bp.route('/redeem', methods=['POST'])
@jwt_required()
def redeem_promo():
    user_id = get_jwt_identity()
    data = request.json or {}
    code = (data.get('code') or '').strip()
    organization_id = data.get('organization_id') or data.get('organizationId')
    if not code:
        return jsonify({"error": "code required"}), 400

    sub = _resolve_subscription_for_request(user_id, organization_id)
    if not sub:
        return jsonify({"error": "Not a member of this organization"}), 403

    result = service.redeem_promo_code(sub.id, code, redeemed_by=user_id)
    status = 200 if result["success"] else 400
    return jsonify(result), status


# ---------------------------------------------------------------------------
# Stripe checkout / portal / webhook — functional once STRIPE_SECRET_KEY is set;
# fail gracefully (not a 500) when it isn't, matching the SES pattern in core/email.py.
# ---------------------------------------------------------------------------

def _stripe():
    import stripe
    secret_key = current_app.config.get('STRIPE_SECRET_KEY')
    if not secret_key:
        return None
    stripe.api_key = secret_key
    return stripe


@billing_bp.route('/checkout', methods=['POST'])
@jwt_required()
def create_checkout_session():
    user_id = get_jwt_identity()
    data = request.json or {}
    plan_key = data.get('plan_key') or data.get('planKey')
    billing_cycle = data.get('billing_cycle', 'monthly')  # monthly|yearly
    organization_id = data.get('organization_id') or data.get('organizationId')

    stripe = _stripe()
    if not stripe:
        return jsonify({"error": "Billing is not configured yet — contact support"}), 503

    plan = Plan.query.filter_by(key=plan_key, is_active=True).first()
    if not plan:
        return jsonify({"error": "Unknown plan"}), 404

    price_id = plan.stripe_price_id_yearly if billing_cycle == 'yearly' else plan.stripe_price_id_monthly
    if not price_id:
        return jsonify({"error": "This plan is not available for self-serve checkout — contact sales"}), 400

    sub = _resolve_subscription_for_request(user_id, organization_id)
    if not sub:
        return jsonify({"error": "Not a member of this organization"}), 403

    user = db.session.get(User, user_id)
    frontend_base = current_app.config.get('FRONTEND_BASE_URL', 'http://localhost:3001')

    try:
        session = stripe.checkout.Session.create(
            mode='subscription',
            customer_email=user.email if not sub.stripe_customer_id else None,
            customer=sub.stripe_customer_id or None,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{frontend_base}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{frontend_base}/billing/cancel",
            client_reference_id=sub.id,
            metadata={"subscription_id": sub.id, "plan_key": plan_key},
        )
        return jsonify({"checkoutUrl": session.url})
    except Exception as e:
        logger.error(f"Stripe checkout session creation failed: {e}")
        return jsonify({"error": "Could not start checkout"}), 502


@billing_bp.route('/portal', methods=['POST'])
@jwt_required()
def create_portal_session():
    user_id = get_jwt_identity()
    data = request.json or {}
    organization_id = data.get('organization_id') or data.get('organizationId')

    stripe = _stripe()
    if not stripe:
        return jsonify({"error": "Billing is not configured yet — contact support"}), 503

    sub = _resolve_subscription_for_request(user_id, organization_id)
    if not sub or not sub.stripe_customer_id:
        return jsonify({"error": "No active billing account"}), 404

    frontend_base = current_app.config.get('FRONTEND_BASE_URL', 'http://localhost:3001')
    try:
        session = stripe.billing_portal.Session.create(
            customer=sub.stripe_customer_id,
            return_url=f"{frontend_base}/settings/billing",
        )
        return jsonify({"portalUrl": session.url})
    except Exception as e:
        logger.error(f"Stripe portal session creation failed: {e}")
        return jsonify({"error": "Could not open billing portal"}), 502


@billing_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    stripe = _stripe()
    webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
    if not stripe or not webhook_secret:
        return jsonify({"error": "Billing is not configured"}), 503

    payload = request.data
    sig_header = request.headers.get('Stripe-Signature', '')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except Exception as e:
        logger.warning(f"Stripe webhook signature verification failed: {e}")
        return jsonify({"error": "Invalid signature"}), 400

    obj = event['data']['object']
    event_type = event['type']

    if event_type == 'checkout.session.completed':
        sub_id = (obj.get('metadata') or {}).get('subscription_id') or obj.get('client_reference_id')
        plan_key = (obj.get('metadata') or {}).get('plan_key')
        sub = db.session.get(Subscription, sub_id) if sub_id else None
        if sub:
            sub.stripe_customer_id = obj.get('customer')
            sub.stripe_subscription_id = obj.get('subscription')
            sub.status = 'active'
            if plan_key:
                plan = Plan.query.filter_by(key=plan_key).first()
                if plan:
                    sub.plan_id = plan.id
            db.session.commit()

    elif event_type in ('customer.subscription.updated', 'customer.subscription.deleted'):
        stripe_sub_id = obj.get('id')
        sub = Subscription.query.filter_by(stripe_subscription_id=stripe_sub_id).first()
        if sub:
            if event_type == 'customer.subscription.deleted':
                sub.status = 'canceled'
            else:
                sub.status = obj.get('status', sub.status)
                period_end = obj.get('current_period_end')
                if period_end:
                    sub.current_period_end = datetime.utcfromtimestamp(period_end)
                sub.cancel_at_period_end = bool(obj.get('cancel_at_period_end'))
            db.session.commit()

    return jsonify({"received": True})


# ---------------------------------------------------------------------------
# Platform admin — the "adjustable mechanism" + marketing special-access surface
# ---------------------------------------------------------------------------

@billing_bp.route('/admin/plans', methods=['GET'])
@require_platform_admin
def admin_list_plans():
    plans = Plan.query.order_by(Plan.sort_order.asc()).all()
    return jsonify([{
        "id": p.id, "key": p.key, "name": p.name, "description": p.description,
        "scope": p.scope, "priceMonthlyUsd": p.price_monthly_usd, "priceYearlyUsd": p.price_yearly_usd,
        "includedSeats": p.included_seats, "perSeatPriceUsd": p.per_seat_price_usd,
        "limits": p.limits, "isActive": p.is_active,
    } for p in plans])


@billing_bp.route('/admin/plans/<plan_id>', methods=['PATCH'])
@require_platform_admin
def admin_update_plan(plan_id):
    plan = db.session.get(Plan, plan_id)
    if not plan:
        return jsonify({"error": "Plan not found"}), 404

    data = request.json or {}
    if 'limits' in data:
        # Merge, don't replace wholesale — an admin adjusting one limit shouldn't
        # accidentally wipe the others.
        merged = dict(plan.limits or {})
        merged.update(data['limits'])
        plan.limits = merged
    for field in ('name', 'description', 'price_monthly_usd', 'price_yearly_usd',
                  'included_seats', 'per_seat_price_usd', 'is_active',
                  'stripe_price_id_monthly', 'stripe_price_id_yearly'):
        if field in data:
            setattr(plan, field, data[field])

    db.session.commit()
    logger.info("billing_plan_updated", extra={
        "admin_user_id": get_jwt_identity(), "plan_id": plan.id, "plan_key": plan.key, "changes": data,
    })
    return jsonify({"status": "updated", "limits": plan.limits})


@billing_bp.route('/admin/settings/trial-days', methods=['GET', 'PATCH'])
@require_platform_admin
def admin_trial_days():
    if request.method == 'GET':
        return jsonify({"defaultTrialDays": service.get_default_trial_days()})
    data = request.json or {}
    days = service.set_default_trial_days(data.get('days', 45))
    return jsonify({"defaultTrialDays": days})


@billing_bp.route('/admin/subscriptions/<subscription_id>/extend-trial', methods=['POST'])
@require_platform_admin
def admin_extend_trial(subscription_id):
    data = request.json or {}
    days = int(data.get('days', 14))
    admin_id = get_jwt_identity()
    sub = service.extend_trial(subscription_id, days, granted_by=admin_id)
    logger.info("billing_trial_extended", extra={
        "admin_user_id": admin_id, "subscription_id": subscription_id, "days": days,
    })
    return jsonify({"status": "extended", "trialEndsAt": sub.trial_ends_at.isoformat()})


@billing_bp.route('/admin/subscriptions/<subscription_id>/overrides', methods=['POST'])
@require_platform_admin
def admin_grant_override(subscription_id):
    """The marketing 'special access' lever — grant a partner/press/beta account
    limits that differ from their plan, optionally time-boxed."""
    data = request.json or {}
    limit_overrides = data.get('limits') or {}
    reason = data.get('reason', 'manual_grant')
    expires_in_days = data.get('expires_in_days')
    expires_at = (datetime.utcnow() + timedelta(days=int(expires_in_days))) if expires_in_days else None
    admin_id = get_jwt_identity()

    override = service.grant_override(
        subscription_id, limit_overrides, reason, granted_by=admin_id, expires_at=expires_at
    )
    logger.info("billing_override_granted", extra={
        "admin_user_id": admin_id, "subscription_id": subscription_id,
        "limits": limit_overrides, "reason": reason,
        "expires_at": expires_at.isoformat() if expires_at else None,
    })
    return jsonify({
        "id": override.id, "limits": override.limit_overrides,
        "reason": override.reason, "expiresAt": override.expires_at.isoformat() if override.expires_at else None,
    }), 201


@billing_bp.route('/admin/overrides/<override_id>', methods=['DELETE'])
@require_platform_admin
def admin_revoke_override(override_id):
    service.revoke_override(override_id)
    return jsonify({"status": "revoked"})


@billing_bp.route('/admin/promo-codes', methods=['GET', 'POST'])
@require_platform_admin
def admin_promo_codes():
    if request.method == 'GET':
        codes = PromoCode.query.order_by(PromoCode.created_at.desc()).all()
        return jsonify([{
            "id": c.id, "code": c.code, "description": c.description,
            "grantsPlanKey": c.grants_plan_key, "trialExtensionDays": c.trial_extension_days,
            "maxRedemptions": c.max_redemptions, "redeemedCount": c.redeemed_count,
            "expiresAt": c.expires_at.isoformat() if c.expires_at else None,
            "isActive": c.is_active,
        } for c in codes])

    data = request.json or {}
    code = (data.get('code') or '').strip().upper()
    if not code:
        return jsonify({"error": "code required"}), 400
    if PromoCode.query.filter_by(code=code).first():
        return jsonify({"error": "Code already exists"}), 409

    admin_id = get_jwt_identity()
    expires_in_days = data.get('expires_in_days')
    promo = PromoCode(
        code=code,
        description=data.get('description'),
        grants_plan_key=data.get('grants_plan_key'),
        trial_extension_days=int(data.get('trial_extension_days', 0)),
        stripe_coupon_id=data.get('stripe_coupon_id'),
        max_redemptions=data.get('max_redemptions'),
        expires_at=(datetime.utcnow() + timedelta(days=int(expires_in_days))) if expires_in_days else None,
        created_by=admin_id,
    )
    db.session.add(promo)
    db.session.commit()
    return jsonify({"id": promo.id, "code": promo.code}), 201


@billing_bp.route('/admin/promo-codes/<promo_id>', methods=['DELETE'])
@require_platform_admin
def admin_deactivate_promo(promo_id):
    promo = db.session.get(PromoCode, promo_id)
    if promo:
        promo.is_active = False
        db.session.commit()
    return jsonify({"status": "deactivated"})
