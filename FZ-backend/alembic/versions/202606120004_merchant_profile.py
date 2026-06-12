"""merchant profile

Revision ID: 202606120004
Revises: 202606120003
Create Date: 2026-06-12 00:04:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606120004"
down_revision: str | None = "202606120003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "merchants",
        sa.Column("web_notification_enabled", sa.Boolean(), server_default="true", nullable=False),
    )
    op.add_column(
        "merchants",
        sa.Column(
            "email_notification_enabled",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("merchants", "email_notification_enabled")
    op.drop_column("merchants", "web_notification_enabled")
