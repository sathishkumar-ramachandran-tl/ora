import uuid
from datetime import UTC, datetime

from .extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class RateLimitCounter(db.Model):
    __tablename__ = 'rate_limit_counters'

    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    key_hash = db.Column(db.String(64), nullable=False)
    policy = db.Column(db.String(32), nullable=False)
    window_start = db.Column(db.DateTime, nullable=False)
    count = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        db.UniqueConstraint('key_hash', 'policy', name='uq_rate_limit_key_policy'),
        db.Index('ix_rate_limit_policy_window', 'policy', 'window_start'),
    )
