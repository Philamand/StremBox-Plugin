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
TRAKT_MOVIE_SEARCH_URL = re.compile(r"https://api\.trakt\.tv/search/movie\?.*")
TRAKT_IMDB_LOOKUP_URL = re.compile(r"https://api\.trakt\.tv/search/imdb/.*")
TRAKT_TRANSLATIONS_URL = re.compile(
    r"https://api\.trakt\.tv/(movies|shows)/.*/translations\?.*"
)
TRAKT_FAVORITES_URL = re.compile(r"https://api\.trakt\.tv/users/.*/favorites/.*")
TRAKT_WATCHLIST_URL = re.compile(r"https://api\.trakt\.tv/users/.*/watchlist/.*")
CINEMETA_URL = re.compile(r"https://v3-cinemeta\.strem\.io/meta/.*")
TRAKT_SHOW_SEARCH_URL = re.compile(r"https://api\.trakt\.tv/search/show\?.*")
TRAKT_SEASONS_URL = re.compile(r"https://api\.trakt\.tv/shows/.*/seasons\?.*")


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


@pytest.mark.asyncio
async def test_get_catalog_search_movies(service):
    """A search on the movie catalog queries the Trakt movie search."""
    with aioresponses_ctx() as m:
        m.get(
            TRAKT_MOVIE_SEARCH_URL,
            payload=[
                {
                    "score": 2893615515668842500,
                    "type": "movie",
                    "movie": {
                        "ids": {"imdb": "tt0109440", "trakt": 9159},
                        "title": "Fear City: A Family-Style Comedy",
                        "year": 1994,
                        "images": {
                            "poster": [
                                "media.trakt.tv/images/movies/000/009/159/posters/medium/ac399a6d86.jpg.webp"
                            ]
                        },
                    },
                },
                {
                    "score": 2893615515668842500,
                    "type": "movie",
                    "movie": {
                        "ids": {"imdb": None, "trakt": 327018},
                        "title": "No IMDb",
                        "year": 2026,
                    },
                },
            ],
        )
        response = await service.get_catalog("trending", "movie", search="la cite de la peur")

    assert len(response.metas) == 1
    assert response.metas[0].id == "tt0109440"
    assert response.metas[0].name == "Fear City: A Family-Style Comedy"
    assert (
        response.metas[0].poster
        == "https://media.trakt.tv/images/movies/000/009/159/posters/medium/ac399a6d86.jpg.webp"
    )


@pytest.mark.asyncio
async def test_get_catalog_search_shows(service):
    """A search on the series catalog queries the Trakt show search."""
    with aioresponses_ctx() as m:
        m.get(
            TRAKT_SHOW_SEARCH_URL,
            payload=[
                {
                    "score": 578730123365189600,
                    "type": "show",
                    "show": {
                        "ids": {"imdb": "tt7678620", "trakt": 136999},
                        "title": "Bluey",
                        "year": 2018,
                        "images": {
                            "poster": [
                                "media.trakt.tv/images/shows/000/136/999/posters/medium/e5e8d5dd92.jpg.webp"
                            ]
                        },
                    },
                },
            ],
        )
        response = await service.get_catalog("trending", "series", search="bluey")

    assert len(response.metas) == 1
    assert response.metas[0].id == "tt7678620"
    assert response.metas[0].type == "series"
    assert response.metas[0].name == "Bluey"
    assert (
        response.metas[0].poster
        == "https://media.trakt.tv/images/shows/000/136/999/posters/medium/e5e8d5dd92.jpg.webp"
    )


@pytest.mark.asyncio
async def test_get_meta_movie(service):
    """Movie meta is served from the Trakt ID lookup with full fields."""
    with aioresponses_ctx() as m:
        m.get(
            TRAKT_IMDB_LOOKUP_URL,
            payload=[
                {
                    "score": 1.0,
                    "type": "movie",
                    "movie": {
                        "ids": {"imdb": "tt32141377", "trakt": 1033738},
                        "title": "28 Years Later: The Bone Temple",
                        "year": 2026,
                        "overview": (
                            "Dr. Kelson finds himself in a shocking new "
                            "relationship..."
                        ),
                        "genres": ["horror", "science-fiction", "thriller"],
                        "runtime": 109,
                        "trailer": "https://youtube.com/watch?v=rl_DJZCyEH4",
                        "images": {
                            "poster": [
                                "media.trakt.tv/images/movies/001/033/738/posters/medium/490a2d3fbb.jpg.webp"
                            ],
                            "fanart": [
                                "media.trakt.tv/images/movies/001/033/738/fanarts/medium/4d1014abc0.jpg.webp"
                            ],
                        },
                    },
                },
            ],
        )
        meta = await service.get_meta("movie", "tt32141377")

    assert meta.meta.id == "tt32141377"
    assert meta.meta.type == "movie"
    assert meta.meta.name == "28 Years Later: The Bone Temple"
    assert meta.meta.releaseInfo == "2026"
    assert meta.meta.genres == ["horror", "science-fiction", "thriller"]
    assert meta.meta.runtime == "109 min"
    assert (
        meta.meta.poster
        == "https://media.trakt.tv/images/movies/001/033/738/posters/medium/490a2d3fbb.jpg.webp"
    )
    assert (
        meta.meta.background
        == "https://media.trakt.tv/images/movies/001/033/738/fanarts/medium/4d1014abc0.jpg.webp"
    )


@pytest.mark.asyncio
async def test_get_meta_show(service):
    """Show meta is served from the Trakt ID lookup, with episode videos."""
    with aioresponses_ctx() as m:
        m.get(
            TRAKT_IMDB_LOOKUP_URL,
            payload=[
                {
                    "score": 1.0,
                    "type": "show",
                    "show": {
                        "ids": {"imdb": "tt27497393", "trakt": 280856},
                        "title": "Stuart Fails to Save the Universe",
                        "year": 2026,
                        "overview": (
                            "After accidentally creating a new multiverse..."
                        ),
                        "genres": ["comedy", "fantasy", "science-fiction"],
                        "runtime": 24,
                        "network": "HBO Max",
                        "images": {"poster": ["media.trakt.tv/images/shows/poster.jpg"]},
                    },
                },
            ],
        )
        m.get(
            TRAKT_SEASONS_URL,
            payload=[
                {
                    "ids": {"trakt": 1, "tmdb": 1, "tvdb": 1},
                    "number": 0,
                    "episodes": [
                        {
                            "ids": {"trakt": 11, "imdb": "tt0000001"},
                            "title": "Special",
                            "number": 1,
                            "season": 0,
                            "first_aired": "2025-12-01T00:00:00.000Z",
                        }
                    ],
                },
                {
                    "ids": {"trakt": 2, "tmdb": 2, "tvdb": 2},
                    "number": 1,
                    "episodes": [
                        {
                            "ids": {"trakt": 21, "imdb": "tt0000002"},
                            "title": "Pilot",
                            "number": 1,
                            "season": 1,
                            "first_aired": "2026-01-01T00:00:00.000Z",
                        },
                        {
                            "ids": {"trakt": 22, "imdb": "tt0000003"},
                            "title": None,
                            "number": 2,
                            "season": 1,
                        },
                    ],
                },
            ],
        )
        meta = await service.get_meta("series", "tt27497393")

    assert meta.meta.id == "tt27497393"
    assert meta.meta.type == "series"
    assert meta.meta.name == "Stuart Fails to Save the Universe"
    assert meta.meta.releaseInfo == "2026"
    assert meta.meta.runtime == "24 min"
    assert meta.meta.videos is not None
    assert len(meta.meta.videos) == 3
    assert meta.meta.videos[0].id == "tt27497393:0:1"
    assert meta.meta.videos[1].id == "tt27497393:1:1"
    assert meta.meta.videos[1].title == "Pilot"
    assert meta.meta.videos[1].released == "2026-01-01T00:00:00.000Z"
    assert meta.meta.videos[1].season == 1
    assert meta.meta.videos[1].episode == 1
    assert meta.meta.videos[2].title == "Episode 2"
    assert meta.meta.videos[2].released == "2000-01-01T00:00:00.000Z"


@pytest.mark.asyncio
async def test_get_meta_not_found(service):
    """An unknown id raises ValueError (the route turns it into a 404)."""
    with aioresponses_ctx() as m:
        m.get(TRAKT_IMDB_LOOKUP_URL, payload=[])

        with pytest.raises(ValueError):
            await service.get_meta("movie", "tt9999999")


def _library_service(stub_redis) -> CatalogService:
    from services.betaseries import BetaSeriesService

    return CatalogService(
        TraktService(api_key="trakt-key"),
        user_slug="some-user",
        librebox_url="http://librebox",
        librebox_token="token",
        betaseries_service=BetaSeriesService(api_key="bs-key"),
    )


@pytest.mark.asyncio
async def test_get_catalog_library_movies(stub_redis, http_session):
    """Favorites are included; watchlist only when present in Bauxite."""
    service = _library_service(stub_redis)

    favorite_movie = {
        "ids": {"imdb": "tt111111", "trakt": 1},
        "title": "Favorite Movie",
        "year": 2020,
        "images": {"poster": ["media.trakt.tv/images/posters/fav.jpg"]},
    }
    # Watchlist entry present on the seedbox...
    watchlisted_present = {
        "ids": {"imdb": "tt222222", "trakt": 2},
        "title": "Watchlisted Movie",
        "year": 2021,
        "images": {"poster": ["media.trakt.tv/images/posters/watch.jpg"]},
    }
    # ...and one absent from it.
    watchlisted_absent = {
        "ids": {"imdb": "tt333333", "trakt": 3},
        "title": "Not Downloaded",
        "year": 2022,
    }

    with aioresponses_ctx() as m:
        m.get(
            TRAKT_FAVORITES_URL,
            payload=[
                {
                    "id": 1,
                    "listed_at": "2026-01-01T00:00:00Z",
                    "rank": 0,
                    "type": "movie",
                    "movie": favorite_movie,
                }
            ],
        )
        m.get(
            TRAKT_WATCHLIST_URL,
            payload=[
                {
                    "type": "movie",
                    "movie": watchlisted_present,
                    "rank": 1,
                    "id": 2,
                    "listed_at": "2026-01-01T00:00:00Z",
                },
                {
                    "type": "movie",
                    "movie": watchlisted_absent,
                    "rank": 2,
                    "id": 3,
                    "listed_at": "2026-01-01T00:00:00Z",
                },
            ],
        )
        m.get(
            "http://librebox/api/hashes/",
            payload={
                "abc": {
                    "name": "Watchlisted.Movie.2021.FRENCH.1080p.WEB.x264-G",
                    "percent_done": 1.0,
                    "files": [],
                }
            },
        )
        # has_bauxite_torrent resolves titles via Cinemeta and the French
        # title via the Trakt slug lookup; the absent entry resolves too but
        # matches no torrent.
        m.get(
            CINEMETA_URL,
            payload={"meta": {"name": "Watchlisted Movie", "year": "2021"}},
        )
        m.get(
            CINEMETA_URL,
            payload={"meta": {"name": "Not Downloaded", "year": "2022"}},
        )
        m.get(
            re.compile(r"https://api\.trakt\.tv/search/imdb/tt222222.*"),
            payload=[
                {
                    "type": "movie",
                    "movie": {
                        "ids": {"imdb": "tt222222", "slug": "watchlisted-movie"},
                        "title": "Watchlisted Movie",
                        "year": 2021,
                    },
                }
            ],
        )
        m.get(
            re.compile(r"https://api\.trakt\.tv/search/imdb/tt333333.*"),
            payload=[],
        )
        m.get(
            re.compile(
                r"https://api\.trakt\.tv/movies/watchlisted-movie/translations\?.*"
            ),
            payload=[
                {
                    "title": "Film Sur Liste",
                    "overview": None,
                    "tagline": None,
                    "language": "fr",
                    "country": "fr",
                }
            ],
        )

        response = await service.get_catalog("library", "movie")

    ids = [meta.id for meta in response.metas]
    assert "tt111111" in ids  # favorite
    assert "tt222222" in ids  # watchlisted + on the seedbox
    assert "tt333333" not in ids  # watchlisted but absent

    posters = {meta.id: meta.poster for meta in response.metas}
    assert posters["tt111111"] == "https://media.trakt.tv/images/posters/fav.jpg"
    assert posters["tt222222"] == "https://media.trakt.tv/images/posters/watch.jpg"

    # Watchlist entries are listed before favorites.
    assert ids.index("tt222222") < ids.index("tt111111")


@pytest.mark.asyncio
async def test_get_catalog_library_without_trakt_slug(stub_redis, http_session):
    """Without a trakt_slug the library catalog is simply empty."""
    service = CatalogService(TraktService(api_key="trakt-key"))
    response = await service.get_catalog("library", "movie")
    assert response.metas == []


@pytest.mark.asyncio
async def test_trending_movies_use_french_titles(service):
    """Trending entries display the French (France) title."""
    with aioresponses_ctx() as m:
        m.get(
            TRAKT_TRENDING_MOVIES_URL,
            payload=[
                {
                    "watchers": 10,
                    "movie": {
                        "ids": {
                            "imdb": "tt1",
                            "slug": "kaamelott-the-second-chapter-part-i-2025",
                        },
                        "title": "Kaamelott: The Second Chapter",
                        "year": 2025,
                    },
                },
            ],
        )
        m.get(
            re.compile(
                r"https://api\.trakt\.tv/movies/kaamelott-the-second-chapter-part-i-2025/translations\?.*"
            ),
            payload=[
                {
                    "title": "Kaamelott : Deuxième Volet, partie 1",
                    "overview": "Les Dieux sont en colère contre Arthur !",
                    "tagline": "Qui part à l'aventure ?",
                    "language": "fr",
                    "country": "fr",
                },
                {
                    # Canada entry: must be ignored even with a title.
                    "title": "Kaamelott Canada",
                    "overview": None,
                    "tagline": None,
                    "language": "fr",
                    "country": "ca",
                },
            ],
        )
        response = await service.get_catalog("trending", "movie")

    assert response.metas[0].name == "Kaamelott : Deuxième Volet, partie 1"


@pytest.mark.asyncio
async def test_search_shows_use_french_titles(service):
    """Search entries display the French title, English fallback."""
    with aioresponses_ctx() as m:
        m.get(
            TRAKT_SHOW_SEARCH_URL,
            payload=[
                {
                    "score": 1,
                    "type": "show",
                    "show": {
                        "ids": {"imdb": "tt2", "slug": "stuart-fails-to-save-the-universe"},
                        "title": "Stuart Fails to Save the Universe",
                        "year": 2026,
                    },
                },
                {
                    "score": 2,
                    "type": "show",
                    # No slug: no translation call, English title kept.
                    "show": {
                        "ids": {"imdb": "tt3"},
                        "title": "No Slug Show",
                        "year": 2020,
                    },
                },
            ],
        )
        m.get(
            re.compile(
                r"https://api\.trakt\.tv/shows/stuart-fails-to-save-the-universe/translations\?.*"
            ),
            payload=[
                {
                    "title": "Stuart fails to save the Universe",
                    "overview": "Le propriétaire de la boutique de comics...",
                    "tagline": "Chaque univers a besoin d'un héros.",
                    "language": "fr",
                    "country": "fr",
                },
                {
                    # Canada entry with a null title: ignored anyway.
                    "title": None,
                    "overview": "Stuart Bloom...",
                    "tagline": None,
                    "language": "fr",
                    "country": "ca",
                },
            ],
        )
        response = await service.get_catalog("trending", "series", search="stuart")

    names = {meta.id: meta.name for meta in response.metas}
    assert names["tt2"] == "Stuart fails to save the Universe"
    assert names["tt3"] == "No Slug Show"


@pytest.mark.asyncio
async def test_french_title_falls_back_to_english(service):
    """Without a French translation the original title is kept."""
    with aioresponses_ctx() as m:
        m.get(
            TRAKT_TRENDING_MOVIES_URL,
            payload=[
                {
                    "watchers": 10,
                    "movie": {
                        "ids": {"imdb": "tt4", "slug": "some-movie"},
                        "title": "Some Movie",
                        "year": 2020,
                    },
                },
            ],
        )
        m.get(
            re.compile(r"https://api\.trakt\.tv/movies/some-movie/translations\?.*"),
            payload=[],
        )
        response = await service.get_catalog("trending", "movie")

    assert response.metas[0].name == "Some Movie"
