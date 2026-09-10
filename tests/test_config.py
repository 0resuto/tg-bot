from __future__ import annotations

import os
from unittest.mock import patch

from bot.config import Settings


def test_settings_parsing():
    env = {
        "TELEGRAM_BOT_TOKEN": "123:ABC",
        "ADMIN_USER_ID": "111",
        "ADMIN_CHAT_ID": "222",
        "BOT_NAMES": "Ista, Иста, Bot",
        "OPENAI_API_KEY": "sk-mock",
        "POSTGRES_PASSWORD": "secret_pass",
        "NEO4J_PASSWORD": "neo_pass",
        "SENSITIVE_CATEGORIES": "health, finance, credentials",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        assert settings.telegram_bot_token == "123:ABC"
        assert settings.admin_user_id == 111
        assert settings.admin_chat_id == 222
        assert settings.bot_name_list == ["Ista", "Иста", "Bot"]
        assert settings.sensitive_category_list == ["health", "finance", "credentials"]
        assert "postgresql+asyncpg://" in settings.postgres_dsn
        assert "postgresql+psycopg://" in settings.postgres_dsn_sync
