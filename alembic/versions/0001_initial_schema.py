"""
Initial schema migration.

Revision ID: b7a1c9e8d4f2
Revises:
Create Date: 2026-09-10 15:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7a1c9e8d4f2"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # chats table
    op.create_table(
        "chats",
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("chat_id"),
    )

    # chat_members table
    op.create_table(
        "chat_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("first_name", sa.String(), nullable=True),
        sa.Column("last_name", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["chat_id"],
            ["chats.chat_id"],
        ),
        sa.UniqueConstraint("telegram_user_id", "chat_id", name="uq_chat_members_user_chat"),
    )
    op.create_index("ix_chat_members_chat_id", "chat_members", ["chat_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_members_chat_id", table_name="chat_members")
    op.drop_table("chat_members")
    op.drop_table("chats")
