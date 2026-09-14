"""Add index on chat_members.chat_id and username_history.telegram_user_id.

Revision ID: c8b2d1f0e3a1
Revises: b7a1c9e8d4f2
Create Date: 2026-09-14 10:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8b2d1f0e3a1"
down_revision: str | None = "b7a1c9e8d4f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_chat_members_chat_id", "chat_members", ["chat_id"])
    op.create_index(
        "ix_username_history_telegram_user_id", "username_history", ["telegram_user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_username_history_telegram_user_id", table_name="username_history")
    op.drop_index("ix_chat_members_chat_id", table_name="chat_members")
