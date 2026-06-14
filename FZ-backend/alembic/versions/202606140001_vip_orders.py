"""vip orders

Revision ID: 202606140001
Revises: 202606120011
Create Date: 2026-06-14 12:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606140001"
down_revision: str | None = "202606120011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "merchant_vip_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("merchant_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=32), server_default="alipay", nullable=False),
        sa.Column("pay_channel", sa.String(length=16), nullable=False),
        sa.Column("order_no", sa.String(length=64), nullable=False),
        sa.Column("plan_months", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("trade_status", sa.String(length=32), nullable=True),
        sa.Column("alipay_trade_no", sa.String(length=64), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grant_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grant_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_no"),
    )
    op.create_index("ix_merchant_vip_orders_merchant_id", "merchant_vip_orders", ["merchant_id"])
    op.create_index("ix_merchant_vip_orders_order_no", "merchant_vip_orders", ["order_no"])
    op.create_index(
        "ix_merchant_vip_orders_alipay_trade_no",
        "merchant_vip_orders",
        ["alipay_trade_no"],
    )


def downgrade() -> None:
    op.drop_index("ix_merchant_vip_orders_alipay_trade_no", table_name="merchant_vip_orders")
    op.drop_index("ix_merchant_vip_orders_order_no", table_name="merchant_vip_orders")
    op.drop_index("ix_merchant_vip_orders_merchant_id", table_name="merchant_vip_orders")
    op.drop_table("merchant_vip_orders")
