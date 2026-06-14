"""visitor need profiles

Revision ID: 202606120011
Revises: 202606120010
Create Date: 2026-06-12 00:11:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202606120011"
down_revision: str | None = "202606120010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "visitor_need_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("original_question", sa.String(length=1000), nullable=False),
        sa.Column("normalized_question", sa.String(length=1000), nullable=False),
        sa.Column("title", sa.String(length=40), nullable=False),
        sa.Column("summary", sa.String(length=120), nullable=False),
        sa.Column("detail", sa.String(length=800), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_visitor_need_profiles_session_id",
        "visitor_need_profiles",
        ["session_id"],
    )
    op.create_index(
        "ix_visitor_need_profiles_source_type",
        "visitor_need_profiles",
        ["source_type"],
    )
    op.add_column("chat_messages", sa.Column("need_profile_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_chat_messages_need_profile_id",
        "chat_messages",
        "visitor_need_profiles",
        ["need_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_chat_messages_need_profile_id", "chat_messages", ["need_profile_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_messages_need_profile_id", table_name="chat_messages")
    op.drop_constraint("fk_chat_messages_need_profile_id", "chat_messages", type_="foreignkey")
    op.drop_column("chat_messages", "need_profile_id")
    op.drop_index("ix_visitor_need_profiles_source_type", table_name="visitor_need_profiles")
    op.drop_index("ix_visitor_need_profiles_session_id", table_name="visitor_need_profiles")
    op.drop_table("visitor_need_profiles")
