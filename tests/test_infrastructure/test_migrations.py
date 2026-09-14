"""Tests for Alembic migration invocation and configuration."""

from __future__ import annotations

from unittest.mock import patch

from bot.app import run_migrations


def test_run_migrations_invokes_upgrade():
    """Verify that run_migrations loads alembic config and upgrades to head."""
    with patch("alembic.command.upgrade") as mock_upgrade:
        run_migrations()
        mock_upgrade.assert_called_once()
        args, _ = mock_upgrade.call_args
        assert args[1] == "head"
        assert args[0].config_file_name == "alembic.ini"
