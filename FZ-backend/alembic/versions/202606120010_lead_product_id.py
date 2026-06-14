"""lead product id

Revision ID: 202606120010
Revises: 202606120009
Create Date: 2026-06-12 00:10:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606120010"
down_revision: str | None = "202606120009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("merchant_leads", sa.Column("product_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_merchant_leads_product_id",
        "merchant_leads",
        "merchant_products",
        ["product_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_merchant_leads_product_id", "merchant_leads", ["product_id"])
    op.create_index(
        "ix_merchant_leads_product_buyer_email",
        "merchant_leads",
        ["product_id", "buyer_email"],
    )


def downgrade() -> None:
    op.drop_index("ix_merchant_leads_product_buyer_email", table_name="merchant_leads")
    op.drop_index("ix_merchant_leads_product_id", table_name="merchant_leads")
    op.drop_constraint("fk_merchant_leads_product_id", "merchant_leads", type_="foreignkey")
    op.drop_column("merchant_leads", "product_id")
