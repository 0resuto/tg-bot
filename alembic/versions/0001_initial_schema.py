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
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("added_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
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
        sa.Column("first_seen_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["chat_id"],
            ["chats.chat_id"],
        ),
        sa.UniqueConstraint("telegram_user_id", "chat_id", name="uq_chat_members_user_chat"),
    )

    # username_history table
    op.create_table(
        "username_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("old_username", sa.String(), nullable=True),
        sa.Column("new_username", sa.String(), nullable=True),
        sa.Column("old_first_name", sa.String(), nullable=True),
        sa.Column("new_first_name", sa.String(), nullable=True),
        sa.Column("changed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # token_usage table
    op.create_table(
        "token_usage",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["chat_id"],
            ["chats.chat_id"],
        ),
    )

    op.create_index("ix_token_usage_chat_id_created_at", "token_usage", ["chat_id", "created_at"])
    op.create_index(
        "ix_token_usage_operation_created_at", "token_usage", ["operation", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_token_usage_operation_created_at", table_name="token_usage")
    op.drop_index("ix_token_usage_chat_id_created_at", table_name="token_usage")
    op.drop_table("token_usage")
    op.drop_table("username_history")
    op.drop_table("chat_members")
    op.drop_table("chats")
