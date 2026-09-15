# This file is AI-generated
"""Tests for :class:`services.trakt.TraktService`.

The Trakt API is reached through aiohttp (via ``http_client.get_session``) and
two of the service methods additionally read/write a Redis cache (via
``cache.cached_call``). Both layers are mocked here so no live HTTP or Redis
backing is required:

* ``aioresponses`` intercepts every aiohttp request issued by the shared
  session and replays canned responses.
* ``cached_call`` is patched to short-circuit the cache and invoke the
  factory directly, so the suite never talks to Redis.
* ``TRAKT_API_KEY`` / ``TRAKT_ACCESS_TOKEN`` are injected through the
  ``trakt_env`` fixture so ``TraktService._get_headers`` succeeds.

Only the scaffolding is set up below: fixtures, helpers and ``aioresponses``
context manager wiring. Concrete test functions live in a separate commit.
"""
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from aioresponses import aioresponses as aioresponses_ctx

from http_client import init_http_session
from services.trakt import TraktService

TRAKT_API_KEY = "test-trakt-api-key"
TRAKT_ACCESS_TOKEN = "test-trakt-access-token"
TRAKT_BASE_URL = "https://api.trakt.tv"


@pytest.fixture(autouse=True)
def trakt_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Populate the credentials TraktService reads from the environment."""
    monkeypatch.setenv("TRAKT_API_KEY", TRAKT_API_KEY)
    monkeypatch.setenv("TRAKT_ACCESS_TOKEN", TRAKT_ACCESS_TOKEN)


@pytest.fixture(autouse=True)
def mock_cache() -> AsyncGenerator[None, None]:
    """Bypass Redis: ``cached_call`` runs the factory and returns its value.

    The real ``cached_call`` talks to Redis (``get_cache_client``), which is not
    available in the test environment. Patching it with a thin pass-through lets
    the cached Trakt methods (``get_all_seasons`` / ``get_all_episodes_season``)
    exercise their inner ``fetch`` coroutine against the mocked HTTP layer.
    """

    async def _passthrough_cached_call(key, ttl, factory, *, cache_none=False):
        return await factory()

    with patch(
        "services.trakt.cached_call",
        new=AsyncMock(side_effect=_passthrough_cached_call),
    ):
        yield


@pytest_asyncio.fixture
async def http_session() -> AsyncGenerator[None, None]:
    """Initialise the shared aiohttp session for the duration of each test."""
    await init_http_session()
    try:
        yield
    finally:
        from http_client import close_http_session

        await close_http_session()


@pytest_asyncio.fixture
async def service(http_session: None) -> TraktService:
    """A TraktService wired against the mocked HTTP session and cache."""
    return TraktService()


@pytest.fixture
def trakt_api() -> AsyncGenerator[aioresponses_ctx, None]:
    """Mock the Trakt HTTP API for the duration of a test.

    Use ``trakt_api.get(url, payload=...)`` / ``trakt_api.post(...)`` to register
    canned responses for the endpoints under ``TRAKT_BASE_URL``.
    """
    with aioresponses_ctx() as mocked:
        yield mocked
