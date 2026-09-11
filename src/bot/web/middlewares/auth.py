"""Authentication middleware for web dashboard API."""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable

from aiohttp import web

from bot.log import get_logger

logger = get_logger(__name__)

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def create_auth_middleware() -> Callable[
    [web.Request, Callable[[web.Request], Awaitable[web.StreamResponse]]],
    Awaitable[web.StreamResponse],
]:
    """Create an aiohttp middleware enforcing API key authentication on /api/* endpoints."""

    @web.middleware
    async def auth_middleware(
        request: web.Request,
        handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
    ) -> web.StreamResponse:
        path = request.path

        # Only protect /api/* endpoints; static and index files remain publicly accessible
        if not path.startswith("/api/"):
            return await handler(request)

        # Health and checklist endpoints are public for container health probes
        if path in ("/api/health", "/api/checklist"):
            return await handler(request)

        container = request.app.get("container")
        configured_key: str = ""
        if container is not None:
            configured_key = (
                getattr(container.config, "api_key", "")
                or getattr(container.settings, "web_api_key", "")
            ).strip()

        # If an API key is configured, strictly enforce validation
        if configured_key:
            token = _extract_token(request)
            if not token or not hmac.compare_digest(token, configured_key):
                logger.warning(
                    "Unauthorized API access attempt",
                    path=path,
                    remote=request.remote,
                )
                return web.json_response(
                    {"error": "Unauthorized: invalid or missing API key"},
                    status=401,
                )
            return await handler(request)

        # If no key is configured, permit requests only from loopback / localhost
        client_ip = request.remote or ""
        if client_ip in LOOPBACK_HOSTS or client_ip.startswith("127."):
            return await handler(request)

        logger.warning(
            "Blocked non-local API access without configured WEB_API_KEY",
            path=path,
            remote=client_ip,
        )
        return web.json_response(
            {"error": "Forbidden: WEB_API_KEY must be configured for non-localhost access"},
            status=403,
        )

    return auth_middleware


def _extract_token(request: web.Request) -> str | None:
    """Extract authentication token from request headers or query parameters."""
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header:
        return api_key_header.strip()

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.removeprefix("Bearer ").strip()

    query_key = request.query.get("api_key")
    if query_key:
        return query_key.strip()

    return None
