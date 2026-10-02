from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from bot.config import Settings


def test_settings_parsing():
    env = {
        "TELEGRAM_BOT_TOKEN": "123:ABC",
        "ADMIN_USER_ID": "111",
        "ADMIN_CHAT_ID": "222",
        "GROUP_CHAT_ID": "-100999888",
        "BOT_NAMES": "Ista, Иста, Bot",
        "OPENAI_API_KEY": "sk-mock",
        "POSTGRES_PASSWORD": "secret_pass",
        "NEO4J_PASSWORD": "neo_pass",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        assert settings.telegram_bot_token == "123:ABC"
        assert settings.admin_user_id == 111
        assert settings.admin_chat_id == 222
        assert settings.group_chat_id == -100999888
        assert settings.bot_name_list == ["Ista", "Иста", "Bot"]
        assert "postgresql+asyncpg://" in settings.postgres_dsn
        assert "postgresql+psycopg://" in settings.postgres_dsn_sync


def test_telegram_proxy_defaults_to_direct_connection():
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None)
    assert settings.telegram_proxy_url == ""


def test_telegram_proxy_url_from_env():
    env = {"TELEGRAM_PROXY_URL": "http://user:pass@127.0.0.1:3128"}
    with patch.dict(os.environ, env, clear=True):
        settings = Settings(_env_file=None)
    assert settings.telegram_proxy_url == "http://user:pass@127.0.0.1:3128"


def test_supported_proxy_schemes_pass_validation():
    env = {
        "TELEGRAM_BOT_TOKEN": "123:ABC",
        "OPENAI_API_KEY": "sk-mock",
        "POSTGRES_PASSWORD": "pg",
        "NEO4J_PASSWORD": "neo",
        "TELEGRAM_PROXY_URL": "socks5://127.0.0.1:1080",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = Settings(_env_file=None)
    settings.validate_for_bot_runtime()


def test_unsupported_proxy_scheme_fails_fast():
    env = {
        "TELEGRAM_BOT_TOKEN": "123:ABC",
        "OPENAI_API_KEY": "sk-mock",
        "POSTGRES_PASSWORD": "pg",
        "NEO4J_PASSWORD": "neo",
        "TELEGRAM_PROXY_URL": "https://proxy.example:3128",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = Settings(_env_file=None)
    with pytest.raises(ValueError, match="unsupported scheme"):
        settings.validate_for_bot_runtime()


def test_json_logging_exception_serialization():
    """Verify that exceptions are serialized without TypeError in JSON mode."""
    import structlog

    from bot.log import setup_logging

    setup_logging(debug=False)
    logger = structlog.get_logger("test_json")
    try:
        raise ValueError("test exception for json serialization")
    except ValueError:
        # Must not raise TypeError: Object of type type is not JSON serializable
        logger.exception("An error occurred")
