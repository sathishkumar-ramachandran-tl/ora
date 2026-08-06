import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import CheckConstraint
from ..core.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class Plan(db.Model):
    """A billing tier. Limits live in JSONB (not hardcoded columns) so platform
    admins can tune them from the admin API without a migration/deploy — the
    'adjustable mechanism' requirement. Seeded with 5 rows: free_trial, student,
    freelancer, startup, enterprise."""
    __tablename__ = 'plans'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    key = db.Column(db.String, unique=True, nullable=False)  # free_trial|student|freelancer|startup|enterprise
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.Text)
    scope = db.Column(db.String, nullable=False, default='personal')  # personal|company

    price_monthly_usd = db.Column(db.Float, default=0.0)
    price_yearly_usd = db.Column(db.Float, default=0.0)
    included_seats = db.Column(db.Integer, default=1)  # company plans: seats before per-seat billing kicks in
    per_seat_price_usd = db.Column(db.Float, default=0.0)

    stripe_product_id = db.Column(db.String, nullable=True)
    stripe_price_id_monthly = db.Column(db.String, nullable=True)
    stripe_price_id_yearly = db.Column(db.String, nullable=True)

    # {workspaces, projects, tasks, ai_calls_per_month, module_generations_per_month,
    #  storage_mb, team_members, custom_roles} — a null value for a key means unlimited.
    limits = db.Column(JSONB, default=dict)

    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Subscription(db.Model):
    """One billing relationship — either a personal user (Free Trial/Student/Freelancer)
    or an organization (Startup/Enterprise). Exactly one of user_id/organization_id is set."""
    __tablename__ = 'subscriptions'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    organization_id = db.Column(db.String, db.ForeignKey('organizations.id'), nullable=True)
    plan_id = db.Column(db.String, db.ForeignKey('plans.id'), nullable=False)

    status = db.Column(db.String, default='trialing')  # trialing|active|past_due|canceled|expired
    trial_ends_at = db.Column(db.DateTime, nullable=True)
    current_period_end = db.Column(db.DateTime, nullable=True)
    seats = db.Column(db.Integer, default=1)
    cancel_at_period_end = db.Column(db.Boolean, default=False)

    stripe_customer_id = db.Column(db.String, nullable=True)
    stripe_subscription_id = db.Column(db.String, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    plan = db.relationship('Plan')

    __table_args__ = (
        CheckConstraint(
            '(user_id IS NOT NULL AND organization_id IS NULL) OR '
            '(user_id IS NULL AND organization_id IS NOT NULL)',
            name='ck_subscription_single_owner'
        ),
    )


class PlanOverride(db.Model):
    """Marketing/special-access grant layered over a subscription's plan limits —
    e.g. 'unlimited AI calls for 90 days' for a beta partner, or a comped upgrade.
    Overrides are additive/partial: only the keys present here replace the plan's
    defaults, everything else still comes from Plan.limits."""
    __tablename__ = 'plan_overrides'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    subscription_id = db.Column(db.String, db.ForeignKey('subscriptions.id'), nullable=False)
    limit_overrides = db.Column(JSONB, default=dict)
    reason = db.Column(db.String)  # 'beta_partner' | 'press' | 'promo_code:XYZ' | 'support_comp' | free text
    granted_by = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)  # null = permanent until revoked
    revoked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PromoCode(db.Model):
    """Self-serve marketing codes — extend a trial, grant a plan upgrade, or apply
    a Stripe coupon at checkout. Distinct from PlanOverride, which is a manual
    admin grant; a PromoCode is something a user redeems themselves."""
    __tablename__ = 'promo_codes'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    code = db.Column(db.String, unique=True, nullable=False)
    description = db.Column(db.String)
    grants_plan_key = db.Column(db.String, nullable=True)  # switch subscription to this plan
    trial_extension_days = db.Column(db.Integer, default=0)
    stripe_coupon_id = db.Column(db.String, nullable=True)
    max_redemptions = db.Column(db.Integer, nullable=True)  # null = unlimited
    redeemed_count = db.Column(db.Integer, default=0)
    expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PromoRedemption(db.Model):
    __tablename__ = 'promo_redemptions'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    promo_code_id = db.Column(db.String, db.ForeignKey('promo_codes.id'), nullable=False)
    subscription_id = db.Column(db.String, db.ForeignKey('subscriptions.id'), nullable=False)
    redeemed_by = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    redeemed_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('promo_code_id', 'subscription_id', name='uq_promo_redemption_once_per_subscription'),
    )


class PlatformSetting(db.Model):
    """Generic key/value store for platform-wide, admin-tunable knobs — starting
    with default_trial_days, but a natural home for future billing/ops toggles
    without a schema change each time."""
    __tablename__ = 'platform_settings'
    key = db.Column(db.String, primary_key=True)
    value = db.Column(JSONB, default=dict)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
