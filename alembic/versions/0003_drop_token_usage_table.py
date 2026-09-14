"""Drop token_usage table and its indexes.

Revision ID: d9c3e2f1a4b2
Revises: c8b2d1f0e3a1
Create Date: 2026-09-14 10:30:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9c3e2f1a4b2"
down_revision: str | None = "c8b2d1f0e3a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_token_usage_operation_created_at", table_name="token_usage")
    op.drop_index("ix_token_usage_chat_id_created_at", table_name="token_usage")
    op.drop_table("token_usage")


def downgrade() -> None:
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
