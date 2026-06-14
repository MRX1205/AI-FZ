"""product images

Revision ID: 202606120007
Revises: 202606120006
Create Date: 2026-06-12 00:07:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606120007"
down_revision: str | None = "202606120006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "merchant_product_images",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("merchant_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("public_url", sa.String(length=500), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["merchant_products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "sort_order", name="uq_product_images_sort_order"),
    )
    op.create_index(
        "ix_merchant_product_images_merchant_id",
        "merchant_product_images",
        ["merchant_id"],
    )
    op.create_index(
        "ix_merchant_product_images_product_id",
        "merchant_product_images",
        ["product_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_merchant_product_images_product_id", table_name="merchant_product_images")
    op.drop_index("ix_merchant_product_images_merchant_id", table_name="merchant_product_images")
    op.drop_table("merchant_product_images")
