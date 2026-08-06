"""Billing module: plan seeding, effective-limit resolution (plan + overrides),
trial lifecycle, promo redemption, and endpoint-level limit enforcement."""
from datetime import datetime, timedelta

from app.core.extensions import db
from app.auth.models import User
from app.billing import service as billing_service
from app.billing.models import Plan, Subscription, PlanOverride, PromoCode


def _make_verified_user(email="billing_user@example.com"):
    from app.core.security import hash_password
    user = User(email=email, name="Billing User", password_hash=hash_password("pw"), email_verified=True)
    db.session.add(user)
    db.session.commit()
    return user


def test_plans_are_seeded_on_app_boot(app, db):
    with app.app_context():
        keys = {p.key for p in Plan.query.all()}
        assert keys == {"free_trial", "student", "freelancer", "startup", "enterprise"}
        trial = Plan.query.filter_by(key="free_trial").first()
        assert trial.limits["workspaces"] == 2  # bumped +1 per explicit instruction


def test_trial_subscription_created_with_expiry(app, db):
    with app.app_context():
        user = _make_verified_user()
        sub = billing_service.create_trial_subscription(user_id=user.id)
        assert sub.status == "trialing"
        assert sub.plan.key == "free_trial"
        assert sub.trial_ends_at > datetime.utcnow()


def test_override_layers_on_top_of_plan_limits(app, db):
    with app.app_context():
        user = _make_verified_user("override_user@example.com")
        sub = billing_service.create_trial_subscription(user_id=user.id)

        base_limits = billing_service.get_effective_limits(sub)
        assert base_limits["ai_calls_per_month"] == 100

        billing_service.grant_override(
            sub.id, {"ai_calls_per_month": None}, reason="beta_partner"
        )
        effective = billing_service.get_effective_limits(sub)
        assert effective["ai_calls_per_month"] is None  # unlimited via override
        assert effective["workspaces"] == 2  # untouched keys still come from the plan


def test_expired_override_does_not_apply(app, db):
    with app.app_context():
        user = _make_verified_user("expired_override@example.com")
        sub = billing_service.create_trial_subscription(user_id=user.id)

        db.session.add(PlanOverride(
            subscription_id=sub.id,
            limit_overrides={"workspaces": 999},
            reason="expired_grant",
            expires_at=datetime.utcnow() - timedelta(days=1),
        ))
        db.session.commit()

        effective = billing_service.get_effective_limits(sub)
        assert effective["workspaces"] == 2  # expired override ignored


def test_extend_trial_pushes_expiry_forward(app, db):
    with app.app_context():
        user = _make_verified_user("extend_trial@example.com")
        sub = billing_service.create_trial_subscription(user_id=user.id)
        original_expiry = sub.trial_ends_at

        updated = billing_service.extend_trial(sub.id, 30)
        assert updated.trial_ends_at > original_expiry


def test_promo_code_extends_trial_and_is_single_use(app, db):
    with app.app_context():
        user = _make_verified_user("promo_user@example.com")
        sub = billing_service.create_trial_subscription(user_id=user.id)
        original_expiry = sub.trial_ends_at

        promo = PromoCode(code="LAUNCH30", trial_extension_days=30, is_active=True)
        db.session.add(promo)
        db.session.commit()

        result = billing_service.redeem_promo_code(sub.id, "LAUNCH30", redeemed_by=user.id)
        assert result["success"] is True

        sub = db.session.get(Subscription, sub.id)
        assert sub.trial_ends_at > original_expiry

        # Second redemption on the same subscription is rejected
        second = billing_service.redeem_promo_code(sub.id, "LAUNCH30", redeemed_by=user.id)
        assert second["success"] is False


def test_promo_code_respects_max_redemptions(app, db):
    with app.app_context():
        user_a = _make_verified_user("promo_a@example.com")
        user_b = _make_verified_user("promo_b@example.com")
        sub_a = billing_service.create_trial_subscription(user_id=user_a.id)
        sub_b = billing_service.create_trial_subscription(user_id=user_b.id)

        promo = PromoCode(code="LIMITED1", trial_extension_days=7, max_redemptions=1, is_active=True)
        db.session.add(promo)
        db.session.commit()

        first = billing_service.redeem_promo_code(sub_a.id, "LIMITED1")
        second = billing_service.redeem_promo_code(sub_b.id, "LIMITED1")
        assert first["success"] is True
        assert second["success"] is False


def test_check_limit_blocks_once_workspace_cap_reached(app, db):
    from app.workspaces.models import Workspace

    with app.app_context():
        user = _make_verified_user("limit_user@example.com")
        sub = billing_service.create_trial_subscription(user_id=user.id)

        for i in range(2):  # free_trial plan allows 2 workspaces
            db.session.add(Workspace(id=f"ws-{i}", name=f"WS {i}", context="personal", owner_id=user.id))
        db.session.commit()

        result = billing_service.check_limit(sub, "workspaces")
        assert result["allowed"] is False
        assert result["limit"] == 2
        assert result["current"] == 2


def test_workspace_creation_endpoint_blocks_over_limit(app, client, db):
    from app.workspaces.models import Workspace
    from flask_jwt_extended import create_access_token

    with app.app_context():
        user = _make_verified_user("endpoint_limit@example.com")
        billing_service.create_trial_subscription(user_id=user.id)
        for i in range(2):
            db.session.add(Workspace(id=f"epws-{i}", name=f"WS {i}", context="personal", owner_id=user.id))
        db.session.commit()
        token = create_access_token(identity=user.id)

    resp = client.post(
        "/api/v1/workspaces",
        json={"workspace": {"name": "One too many", "context": "personal"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 402
    assert resp.get_json()["code"] == "limit_reached"


def test_admin_endpoints_require_platform_admin(app, client, db):
    from flask_jwt_extended import create_access_token

    with app.app_context():
        user = _make_verified_user("not_admin@example.com")
        token = create_access_token(identity=user.id)

    resp = client.get("/api/v2/billing/admin/plans", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_admin_can_update_plan_limits_without_wiping_other_keys(app, client, db):
    from flask_jwt_extended import create_access_token

    with app.app_context():
        admin = _make_verified_user("plan_admin@example.com")
        admin.is_platform_admin = True
        db.session.commit()
        token = create_access_token(identity=admin.id)
        plan = Plan.query.filter_by(key="student").first()
        plan_id = plan.id
        original_tasks_limit = plan.limits["tasks"]

    resp = client.patch(
        f"/api/v2/billing/admin/plans/{plan_id}",
        json={"limits": {"workspaces": 5}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    with app.app_context():
        plan = db.session.get(Plan, plan_id)
        assert plan.limits["workspaces"] == 5
        assert plan.limits["tasks"] == original_tasks_limit  # untouched
