"""initial

Revision ID: 202606120001
Revises:
Create Date: 2026-06-12 00:01:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202606120001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    merchant_tier = postgresql.ENUM("free", "vip", name="merchant_tier", create_type=False)
    merchant_tier.create(bind, checkfirst=True)

    op.create_table(
        "merchants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("tier", merchant_tier, nullable=False),
        sa.Column("vip_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("vip_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_merchants_email", "merchants", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_merchants_email", table_name="merchants")
    op.drop_table("merchants")

    merchant_tier = postgresql.ENUM("free", "vip", name="merchant_tier", create_type=False)
    merchant_tier.drop(op.get_bind(), checkfirst=True)
