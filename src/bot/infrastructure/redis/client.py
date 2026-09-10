"""Redis client setup."""

from __future__ import annotations

import redis.asyncio as redis


def create_redis_client(url: str) -> redis.Redis:
    """Create and return an async Redis client."""
    return redis.from_url(url, decode_responses=True)
