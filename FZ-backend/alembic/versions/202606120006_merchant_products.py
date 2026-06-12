"""merchant products

Revision ID: 202606120006
Revises: 202606120005
Create Date: 2026-06-12 00:06:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202606120006"
down_revision: str | None = "202606120005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "merchant_products",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("merchant_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.String(length=300), nullable=False),
        sa.Column("detail", sa.String(length=1200), nullable=False),
        sa.Column("tags", postgresql.JSONB(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("image_urls", postgresql.JSONB(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_merchant_products_merchant_id", "merchant_products", ["merchant_id"])


def downgrade() -> None:
    op.drop_index("ix_merchant_products_merchant_id", table_name="merchant_products")
    op.drop_table("merchant_products")
