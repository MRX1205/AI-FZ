"""auth

Revision ID: 202606120003
Revises: 202606120002
Create Date: 2026-06-12 00:03:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606120003"
down_revision: str | None = "202606120002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_codes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_codes_email", "auth_codes", ["email"])

    op.create_table(
        "merchant_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("merchant_id", sa.UUID(), nullable=False),
        sa.Column("token", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_merchant_sessions_merchant_id", "merchant_sessions", ["merchant_id"])
    op.create_index("ix_merchant_sessions_token", "merchant_sessions", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_merchant_sessions_token", table_name="merchant_sessions")
    op.drop_index("ix_merchant_sessions_merchant_id", table_name="merchant_sessions")
    op.drop_table("merchant_sessions")
    op.drop_index("ix_auth_codes_email", table_name="auth_codes")
    op.drop_table("auth_codes")
