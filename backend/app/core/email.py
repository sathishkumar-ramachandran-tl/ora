"""
All transactional email — Amazon SES only.

Replaces the previous Gmail-API-based sending (personal Gmail credentials, OAuth
installed-app flow, token.json on disk — fragile for a containerized deploy and not
something a team can share credentials for cleanly). SES uses standard AWS credentials
(env vars, IAM role) via boto3's default credential chain — nothing app-specific to
provision per developer.

Usage patterns are intentionally narrow now that OTP is scoped to new-user verification
and password reset (see app/auth) rather than every login:
    send_verification_email(email, otp)
    send_password_reset_email(email, reset_link)
    send_welcome_email(email, name)
"""
import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import current_app

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("ses", region_name=current_app.config["AWS_REGION"])
    return _client


def send_email(recipient: str, subject: str, body_text: str, body_html: str | None = None) -> bool:
    sender = current_app.config["SES_SENDER_EMAIL"]
    body = {"Text": {"Data": body_text, "Charset": "UTF-8"}}
    if body_html:
        body["Html"] = {"Data": body_html, "Charset": "UTF-8"}

    try:
        _get_client().send_email(
            Source=sender,
            Destination={"ToAddresses": [recipient]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": body,
            },
        )
        return True
    except (ClientError, BotoCoreError) as e:
        # ClientError = SES rejected the request (bad params, throttling, unverified sender...);
        # BotoCoreError = client-side failure before the request even went out (e.g. missing
        # AWS credentials). Either way, a broken mail provider should degrade the calling flow
        # (register/reset still succeeds, user can resend later) — never crash the request.
        logger.error("SES send_email failed", extra={"recipient": recipient, "error": str(e)})
        return False


def send_verification_email(recipient: str, otp: str) -> bool:
    return send_email(
        recipient,
        subject="Verify your Ora account",
        body_text=f"Your verification code is {otp}. It expires in 10 minutes.",
        body_html=f"<p>Your verification code is <strong>{otp}</strong>. It expires in 10 minutes.</p>",
    )


def send_password_reset_email(recipient: str, reset_link: str) -> bool:
    return send_email(
        recipient,
        subject="Reset your Ora password",
        body_text=f"Reset your password: {reset_link}\nThis link expires in 30 minutes. "
                  f"If you didn't request this, you can safely ignore this email.",
        body_html=f'<p><a href="{reset_link}">Reset your password</a> (expires in 30 minutes).</p>'
                  f"<p>If you didn't request this, you can safely ignore this email.</p>",
    )


def send_welcome_email(recipient: str, name: str) -> bool:
    display_name = name or "there"
    return send_email(
        recipient,
        subject="Welcome to Ora",
        body_text=f"Hi {display_name}, welcome to Ora — your AI-native operating system "
                  f"for high-velocity work. Let's get started.",
        body_html=f"<p>Hi {display_name},</p><p>Welcome to Ora — your AI-native operating "
                  f"system for high-velocity work. Let's get started.</p>",
    )
