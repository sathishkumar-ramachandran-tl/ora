"""Billing/limits service layer — effective-limit resolution, usage counting,
trial lifecycle, and special-access grants (overrides + promo codes)."""
from datetime import datetime, timedelta

from ..core.extensions import db
from .models import Plan, Subscription, PlanOverride, PromoCode, PromoRedemption, PlatformSetting
from .plan_defaults import PLAN_DEFAULTS, DEFAULT_TRIAL_DAYS


def seed_plans():
    """Idempotent — inserts any PLAN_DEFAULTS rows missing from the plans table.
    Never overwrites an existing plan's limits, since admins may have tuned them."""
    existing_keys = {p.key for p in Plan.query.all()}
    for defaults in PLAN_DEFAULTS:
        if defaults["key"] in existing_keys:
            continue
        db.session.add(Plan(**defaults))
    db.session.commit()


def get_default_trial_days() -> int:
    setting = db.session.get(PlatformSetting, "default_trial_days")
    if setting and isinstance(setting.value, dict) and "days" in setting.value:
        return int(setting.value["days"])
    return DEFAULT_TRIAL_DAYS


def set_default_trial_days(days: int):
    days = max(1, min(int(days), 365))
    setting = db.session.get(PlatformSetting, "default_trial_days")
    if setting:
        setting.value = {"days": days}
    else:
        setting = PlatformSetting(key="default_trial_days", value={"days": days})
        db.session.add(setting)
    db.session.commit()
    return days


def _trial_plan() -> Plan:
    plan = Plan.query.filter_by(key="free_trial").first()
    if not plan:
        raise RuntimeError("free_trial plan is not seeded — call seed_plans() at startup")
    return plan


def create_trial_subscription(user_id: str = None, organization_id: str = None) -> Subscription:
    """Every new personal user or organization starts on a trial subscription —
    called from auth registration / organization creation."""
    if bool(user_id) == bool(organization_id):
        raise ValueError("exactly one of user_id or organization_id is required")

    plan = _trial_plan()
    sub = Subscription(
        user_id=user_id,
        organization_id=organization_id,
        plan_id=plan.id,
        status="trialing",
        trial_ends_at=datetime.utcnow() + timedelta(days=get_default_trial_days()),
        seats=1,
    )
    db.session.add(sub)
    db.session.commit()
    return sub


def get_subscription(user_id: str = None, organization_id: str = None) -> Subscription:
    q = Subscription.query
    if organization_id:
        return q.filter_by(organization_id=organization_id).first()
    return q.filter_by(user_id=user_id).first()


def _active_overrides(subscription_id: str):
    now = datetime.utcnow()
    overrides = PlanOverride.query.filter_by(subscription_id=subscription_id, revoked_at=None).all()
    return [o for o in overrides if o.expires_at is None or o.expires_at > now]


def get_effective_limits(subscription: Subscription) -> dict:
    """Plan defaults with any active PlanOverride keys layered on top. A limit
    value of None means unlimited for that resource."""
    limits = dict(subscription.plan.limits or {})
    for override in _active_overrides(subscription.id):
        for key, value in (override.limit_overrides or {}).items():
            limits[key] = value
    return limits


def is_trial_expired(subscription: Subscription) -> bool:
    if subscription.status != "trialing":
        return False
    return bool(subscription.trial_ends_at and subscription.trial_ends_at < datetime.utcnow())


def extend_trial(subscription_id: str, days: int, granted_by: str = None) -> Subscription:
    sub = db.session.get(Subscription, subscription_id)
    if not sub:
        raise ValueError("subscription not found")
    base = sub.trial_ends_at if sub.trial_ends_at and sub.trial_ends_at > datetime.utcnow() else datetime.utcnow()
    sub.trial_ends_at = base + timedelta(days=int(days))
    if sub.status == "expired":
        sub.status = "trialing"
    db.session.commit()
    return sub


def grant_override(subscription_id: str, limit_overrides: dict, reason: str,
                    granted_by: str = None, expires_at: datetime = None) -> PlanOverride:
    override = PlanOverride(
        subscription_id=subscription_id,
        limit_overrides=limit_overrides,
        reason=reason,
        granted_by=granted_by,
        expires_at=expires_at,
    )
    db.session.add(override)
    db.session.commit()
    return override


def revoke_override(override_id: str):
    override = db.session.get(PlanOverride, override_id)
    if override:
        override.revoked_at = datetime.utcnow()
        db.session.commit()
    return override


def redeem_promo_code(subscription_id: str, code: str, redeemed_by: str = None) -> dict:
    promo = PromoCode.query.filter_by(code=code, is_active=True).first()
    if not promo:
        return {"success": False, "error": "Invalid or inactive promo code"}
    if promo.expires_at and promo.expires_at < datetime.utcnow():
        return {"success": False, "error": "Promo code has expired"}
    if promo.max_redemptions is not None and promo.redeemed_count >= promo.max_redemptions:
        return {"success": False, "error": "Promo code has reached its redemption limit"}
    already = PromoRedemption.query.filter_by(
        promo_code_id=promo.id, subscription_id=subscription_id
    ).first()
    if already:
        return {"success": False, "error": "Promo code already redeemed on this subscription"}

    sub = db.session.get(Subscription, subscription_id)
    if not sub:
        return {"success": False, "error": "Subscription not found"}

    if promo.trial_extension_days:
        extend_trial(subscription_id, promo.trial_extension_days)

    if promo.grants_plan_key:
        plan = Plan.query.filter_by(key=promo.grants_plan_key).first()
        if plan:
            sub.plan_id = plan.id
            db.session.commit()

    db.session.add(PromoRedemption(
        promo_code_id=promo.id, subscription_id=subscription_id, redeemed_by=redeemed_by
    ))
    promo.redeemed_count = (promo.redeemed_count or 0) + 1
    db.session.commit()
    return {"success": True, "error": None}


# ---------------------------------------------------------------------------
# Usage counting — reads current consumption for the resources referenced in
# Plan.limits. Kept separate from the limits dict itself so new resources can
# be added without touching the Plan schema.
# ---------------------------------------------------------------------------

def get_current_usage(subscription: Subscription) -> dict:
    from ..workspaces.models import Workspace
    from ..projects.models import Project
    from ..tasks.models import Task
    from ..organizations.models import OrganizationMember, CustomRole
    from ..agents.models import LlmCall

    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if subscription.organization_id:
        workspace_ids = [w.id for w in Workspace.query.filter_by(
            organization_id=subscription.organization_id
        ).all()]
        team_members = OrganizationMember.query.filter_by(
            organization_id=subscription.organization_id
        ).count()
        custom_roles = CustomRole.query.filter_by(
            organization_id=subscription.organization_id, is_system=False
        ).count()
    else:
        workspace_ids = [w.id for w in Workspace.query.filter_by(
            owner_id=subscription.user_id
        ).all()]
        team_members = None
        custom_roles = None

    projects = Project.query.filter(Project.workspace_id.in_(workspace_ids)).count() if workspace_ids else 0
    tasks = Task.query.filter(Task.workspace_id.in_(workspace_ids)).count() if workspace_ids else 0
    ai_calls = LlmCall.query.filter(
        LlmCall.workspace_id.in_(workspace_ids), LlmCall.created_at >= month_start
    ).count() if workspace_ids else 0

    return {
        "workspaces": len(workspace_ids),
        "projects": projects,
        "tasks": tasks,
        "ai_calls_per_month": ai_calls,
        "team_members": team_members,
        "custom_roles": custom_roles,
    }


def check_limit(subscription: Subscription, resource: str, increment: int = 1) -> dict:
    """Returns {'allowed': bool, 'limit': int|None, 'current': int, 'resource': str}.
    A None limit means unlimited (always allowed)."""
    limits = get_effective_limits(subscription)
    limit = limits.get(resource)
    if limit is None:
        return {"allowed": True, "limit": None, "current": None, "resource": resource}

    usage = get_current_usage(subscription)
    current = usage.get(resource, 0) or 0
    allowed = (current + increment) <= limit
    return {"allowed": allowed, "limit": limit, "current": current, "resource": resource}
