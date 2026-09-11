"""Web middlewares package."""

from __future__ import annotations

from bot.web.middlewares.auth import create_auth_middleware

__all__ = ["create_auth_middleware"]
