# This file is AI-generated
"""Tests for :class:`services.betaseries.BetaSeriesService`.

The BetaSeries API is reached through aiohttp (via ``http_client.get_session``)
and authenticated with a single ``X-BetaSeries-Key`` header derived from the
``BETASERIES_API_KEY`` environment variable. No Redis cache is involved.

* ``aioresponses`` intercepts every aiohttp request issued by the shared
  session and replays canned responses.
* ``BETASERIES_API_KEY`` is injected through the ``betaseries_env`` fixture so
  ``BetaSeriesService`` reads a configured key.
* ``init_http_session`` / ``close_http_session`` manage the shared session.

Canned BetaSeries API payloads live under ``tests/fixtures`` as JSON and are
loaded with the ``load_fixture`` helper.
"""
import json
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from aioresponses import aioresponses as aioresponses_ctx

from http_client import init_http_session
from services.betaseries import BetaSeriesService

BETASERIES_API_KEY = "test-betaseries-api-key"
BETASERIES_BASE_URL = "https://api.betaseries.com"

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    """Load a JSON fixture from ``tests/fixtures``."""
    return json.loads((FIXTURES_DIR / name).read_text())


@pytest.fixture(autouse=True)
def betaseries_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Populate the API key BetaSeriesService reads from the environment."""
    monkeypatch.setenv("BETASERIES_API_KEY", BETASERIES_API_KEY)


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
async def service(http_session: None) -> BetaSeriesService:
    """A BetaSeriesService wired against the mocked HTTP session."""
    return BetaSeriesService()


@pytest.fixture
def betaseries_api() -> AsyncGenerator[aioresponses_ctx, None]:
    """Mock the BetaSeries HTTP API for the duration of a test.

    Use ``betaseries_api.get(url, payload=...)`` to register canned responses
    for the endpoints under ``BETASERIES_BASE_URL``.
    """
    with aioresponses_ctx() as mocked:
        yield mocked


# ---------------------------------------------------------------------------
# get_show_french_title
# ---------------------------------------------------------------------------


async def test_get_show_french_title_returns_title(
    service: BetaSeriesService, betaseries_api: aioresponses_ctx
) -> None:
    """get_show_french_title should return the BetaSeries show title."""
    payload = load_fixture("betaseries_shows_display.json")
    url = f"{BETASERIES_BASE_URL}/shows/display?imdb_id=tt3121722&summary=true"
    betaseries_api.get(url, payload=payload)

    title = await service.get_show_french_title("tt3121722")

    assert title == "Paw Patrol"


async def test_get_show_french_title_returns_none_without_api_key(
    monkeypatch: pytest.MonkeyPatch, http_session: None
) -> None:
    """get_show_french_title should short-circuit to None without an API key."""
    monkeypatch.delenv("BETASERIES_API_KEY")
    service = BetaSeriesService()

    title = await service.get_show_french_title("tt3121722")

    assert title is None


# ---------------------------------------------------------------------------
# get_tmdb_id
# ---------------------------------------------------------------------------


async def test_get_tmdb_id_returns_show_themoviedb_id(
    service: BetaSeriesService, betaseries_api: aioresponses_ctx
) -> None:
    """get_tmdb_id (show) should return the BetaSeries show themoviedb_id."""
    payload = load_fixture("betaseries_shows_display.json")
    url = f"{BETASERIES_BASE_URL}/shows/display?imdb_id=tt3121722&summary=true"
    betaseries_api.get(url, payload=payload)

    tmdb_id = await service.get_tmdb_id("tt3121722")

    assert tmdb_id == 57532


async def test_get_tmdb_id_returns_movie_tmdb_id(
    service: BetaSeriesService, betaseries_api: aioresponses_ctx
) -> None:
    """get_tmdb_id (movie) should return the BetaSeries movie tmdb_id."""
    payload = load_fixture("betaseries_movies_movie.json")
    url = f"{BETASERIES_BASE_URL}/movies/movie?imdb_id=tt11832046&summary=true"
    betaseries_api.get(url, payload=payload)

    tmdb_id = await service.get_tmdb_id("tt11832046", movie=True)

    assert tmdb_id == 675445


async def test_get_tmdb_id_returns_movie_tmdb_id_without_other_title(
    service: BetaSeriesService, betaseries_api: aioresponses_ctx
) -> None:
    """get_tmdb_id (movie) should still return tmdb_id when other_title is None."""
    payload = load_fixture("betaseries_movies_movie_no_other_title.json")
    url = f"{BETASERIES_BASE_URL}/movies/movie?imdb_id=tt9844322&summary=true"
    betaseries_api.get(url, payload=payload)

    tmdb_id = await service.get_tmdb_id("tt9844322", movie=True)

    assert tmdb_id == 577242


async def test_get_tmdb_id_returns_none_without_api_key(
    monkeypatch: pytest.MonkeyPatch, http_session: None
) -> None:
    """get_tmdb_id should short-circuit to None without an API key (both branches)."""
    monkeypatch.delenv("BETASERIES_API_KEY")
    service = BetaSeriesService()

    assert await service.get_tmdb_id("tt3121722") is None
    assert await service.get_tmdb_id("tt11832046", movie=True) is None
