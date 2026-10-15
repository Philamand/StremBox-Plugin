"""Tests for ``CatalogService.get_catalog``/``get_meta``.

Bauxite and Trakt HTTP calls are replayed with ``aioresponses``; the Redis
cache is replaced by an in-memory stub so no real Redis is involved.
"""

import re
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from aioresponses import aioresponses as aioresponses_ctx

from cache import cached_call
from services.catalog import CatalogService
from services.trakt import TraktService

BAUXITE_BASE_URL = "http://librebox"
TRAKT_BASE_URL = "https://api.trakt.tv"

TRAKT_MOVIE_SEARCH_URL = re.compile(rf"{re.escape(TRAKT_BASE_URL)}/search/movie\?.*")
TRAKT_SHOW_SEARCH_URL = re.compile(rf"{re.escape(TRAKT_BASE_URL)}/search/show\?.*")


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
        trakt_service=TraktService(api_key="trakt-key"),
    )


def _bauxite_hashes(names: list[str]) -> dict:
    return {
        f"hash{i}": {"name": name, "percent_done": 1.0, "files": []}
        for i, name in enumerate(names)
    }


def _trakt_search_result(imdb_id: str, title: str, year: int | None) -> dict:
    return {
        "type": "movie",
        "score": 10.0,
        "movie": {"ids": {"imdb": imdb_id}, "title": title, "year": year},
    }


@pytest.mark.asyncio
async def test_get_catalog_movies(service):
    """Torrents are resolved to IMDb ids, deduplicated, non-video skipped."""
    with aioresponses_ctx() as m:
        m.get(
            f"{BAUXITE_BASE_URL}/api/hashes/",
            payload=_bauxite_hashes(
                [
                    "Movie.One.2020.FRENCH.1080p.WEB.x264-GROUP",
                    "Movie.One.2020.VFF.720p.WEB-DL.XviD-OTHER",
                    "Investir - 10 Octobre 2026.pdf",
                ]
            ),
        )
        m.get(
            TRAKT_MOVIE_SEARCH_URL,
            repeat=True,
            payload=[
                _trakt_search_result("tt111111", "Movie One", 2020),
            ],
        )
        response = await service.get_catalog("movie")

    assert len(response.metas) == 1
    assert response.metas[0].id == "tt111111"
    assert response.metas[0].type == "movie"
    assert response.metas[0].name == "Movie One"


@pytest.mark.asyncio
async def test_get_catalog_series_and_search(service):
    """Series torrents resolve against the show search endpoint."""
    with aioresponses_ctx() as m:
        m.get(
            f"{BAUXITE_BASE_URL}/api/hashes/",
            payload=_bauxite_hashes(
                [
                    "Kaamelott.S05.VOF.1080p.BluRay.x265.DDP.5.1-NOTAG",
                ]
            ),
        )
        m.get(
            TRAKT_SHOW_SEARCH_URL,
            repeat=True,
            payload=[
                {
                    "type": "show",
                    "score": 10.0,
                    "show": {"ids": {"imdb": "tt222222"}, "title": "Kaamelott"},
                },
            ],
        )

        response = await service.get_catalog("series")

    assert len(response.metas) == 1
    assert response.metas[0].id == "tt222222"
    assert response.metas[0].type == "series"

    # The catalog is always rebuilt from a fresh Bauxite listing, but the
    # title resolutions stay cached, so the Trakt search endpoint is not
    # hit again.
    with aioresponses_ctx() as m:
        m.get(
            f"{BAUXITE_BASE_URL}/api/hashes/",
            payload=_bauxite_hashes(
                ["Kaamelott.S05.VOF.1080p.BluRay.x265.DDP.5.1-NOTAG"]
            ),
        )
        cached = await service.get_catalog("series", search="kaamelott")
    assert cached.metas[0].id == "tt222222"

    # A non-matching search yields an empty catalog without a Trakt call.
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
        m.get(TRAKT_MOVIE_SEARCH_URL, payload=[], repeat=True)

        response = await service.get_catalog("movie")

    assert response.metas == []


@pytest.mark.asyncio
async def test_get_meta_found(service):
    """``get_meta`` returns the meta of an item present in the catalog."""
    with aioresponses_ctx() as m:
        # The catalog is rebuilt on every call (no catalog cache), so
        # Bauxite is hit twice: once for get_catalog, once inside get_meta.
        m.get(
            f"{BAUXITE_BASE_URL}/api/hashes/",
            repeat=True,
            payload=_bauxite_hashes(["Movie.One.2020.FRENCH.1080p.WEB.x264-GROUP"]),
        )
        m.get(
            TRAKT_MOVIE_SEARCH_URL,
            repeat=True,
            payload=[_trakt_search_result("tt111111", "Movie One", 2020)],
        )
        meta = await service.get_meta("movie", "tt111111")

    assert meta.meta.id == "tt111111"
    assert meta.meta.name == "Movie One"


@pytest.mark.asyncio
async def test_get_meta_not_found(service):
    """``get_meta`` raises for an item that is not in the catalog."""
    with aioresponses_ctx() as m:
        m.get(f"{BAUXITE_BASE_URL}/api/hashes/", payload={})
        m.get(TRAKT_MOVIE_SEARCH_URL, payload=[], repeat=True)

        with pytest.raises(ValueError):
            await service.get_meta("movie", "tt999999")
