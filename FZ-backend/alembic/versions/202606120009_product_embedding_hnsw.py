"""product embedding hnsw index

Revision ID: 202606120009
Revises: 202606120008
Create Date: 2026-06-12 00:09:00

"""
from collections.abc import Sequence

from alembic import op

revision: str = "202606120009"
down_revision: str | None = "202606120008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_merchant_product_embeddings_embedding_hnsw "
        "ON merchant_product_embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_merchant_product_embeddings_embedding_hnsw")
