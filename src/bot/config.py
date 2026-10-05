"""Application configuration via pydantic-settings.

All secrets and tunables come from environment variables (or a local .env file).
The Settings class is the single source of truth for configuration — no other
module should read os.environ directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

_SUPPORTED_PROXY_SCHEMES = frozenset({"http", "socks4", "socks5"})


class Settings(BaseSettings):
    """Root settings loaded from environment variables / ``.env`` file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- General -----------------------------------------------------------
    debug: bool = False

    # -- Telegram ----------------------------------------------------------
    telegram_bot_token: str = ""
    telegram_proxy_url: str = Field(
        default="",
        description=(
            "Optional proxy for Telegram API calls, e.g. http://user:pass@host:3128, "
            "socks5://host:1080. Empty means a direct connection."
        ),
    )
    admin_user_id: int = 0
    admin_chat_id: int = 0
    group_chat_id: int = 0

    @field_validator("admin_user_id", "admin_chat_id", "group_chat_id", mode="before")
    @classmethod
    def _parse_id(cls, v: object) -> int:
        if isinstance(v, str):
            clean = v.replace(",", "").replace(" ", "").strip()
            return int(clean) if clean else 0
        if v is None:
            return 0
        if isinstance(v, int):
            return v
        return int(str(v))

    # -- Bot Persona -------------------------------------------------------
    bot_names: str = Field(
        default="Bot",
        description="Comma-separated names the bot responds to (e.g. 'Ista,Иста').",
    )
    bot_persona_system_prompt: str = ""
    bot_persona_prompt_file: str = ""

    # -- OpenAI ------------------------------------------------------------
    openai_api_key: str = ""
    openai_response_model: str = "gpt-4o"
    openai_response_max_tokens: int = 1500
    openai_extraction_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_timeout_seconds: float = 60.0

    # -- PostgreSQL --------------------------------------------------------
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "tgbot"
    postgres_user: str = "tgbot"
    postgres_password: str = ""

    # -- Redis -------------------------------------------------------------
    redis_url: str = "redis://redis:6379/0"

    # -- Neo4j -------------------------------------------------------------
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""

    # -- Memory & Behaviour ------------------------------------------------
    bot_timezone: str = Field(
        default="Europe/Moscow",
        description=(
            "IANA timezone used to render dates in prompts and to interpret "
            "relative time windows (e.g. 'за неделю')."
        ),
    )
    debounce_seconds: float = 10.0
    context_window_minutes: int = 15
    context_min_messages: int = 10
    context_ttl_seconds: int = 86400 * 14  # 14 days
    memory_search_limit_quick: int = 5
    memory_search_limit_deep: int = 15

    # -- Web Dashboard -----------------------------------------------------
    web_host: str = "127.0.0.1"
    web_port: int = 8080
    web_enable_simulator: bool = False

    def to_web_config(self, enable_simulator: bool | None = None) -> WebConfig:
        """Create a WebConfig instance populated from these Settings."""
        return WebConfig(
            host=self.web_host,
            port=self.web_port,
            enable_simulator=self.web_enable_simulator
            if enable_simulator is None
            else enable_simulator,
        )

    # -- Derived helpers ---------------------------------------------------

    @property
    def bot_name_list(self) -> list[str]:
        """Parse comma-separated bot names into a list."""
        return [n.strip() for n in self.bot_names.split(",") if n.strip()]

    @property
    def postgres_dsn(self) -> str:
        """Async DSN for SQLAlchemy (asyncpg driver)."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_dsn_sync(self) -> str:
        """Synchronous DSN for Alembic migrations."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def get_persona_prompt(self) -> str:
        """Return the persona system prompt, preferring the file if configured."""
        if self.bot_persona_prompt_file:
            path = Path(self.bot_persona_prompt_file)
            if path.is_file():
                return path.read_text(encoding="utf-8")
        return self.bot_persona_system_prompt

    def validate_for_bot_runtime(self) -> None:
        """Validate required secrets before starting the Telegram polling bot."""
        try:
            ZoneInfo(self.bot_timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(
                "\n=================================================================\n"
                "[FATAL CONFIGURATION ERROR] Telegram Bot cannot start!\n"
                f"BOT_TIMEZONE is not a valid IANA timezone: {self.bot_timezone!r}\n"
                "Example: BOT_TIMEZONE=Europe/Moscow\n"
                "=================================================================\n"
            ) from None

        proxy = self.telegram_proxy_url.strip()
        if proxy:
            scheme = proxy.split("://", 1)[0].lower()
            if scheme not in _SUPPORTED_PROXY_SCHEMES:
                raise ValueError(
                    "\n=================================================================\n"
                    "[FATAL CONFIGURATION ERROR] Telegram Bot cannot start!\n"
                    f"TELEGRAM_PROXY_URL has an unsupported scheme: {scheme!r}\n"
                    "Supported schemes: http://, socks4://, socks5://\n"
                    "=================================================================\n"
                )

        missing: list[str] = []
        token = self.telegram_bot_token.strip()
        if not token or token.startswith("YOUR_"):
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.openai_api_key or self.openai_api_key.strip().startswith("sk-..."):
            missing.append("OPENAI_API_KEY")
        if not self.postgres_password:
            missing.append("POSTGRES_PASSWORD")
        if not self.neo4j_password:
            missing.append("NEO4J_PASSWORD")

        if missing:
            msg = (
                "\n=================================================================\n"
                "[FATAL CONFIGURATION ERROR] Telegram Bot cannot start!\n"
                "Missing or unconfigured required environment variables:\n"
                + "".join(f"  - {var}\n" for var in missing)
                + "\nTo run the Telegram Bot, configure these in your .env file.\n"
                "For local development without Telegram, run dev.bat (Simulator mode).\n"
                "=================================================================\n"
            )
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class WebConfig:
    """Settings specifically governing the web dashboard server."""

    host: str = "127.0.0.1"
    port: int = 8080
    enable_simulator: bool = False
    static_dir: Path = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    dev_static_dir: Path = Path(__file__).resolve().parent.parent.parent / "frontend"
