"""leads notifications

Revision ID: 202606120005
Revises: 202606120004
Create Date: 2026-06-12 00:05:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606120005"
down_revision: str | None = "202606120004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "merchant_leads",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("merchant_id", sa.UUID(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("buyer_email", sa.String(length=320), nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=False),
        sa.Column("product_title", sa.String(length=200), nullable=False),
        sa.Column("product_price_cents", sa.Integer(), nullable=False),
        sa.Column("product_image_url", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_merchant_leads_merchant_id", "merchant_leads", ["merchant_id"])
    op.create_index("ix_merchant_leads_submitted_at", "merchant_leads", ["submitted_at"])

    op.create_table(
        "merchant_notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("merchant_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.String(length=500), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_merchant_notifications_merchant_id",
        "merchant_notifications",
        ["merchant_id"],
    )
    op.create_index("ix_merchant_notifications_sent_at", "merchant_notifications", ["sent_at"])


def downgrade() -> None:
    op.drop_index("ix_merchant_notifications_sent_at", table_name="merchant_notifications")
    op.drop_index("ix_merchant_notifications_merchant_id", table_name="merchant_notifications")
    op.drop_table("merchant_notifications")
    op.drop_index("ix_merchant_leads_submitted_at", table_name="merchant_leads")
    op.drop_index("ix_merchant_leads_merchant_id", table_name="merchant_leads")
    op.drop_table("merchant_leads")
