"""
Auth flow tests. SES sending is mocked (no live AWS credentials in this environment) —
these tests verify the register/login/verify/reset state machine and DB effects, not
actual email delivery.
"""
from unittest.mock import patch

from app.auth.models import User, EmailVerificationToken, PasswordResetToken


@patch("app.auth.services.send_verification_email", return_value=True)
def test_register_creates_unverified_user_and_issues_token(mock_send, client, db):
    resp = client.post('/api/v1/auth/register', json={
        "email": "new@example.com", "password": "supersecret1", "name": "New User"
    })
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["user"]["email"] == "new@example.com"
    assert body["user"]["email_verified"] is False
    assert body["token"]

    user = User.query.filter_by(email="new@example.com").first()
    assert user is not None
    assert user.password_hash is not None
    assert EmailVerificationToken.query.filter_by(user_id=user.id).count() == 1
    mock_send.assert_called_once()


@patch("app.auth.services.send_verification_email", return_value=True)
def test_register_duplicate_email_rejected(mock_send, client, db):
    client.post('/api/v1/auth/register', json={"email": "dup@example.com", "password": "supersecret1"})
    resp = client.post('/api/v1/auth/register', json={"email": "dup@example.com", "password": "anotherpass1"})
    assert resp.status_code == 409


@patch("app.auth.services.send_verification_email", return_value=True)
def test_login_with_correct_password_succeeds(mock_send, client, db):
    client.post('/api/v1/auth/register', json={"email": "login@example.com", "password": "correcthorse1"})
    resp = client.post('/api/v1/auth/login', json={"email": "login@example.com", "password": "correcthorse1"})
    assert resp.status_code == 200
    assert resp.get_json()["token"]


@patch("app.auth.services.send_verification_email", return_value=True)
def test_login_with_wrong_password_rejected(mock_send, client, db):
    client.post('/api/v1/auth/register', json={"email": "wrongpw@example.com", "password": "correcthorse1"})
    resp = client.post('/api/v1/auth/login', json={"email": "wrongpw@example.com", "password": "wrongpassword"})
    assert resp.status_code == 401


@patch("app.auth.services.send_verification_email", return_value=True)
def test_verify_email_with_correct_code_marks_verified(mock_send, client, db):
    register_resp = client.post('/api/v1/auth/register', json={"email": "verify@example.com", "password": "supersecret1"})
    token = register_resp.get_json()["token"]
    user = User.query.filter_by(email="verify@example.com").first()
    code = EmailVerificationToken.query.filter_by(user_id=user.id).first().code

    resp = client.post('/api/v1/auth/verify-email',
                        json={"code": code},
                        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.get_json()["user"]["email_verified"] is True


@patch("app.auth.services.send_verification_email", return_value=True)
def test_verify_email_with_wrong_code_rejected(mock_send, client, db):
    register_resp = client.post('/api/v1/auth/register', json={"email": "badcode@example.com", "password": "supersecret1"})
    token = register_resp.get_json()["token"]

    resp = client.post('/api/v1/auth/verify-email',
                        json={"code": "000000"},
                        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400


@patch("app.auth.services.send_password_reset_email", return_value=True)
@patch("app.auth.services.send_verification_email", return_value=True)
def test_forgot_password_and_reset_roundtrip(mock_verify_send, mock_reset_send, client, db):
    client.post('/api/v1/auth/register', json={"email": "reset@example.com", "password": "oldpassword1"})

    forgot_resp = client.post('/api/v1/auth/forgot-password', json={"email": "reset@example.com"})
    assert forgot_resp.status_code == 200
    mock_reset_send.assert_called_once()

    user = User.query.filter_by(email="reset@example.com").first()
    reset_token = PasswordResetToken.query.filter_by(user_id=user.id).first().token

    reset_resp = client.post('/api/v1/auth/reset-password', json={"token": reset_token, "password": "newpassword1"})
    assert reset_resp.status_code == 200

    old_login = client.post('/api/v1/auth/login', json={"email": "reset@example.com", "password": "oldpassword1"})
    assert old_login.status_code == 401
    new_login = client.post('/api/v1/auth/login', json={"email": "reset@example.com", "password": "newpassword1"})
    assert new_login.status_code == 200


def test_forgot_password_unknown_email_does_not_leak_existence(client, db):
    resp = client.post('/api/v1/auth/forgot-password', json={"email": "doesnotexist@example.com"})
    assert resp.status_code == 200  # same response whether or not the account exists
