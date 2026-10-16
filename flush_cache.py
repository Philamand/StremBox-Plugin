"""Flush StremBox cache entries from Redis.

Usage (from the repository root, with the same environment as the app):

    uv run --env-file .uv.env python flush_cache.py [target ...]

Targets:

    all           Every StremBox cache entry (default).
    betaseries    Title-to-IMDb resolutions (betaseries:resolve:*)
    trakt         Trakt trending/seasons/episodes entries (trakt:*)
    c411          C411 tracker search results (c411:search:*)
    tr4ker        Tr4ker tracker search results (tr4ker:search:*)

Only keys created by StremBox are flushed; anything else in the Redis
database is left untouched. The Redis URL is read from REDIS_URL, the
same environment variable the app uses.
"""

import argparse
import asyncio
import os
import sys

from redis.asyncio import Redis

# Cache key prefixes used across the codebase. Keep in sync with the
# cached_call() keys in services/*.
TARGET_PATTERNS: dict[str, tuple[str, ...]] = {
    "all": ("c411:search:*", "tr4ker:search:*", "trakt:*", "betaseries:resolve:*"),
    "betaseries": ("betaseries:resolve:*",),
    "trakt": ("trakt:*",),
    "c411": ("c411:search:*",),
    "tr4ker": ("tr4ker:search:*",),
}


async def flush(redis: Redis, patterns: tuple[str, ...]) -> int:
    """Delete every key matching one of *patterns*; return the count."""
    deleted = 0
    for pattern in patterns:
        async for key in redis.scan_iter(match=pattern, count=500):
            await redis.delete(key)
            deleted += 1
    return deleted


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Flush StremBox cache entries from Redis.",
        epilog="Targets: " + ", ".join(sorted(TARGET_PATTERNS)),
    )
    parser.add_argument(
        "targets",
        nargs="*",
        default=["all"],
        choices=sorted(TARGET_PATTERNS),
        help="Which cache entries to flush (default: all).",
    )
    args = parser.parse_args()

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis = Redis.from_url(redis_url, decode_responses=True)
    try:
        patterns = tuple(
            pattern
            for target in args.targets
            for pattern in TARGET_PATTERNS[target]
        )
        deleted = await flush(redis, patterns)
        print(f"Flushed {deleted} cache entr{'y' if deleted == 1 else 'ies'}.")
    finally:
        await redis.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:  # noqa: BLE001 - CLI boundary
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
