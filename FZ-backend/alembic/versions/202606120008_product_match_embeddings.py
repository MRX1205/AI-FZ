"""product match embeddings

Revision ID: 202606120008
Revises: 202606120007
Create Date: 2026-06-12 00:08:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202606120008"
down_revision: str | None = "202606120007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "merchant_products",
        sa.Column(
            "match_params",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "merchant_products",
        sa.Column("search_text", sa.Text(), server_default="", nullable=False),
    )
    op.create_table(
        "merchant_product_embeddings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("merchant_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=32), server_default="dashscope", nullable=False),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["merchant_products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_merchant_product_embeddings_merchant_id",
        "merchant_product_embeddings",
        ["merchant_id"],
    )
    op.create_index(
        "ix_merchant_product_embeddings_product_id",
        "merchant_product_embeddings",
        ["product_id"],
        unique=True,
    )
    op.create_index(
        "ix_merchant_product_embeddings_content_hash",
        "merchant_product_embeddings",
        ["content_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_merchant_product_embeddings_content_hash",
        table_name="merchant_product_embeddings",
    )
    op.drop_index(
        "ix_merchant_product_embeddings_product_id",
        table_name="merchant_product_embeddings",
    )
    op.drop_index(
        "ix_merchant_product_embeddings_merchant_id",
        table_name="merchant_product_embeddings",
    )
    op.drop_table("merchant_product_embeddings")
    op.drop_column("merchant_products", "search_text")
    op.drop_column("merchant_products", "match_params")
