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

Canned Trakt API payloads live under ``tests/fixtures`` as JSON and are loaded
with the ``load_fixture`` helper.
"""
import json
from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from aioresponses import aioresponses as aioresponses_ctx

from http_client import init_http_session
from schemas.trakt import (
    TraktEpisode,
    TraktFavoriteMovieEntry,
    TraktFavoriteShowEntry,
    TraktHistoryEntry,
    TraktMovieHistoryEntry,
    TraktSeason,
    TraktWatchedShow,
    TraktWatchlistMovie,
    TraktWatchlistShow,
)
from services.trakt import TraktService

TRAKT_API_KEY = "test-trakt-api-key"
TRAKT_ACCESS_TOKEN = "test-trakt-access-token"
TRAKT_BASE_URL = "https://api.trakt.tv"

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    """Load a JSON fixture from ``tests/fixtures``."""
    return json.loads((FIXTURES_DIR / name).read_text())


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


# ---------------------------------------------------------------------------
# get_all_seasons
# ---------------------------------------------------------------------------


async def test_get_all_seasons_returns_parsed_seasons(
    service: TraktService, trakt_api: aioresponses_ctx
) -> None:
    """get_all_seasons should parse the Trakt response into TraktSeason models."""
    payload = load_fixture("bluey_seasons.json")
    # aioresponses normalizes both the registered and request URLs (sorting
    # query params), so the params the service sends must be part of the mock URL.
    url = f"{TRAKT_BASE_URL}/shows/bluey/seasons?extended=episodes"
    trakt_api.get(url, payload=payload)

    seasons = await service.get_all_seasons("bluey")

    assert len(seasons) == 5
    assert [s.number for s in seasons] == [0, 1, 2, 3, 4]
    assert [len(s.episodes) for s in seasons] == [54, 52, 52, 49, 1]
    assert all(isinstance(s, TraktSeason) for s in seasons)
    assert all(isinstance(e, TraktEpisode) for s in seasons for e in s.episodes)

    first = seasons[1]
    assert first.ids.trakt == 173086
    assert first.episodes[0].title == "The Magic Xylophone"
    assert first.episodes[0].ids.trakt == 3178595

    last_season = seasons[-1]
    assert last_season.number == 4
    assert last_season.episodes[0].title == "Episode #4.1"


# ---------------------------------------------------------------------------
# get_all_episodes_season
# ---------------------------------------------------------------------------


async def test_get_all_episodes_season_returns_parsed_episodes(
    service: TraktService, trakt_api: aioresponses_ctx
) -> None:
    """get_all_episodes_season should parse the Trakt response into TraktEpisode models."""
    payload = load_fixture("bluey_episodes.json")
    url = f"{TRAKT_BASE_URL}/shows/bluey/seasons/1"
    trakt_api.get(url, payload=payload)

    episodes = await service.get_all_episodes_season("bluey", 1)

    assert len(episodes) == 52
    assert [e.number for e in episodes] == list(range(1, 53))
    assert all(isinstance(e, TraktEpisode) for e in episodes)
    assert all(e.season == 1 for e in episodes)

    first = episodes[0]
    assert first.title == "The Magic Xylophone"
    assert first.ids.trakt == 3178595
    assert first.ids.imdb == "tt8865002"

    last = episodes[-1]
    assert last.number == 52
    assert last.title == "Verandah Santa"
    assert last.ids.trakt == 3477402


# ---------------------------------------------------------------------------
# get_unwatched_movies
# ---------------------------------------------------------------------------


async def test_get_unwatched_movies_returns_parsed_watchlist(
    service: TraktService, trakt_api: aioresponses_ctx
) -> None:
    """get_unwatched_movies should parse the Trakt watchlist into TraktWatchlistMovie models."""
    payload = load_fixture("movie_watchlist.json")
    url = f"{TRAKT_BASE_URL}/users/me/watchlist/movies/title?hide=unreleased"
    trakt_api.get(url, payload=payload)

    movies = await service.get_unwatched_movies("me")

    assert len(movies) == 2
    assert all(isinstance(m, TraktWatchlistMovie) for m in movies)

    first = movies[0]
    assert first.type == "movie"
    assert first.rank == 2
    assert first.id == 1544201352
    assert first.movie.title == "28 Years Later: The Bone Temple"
    assert first.movie.year == 2026
    assert first.movie.ids.trakt == 1033738


# ---------------------------------------------------------------------------
# get_unwatched_shows
# ---------------------------------------------------------------------------


async def test_get_unwatched_shows_returns_parsed_watchlist(
    service: TraktService, trakt_api: aioresponses_ctx
) -> None:
    """get_unwatched_shows should parse the Trakt watchlist into TraktWatchlistShow models."""
    payload = load_fixture("show_watchlist.json")
    url = f"{TRAKT_BASE_URL}/users/me/watchlist/shows/title?hide=unreleased"
    trakt_api.get(url, payload=payload)

    shows = await service.get_unwatched_shows("me")

    assert len(shows) == 2
    assert all(isinstance(s, TraktWatchlistShow) for s in shows)

    first = shows[0]
    assert first.type == "show"
    assert first.rank == 3
    assert first.show.title == "Little House on the Prairie"
    assert first.show.aired_episodes == 8
    assert first.show.ids.trakt == 275053


# ---------------------------------------------------------------------------
# get_unfinished_shows
# ---------------------------------------------------------------------------


async def test_get_unfinished_shows_filters_partially_watched(
    service: TraktService, trakt_api: aioresponses_ctx
) -> None:
    """get_unfinished_shows should keep only shows with plays below aired_episodes."""
    payload = load_fixture("watched_shows.json")
    url = f"{TRAKT_BASE_URL}/users/me/watched/shows?hidden=false&specials=false"
    trakt_api.get(url, payload=payload)

    shows = await service.get_unfinished_shows("me")

    # 17 watched shows, but only 5 are not fully watched.
    assert len(shows) == 5
    assert all(isinstance(s, TraktWatchedShow) for s in shows)
    assert all(s.plays < s.show.aired_episodes for s in shows)
    assert [s.show.title for s in shows] == [
        "PAW Patrol",
        "Kaamelott",
        "Bluey",
        "Futurama",
        "American Dad!",
    ]

    first = shows[0]
    assert first.plays == 46
    assert first.show.aired_episodes == 570
    assert first.show.ids.trakt == 57161


# ---------------------------------------------------------------------------
# get_favorite_movies
# ---------------------------------------------------------------------------


async def test_get_favorite_movies_returns_parsed_favorites(
    service: TraktService, trakt_api: aioresponses_ctx
) -> None:
    """get_favorite_movies should parse the Trakt favorites into TraktFavoriteMovieEntry models."""
    payload = load_fixture("favorite_movies.json")
    url = f"{TRAKT_BASE_URL}/users/me/favorites/movies/rank"
    trakt_api.get(url, payload=payload)

    favorites = await service.get_favorite_movies("me")

    assert len(favorites) == 5
    assert all(isinstance(f, TraktFavoriteMovieEntry) for f in favorites)

    first = favorites[0]
    assert first.type == "movie"
    assert first.rank == 1
    assert first.id == 1544604587
    assert first.movie.title == "28 Days Later"
    assert first.movie.year == 2002
    assert first.movie.ids.trakt == 135


# ---------------------------------------------------------------------------
# get_favorite_shows
# ---------------------------------------------------------------------------


async def test_get_favorite_shows_returns_parsed_favorites(
    service: TraktService, trakt_api: aioresponses_ctx
) -> None:
    """get_favorite_shows should parse the Trakt favorites into TraktFavoriteShowEntry models."""
    payload = load_fixture("favorite_shows.json")
    url = f"{TRAKT_BASE_URL}/users/me/favorites/shows/rank"
    trakt_api.get(url, payload=payload)

    favorites = await service.get_favorite_shows("me")

    assert len(favorites) == 4
    assert all(isinstance(f, TraktFavoriteShowEntry) for f in favorites)

    first = favorites[0]
    assert first.type == "show"
    assert first.rank == 2
    assert first.id == 1544604605
    assert first.show.title == "The Lord of the Rings: The Rings of Power"
    assert first.show.aired_episodes == 16
    assert first.show.ids.trakt == 150900



