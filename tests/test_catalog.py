"""Tests for ``CatalogService.get_catalog``.

Bauxite and BetaSeries HTTP calls are replayed with ``aioresponses``; the
Redis cache is replaced by an in-memory stub so no real Redis is involved.
"""

import re
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from aioresponses import aioresponses as aioresponses_ctx

from cache import cached_call
from services.betaseries import BetaSeriesService
from services.catalog import CatalogService

BAUXITE_BASE_URL = "http://librebox"
BETASERIES_BASE_URL = "https://api.betaseries.com"

BETASERIES_MOVIE_SEARCH_URL = re.compile(
    rf"{re.escape(BETASERIES_BASE_URL)}/search/movies\?.*"
)
BETASERIES_SHOW_SEARCH_URL = re.compile(
    rf"{re.escape(BETASERIES_BASE_URL)}/search/shows\?.*"
)
BETASERIES_MOVIE_URL = re.compile(
    rf"{re.escape(BETASERIES_BASE_URL)}/movies/movie\?.*"
)
BETASERIES_SHOW_URL = re.compile(
    rf"{re.escape(BETASERIES_BASE_URL)}/shows/display\?.*"
)


class _StubRedis:
    """Minimal in-memory replacement for the Redis client in ``cached_call``."""

    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value


@pytest_asyncio.fixture
async def http_session() -> AsyncGenerator[None]:
    """Initialise the shared aiohttp session for the duration of each test."""
    from http_client import init_http_session, close_http_session

    await init_http_session()
    try:
        yield
    finally:
        await close_http_session()


@pytest_asyncio.fixture
async def stub_redis(monkeypatch, http_session) -> AsyncGenerator[_StubRedis]:
    redis = _StubRedis()
    monkeypatch.setattr("cache.get_cache_client", lambda: redis)
    yield redis


@pytest_asyncio.fixture
async def service(stub_redis) -> CatalogService:
    return CatalogService(
        BAUXITE_BASE_URL,
        "token",
        betaseries_service=BetaSeriesService(api_key="betaseries-key"),
    )


def _bauxite_hashes(names: list[str]) -> dict:
    return {
        f"hash{i}": {"name": name, "percent_done": 1.0, "files": []}
        for i, name in enumerate(names)
    }


def _betaseries_movie(
    bs_id: int,
    title: str,
    year: int | None,
    alias_title: str | None,
    poster: str | None = None,
) -> dict:
    return {
        "id": bs_id,
        "slug": "slug",
        "release_date": year,
        "poster": poster,
        "alias_title": alias_title,
        "title": title,
    }


def _betaseries_show(
    bs_id: int, title: str, year: int | None, poster: str | None = None
) -> dict:
    return {
        "id": bs_id,
        "slug": "slug",
        "release_date": year,
        "poster": poster,
        "alias_title": None,
        "title": title,
    }


@pytest.mark.asyncio
async def test_get_catalog_movies_french_title(service):
    """Movies resolve through BetaSeries; alias_title is the display name."""
    with aioresponses_ctx() as m:
        m.get(
            f"{BAUXITE_BASE_URL}/api/hashes/",
            payload=_bauxite_hashes(
                [
                    "28.Ans.Plus.Tard.Le.Temple.Des.Morts.2026.Multi.VFF.2160p."
                    "Webrip.DV.HDR10Plus.EAC3.5.1.x265-Neostark.mkv",
                ]
            ),
        )
        m.get(
            BETASERIES_MOVIE_SEARCH_URL,
            payload={
                "movies": [
                    _betaseries_movie(
                        140245,
                        "28 Years Later: The Bone Temple",
                        2026,
                        "28 Ans plus tard : Le Temple des morts",
                        poster="https://pictures.betaseries.com/films/affiches/original/140245.jpg",
                    )
                ],
                "total": 1,
            },
        )
        m.get(
            BETASERIES_MOVIE_URL,
            payload={"movie": {"id": 140245, "imdb_id": "tt111111"}},
        )

        response = await service.get_catalog("movie")

    assert len(response.metas) == 1
    assert response.metas[0].id == "tt111111"
    assert response.metas[0].type == "movie"
    # French title preferred for movies.
    assert response.metas[0].name == "28 Ans plus tard : Le Temple des morts"
    assert (
        response.metas[0].poster
        == "https://pictures.betaseries.com/films/affiches/original/140245.jpg"
    )


@pytest.mark.asyncio
async def test_get_catalog_movies_falls_back_to_original_title(service):
    """Without an alias_title the original title is used."""
    with aioresponses_ctx() as m:
        m.get(
            f"{BAUXITE_BASE_URL}/api/hashes/",
            payload=_bauxite_hashes(
                ["Movie.One.2020.FRENCH.1080p.WEB.x264-GROUP"]
            ),
        )
        m.get(
            BETASERIES_MOVIE_SEARCH_URL,
            payload={"movies": [_betaseries_movie(132475, "Movie One", 2020, None)]},
        )
        m.get(
            BETASERIES_MOVIE_URL,
            payload={"movie": {"id": 132475, "imdb_id": "tt333333"}},
        )

        response = await service.get_catalog("movie")

    assert response.metas[0].name == "Movie One"


@pytest.mark.asyncio
async def test_get_catalog_series_and_search(service):
    """Series resolve through the BetaSeries show search."""
    with aioresponses_ctx() as m:
        m.get(
            f"{BAUXITE_BASE_URL}/api/hashes/",
            payload=_bauxite_hashes(
                ["Kaamelott.S05.VOF.1080p.BluRay.x265.DDP.5.1-NOTAG"]
            ),
        )
        m.get(
            BETASERIES_SHOW_SEARCH_URL,
            payload={
                "shows": [
                    _betaseries_show(
                        536,
                        "Kaamelott",
                        None,
                        poster="https://pictures.betaseries.com/fonds/poster/d32448919bd236d3d58ab5d4bd2c1459.jpg",
                    )
                ]
            },
        )
        m.get(
            BETASERIES_SHOW_URL,
            payload={"show": {"id": 536, "imdb_id": "tt222222"}},
        )

        response = await service.get_catalog("series")

    assert len(response.metas) == 1
    assert response.metas[0].id == "tt222222"
    assert response.metas[0].type == "series"
    assert response.metas[0].name == "Kaamelott"
    assert (
        response.metas[0].poster
        == "https://pictures.betaseries.com/fonds/poster/d32448919bd236d3d58ab5d4bd2c1459.jpg"
    )

    # The catalog is always rebuilt from a fresh Bauxite listing, but the
    # title resolutions stay cached, so BetaSeries search is not hit again.
    with aioresponses_ctx() as m:
        m.get(
            f"{BAUXITE_BASE_URL}/api/hashes/",
            payload=_bauxite_hashes(
                ["Kaamelott.S05.VOF.1080p.BluRay.x265.DDP.5.1-NOTAG"]
            ),
        )
        cached = await service.get_catalog("series", search="kaamelott")
    assert cached.metas[0].id == "tt222222"

    # A non-matching search yields an empty catalog without a BetaSeries call.
    with aioresponses_ctx() as m:
        m.get(
            f"{BAUXITE_BASE_URL}/api/hashes/",
            payload=_bauxite_hashes(
                ["Kaamelott.S05.VOF.1080p.BluRay.x265.DDP.5.1-NOTAG"]
            ),
        )
        empty = await service.get_catalog("series", search="inception")
    assert empty.metas == []


@pytest.mark.asyncio
async def test_get_catalog_unresolvable_torrent_skipped(service):
    """A torrent whose title resolves to nothing is not in the catalog."""
    with aioresponses_ctx() as m:
        m.get(
            f"{BAUXITE_BASE_URL}/api/hashes/",
            payload=_bauxite_hashes(["Unknown.thing.2019.FRENCH.1080p.WEB.x264-G"]),
        )
        m.get(BETASERIES_MOVIE_SEARCH_URL, payload={"movies": [], "total": 0})

        response = await service.get_catalog("movie")

    assert response.metas == []


@pytest.mark.asyncio
async def test_get_catalog_search_filters_on_torrent_title(service):
    """The search filter applies to the torrent title, case-insensitive."""
    with aioresponses_ctx() as m:
        m.get(
            f"{BAUXITE_BASE_URL}/api/hashes/",
            payload=_bauxite_hashes(
                ["Movie.One.2020.FRENCH.1080p.WEB.x264-GROUP"]
            ),
        )
        m.get(
            BETASERIES_MOVIE_SEARCH_URL,
            payload={"movies": [_betaseries_movie(132475, "Movie One", 2020, None)]},
        )
        m.get(
            BETASERIES_MOVIE_URL,
            payload={"movie": {"id": 132475, "imdb_id": "tt333333"}},
        )
        matched = await service.get_catalog("movie", search="movie one")

    assert len(matched.metas) == 1
    assert matched.metas[0].id == "tt333333"
