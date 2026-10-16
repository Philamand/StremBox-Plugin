"""Tests for the ``flush_cache`` CLI utility."""

import fnmatch

import pytest

from flush_cache import TARGET_PATTERNS, flush


class FakeRedis:
    """Async stub mimicking ``redis.asyncio.Redis`` scan_iter/delete."""

    def __init__(self, keys):
        self.keys = list(keys)
        self.deleted = []

    def scan_iter(self, match=None, count=None):
        keys = [k for k in self.keys if fnmatch.fnmatch(k, match)]

        async def gen():
            for key in keys:
                yield key

        return gen()

    async def delete(self, *keys):
        for key in keys:
            self.deleted.append(key)
            self.keys.remove(key)
        return len(keys)


@pytest.mark.asyncio
async def test_flush_all_removes_only_strembox_keys():
    redis = FakeRedis(
        [
            "betaseries:resolve:movie:Old:2020",
            "trakt:trending:movies",
            "trakt:seasons:536",
            "c411:search:abc",
            "tr4ker:search:def",
            "unrelated:key",
        ]
    )
    deleted = await flush(redis, TARGET_PATTERNS["all"])
    assert deleted == 5
    assert "unrelated:key" not in redis.deleted


@pytest.mark.asyncio
async def test_flush_target_scoping():
    redis = FakeRedis(
        [
            "betaseries:resolve:movie:Old:2020",
            "trakt:trending:movies",
        ]
    )
    deleted = await flush(redis, TARGET_PATTERNS["betaseries"])
    assert deleted == 1
    assert redis.deleted == ["betaseries:resolve:movie:Old:2020"]


@pytest.mark.asyncio
async def test_flush_empty_cache():
    redis = FakeRedis([])
    assert await flush(redis, TARGET_PATTERNS["all"]) == 0
