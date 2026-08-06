from app.auth.models import User
from app.organizations.models import Organization, OrganizationMember, CustomRole
from app.organizations.permissions import check_permission
from app.organizations import rbac_tools
from app.core.extensions import db


def _seed_org_with_member(member_role="member"):
    owner = User(id="owner1", email="owner@example.com", name="Owner")
    member = User(id="member1", email="member@example.com", name="Member")
    db.session.add_all([owner, member])
    db.session.commit()

    org = Organization(id="org1", name="Acme", owner_id="owner1")
    db.session.add(org)
    db.session.commit()

    db.session.add(OrganizationMember(organization_id="org1", user_id="owner1", role="owner"))
    db.session.add(OrganizationMember(organization_id="org1", user_id="member1", role=member_role))
    db.session.commit()


def test_owner_has_every_permission(client, db):
    _seed_org_with_member()
    assert check_permission("owner1", "org1", "org.manage_billing") is True
    assert check_permission("owner1", "org1", "org.manage_roles") is True


def test_default_member_lacks_manage_roles(client, db):
    _seed_org_with_member()
    assert check_permission("member1", "org1", "org.manage_roles") is False
    assert check_permission("member1", "org1", "task.create") is True  # default member perms


def test_agentic_grant_permission_requires_caller_to_already_have_manage_roles(client, db):
    _seed_org_with_member()
    # member1 doesn't have org.manage_roles — should be rejected, not silently granted
    result = rbac_tools.grant_permission("member1", "org1", "member1", "org.manage_billing")
    assert result["success"] is False
    assert "permission" in result["error"].lower()


def test_agentic_grant_permission_by_authorized_owner_succeeds(client, db):
    _seed_org_with_member()
    result = rbac_tools.grant_permission("owner1", "org1", "member1", "project.view_financials")
    assert result["success"] is True
    assert "project.view_financials" in result["data"]["effective_permissions"]
    assert check_permission("member1", "org1", "project.view_financials") is True


def test_agentic_revoke_permission(client, db):
    _seed_org_with_member()
    rbac_tools.grant_permission("owner1", "org1", "member1", "org.manage_billing")
    assert check_permission("member1", "org1", "org.manage_billing") is True

    result = rbac_tools.revoke_permission("owner1", "org1", "member1", "org.manage_billing")
    assert result["success"] is True
    assert check_permission("member1", "org1", "org.manage_billing") is False


def test_cannot_grant_unknown_permission(client, db):
    _seed_org_with_member()
    result = rbac_tools.grant_permission("owner1", "org1", "member1", "not.a.real.permission")
    assert result["success"] is False


def test_create_role_rejects_unknown_permissions(client, db):
    _seed_org_with_member()
    result = rbac_tools.create_custom_role("owner1", "org1", "Bad Role", ["fake.permission", "task.create"])
    assert result["success"] is False


def test_owner_role_cannot_be_reassigned(client, db):
    _seed_org_with_member()
    role = CustomRole(organization_id="org1", name="Custom", permissions=["task.create"])
    db.session.add(role)
    db.session.commit()

    result = rbac_tools.assign_role_to_member("owner1", "org1", "owner1", role.id)
    assert result["success"] is False


def test_system_roles_seeded_on_org_creation(client, db):
    """The org-create HTTP route (not the direct-model seed helper above) should
    provision default Admin/Member/Viewer roles."""
    owner = User(id="owner2", email="owner2@example.com", name="Owner2")
    db.session.add(owner)
    db.session.commit()

    from flask_jwt_extended import create_access_token
    token = create_access_token(identity="owner2")

    resp = client.post('/api/v2/orgs/', json={"name": "New Co"},
                        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    org_id = resp.get_json()["organization"]["id"]

    roles = CustomRole.query.filter_by(organization_id=org_id).all()
    role_names = {r.name for r in roles}
    assert role_names == {"Admin", "Member", "Viewer"}
    assert all(r.is_system for r in roles)
