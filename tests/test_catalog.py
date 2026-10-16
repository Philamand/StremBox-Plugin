"""Tests for ``CatalogService`` (Trakt trending catalogs).

Trakt HTTP calls are replayed with ``aioresponses``; the Redis cache is
replaced by an in-memory stub so no real Redis is involved.
"""

import re
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from aioresponses import aioresponses as aioresponses_ctx

from services.catalog import CatalogService
from services.trakt import TraktService

TRAKT_TRENDING_MOVIES_URL = re.compile(
    r"https://api\.trakt\.tv/movies/trending\?.*"
)
TRAKT_TRENDING_SHOWS_URL = re.compile(
    r"https://api\.trakt\.tv/shows/trending\?.*"
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
    return CatalogService(trakt_service=TraktService(api_key="trakt-key"))


def _trending_movie_payload(imdb_id: str, title: str, poster: str | None) -> dict:
    movie = {"ids": {"imdb": imdb_id}, "title": title, "year": 2026}
    if poster:
        movie["images"] = {"poster": [poster]}
    return {"watchers": 1686, "movie": movie}


def _trending_show_payload(imdb_id: str, title: str, poster: str | None) -> dict:
    show = {"ids": {"imdb": imdb_id}, "title": title, "year": 1997}
    if poster:
        show["images"] = {"poster": [poster]}
    return {"watchers": 6836, "show": show}


@pytest.mark.asyncio
async def test_get_catalog_trending_movies(service):
    """Trending movies serve English titles with scheme-normalised posters."""
    with aioresponses_ctx() as m:
        m.get(
            TRAKT_TRENDING_MOVIES_URL,
            payload=[
                _trending_movie_payload(
                    "tt22084616",
                    "Spider-Man: Brand New Day",
                    "media.trakt.tv/images/movies/000/905/132/posters/medium/7d648ba4cb.jpg.webp",
                ),
                # No IMDb id: dropped from the catalog.
                _trending_movie_payload("tt999999", "Has IMDb", None)
                | {"movie": {"ids": {"imdb": None}, "title": "No IMDb", "year": 2024}},
            ],
        )
        response = await service.get_catalog("trending", "movie")

    assert len(response.metas) == 1
    assert response.metas[0].id == "tt22084616"
    assert response.metas[0].type == "movie"
    assert response.metas[0].name == "Spider-Man: Brand New Day"
    assert (
        response.metas[0].poster
        == "https://media.trakt.tv/images/movies/000/905/132/posters/medium/7d648ba4cb.jpg.webp"
    )


@pytest.mark.asyncio
async def test_get_catalog_trending_shows(service):
    """Trending series serve English titles with scheme-normalised posters."""
    with aioresponses_ctx() as m:
        m.get(
            TRAKT_TRENDING_SHOWS_URL,
            payload=[
                _trending_show_payload(
                    "tt0121955",
                    "South Park",
                    "media.trakt.tv/images/shows/000/002/177/posters/medium/9cb5875b93.jpg.webp",
                ),
            ],
        )
        response = await service.get_catalog("trending", "series")

    assert len(response.metas) == 1
    assert response.metas[0].id == "tt0121955"
    assert response.metas[0].type == "series"
    assert response.metas[0].name == "South Park"
    assert (
        response.metas[0].poster
        == "https://media.trakt.tv/images/shows/000/002/177/posters/medium/9cb5875b93.jpg.webp"
    )


@pytest.mark.asyncio
async def test_get_catalog_trending_cached(service):
    """Trending is cached in Redis; a second call makes no HTTP request."""
    with aioresponses_ctx() as m:
        m.get(
            TRAKT_TRENDING_MOVIES_URL,
            payload=[
                _trending_movie_payload("tt22084616", "Spider-Man: Brand New Day", None),
            ],
        )
        await service.get_catalog("trending", "movie")

    # No mock context: any HTTP call would raise.
    cached = await service.get_catalog("trending", "movie")
    assert cached.metas[0].id == "tt22084616"


@pytest.mark.asyncio
async def test_get_catalog_rejects_unknown_ids(service):
    """Only the trending catalog id is accepted."""
    with pytest.raises(ValueError):
        await service.get_catalog("bauxite", "movie")

    with pytest.raises(ValueError):
        await service.get_catalog("trending", "other")
