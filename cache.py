import json
import os
from collections.abc import Awaitable, Callable
from typing import Any

from redis.asyncio import Redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_client: Redis | None = None


async def init_cache_client() -> None:
    """Create the application-wide Redis client.

    A single connection pool is shared across every request so the underlying
    connections are reused instead of being recreated for each call. Must be
    called from within the running event loop (e.g. from the FastAPI lifespan),
    as the client binds to the loop that creates it.
    """
    global _client
    _client = Redis.from_url(REDIS_URL, decode_responses=True)


async def close_cache_client() -> None:
    """Close the global Redis client if one is open."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def get_cache_client() -> Redis:
    """Return the shared Redis client.

    Raises:
        RuntimeError: If the client has not been initialized (lifespan not running).

    Returns:
        The initialized redis.asyncio.Redis instance.
    """
    if _client is None:
        raise RuntimeError("Cache client not initialized. Lifespan not running?")
    return _client


_SENTINEL_NONE = "__strembox_cache_none__"


async def cached_call(
    key: str,
    ttl: int,
    factory: Callable[[], Awaitable[Any]],
    *,
    cache_none: bool = False,
) -> Any:
    """Return the result of *factory*, caching it in Redis for *ttl* seconds.

    On a cache miss *factory* is awaited and its return value is stored as JSON
    under *key* with the given *ttl*. ``None`` results are cached only when
    *cache_none* is true (stored as a sentinel so a genuine ``None`` is
    distinguishable from a missing key). Any value that cannot be JSON-serialized
    is returned as-is without being written to the cache.

    Args:
        key: Cache key to read/write.
        ttl: Time-to-live in seconds for the cached value.
        factory: Coroutine factory producing the value on a miss.
        cache_none: When true, cache ``None`` results too.

    Returns:
        The cached or freshly produced value.
    """
    client = get_cache_client()
    cached = await client.get(key)
    if cached is not None:
        if cached == _SENTINEL_NONE:
            return None
        return json.loads(cached)

    value = await factory()
    if value is None:
        if cache_none:
            await client.set(key, _SENTINEL_NONE, ex=ttl)
        return None

    try:
        serialized = json.dumps(value)
    except (TypeError, ValueError):
        return value
    await client.set(key, serialized, ex=ttl)
    return value
