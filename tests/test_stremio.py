# This file is AI-generated
"""Tests for ``StremioOrchestrationService.has_bauxite_torrent``.

The matching relies on two metadata lookups: the Cinemeta title/year
(``utils.stremio.get_torrent_name``) and the French title from
``TraktService.get_french_translation`` (resolved through the Trakt
``get_movie_meta``/``get_show_meta`` slug lookup). Both are reached through
the shared aiohttp session, so ``aioresponses`` replays canned payloads and
no real network call is made. No Redis cache is involved.

Torrents already in Bauxite are passed in as a plain ``dict`` keyed by info
hash, mirroring what ``BauxiteService.get_torrent_hashes`` returns.
"""

from collections.abc import AsyncGenerator

import aiohttp
import pytest
import pytest_asyncio
from aioresponses import aioresponses as aioresponses_ctx

from http_client import init_http_session
from schemas.trakt import TraktMovie, TraktMovieIds, TraktShow, TraktShowIds
from services.stremio import StremioOrchestrationService

CINEMETA_BASE_URL = "https://v3-cinemeta.strem.io/meta"
TRAKT_BASE_URL = "https://api.trakt.tv"


def _cinemeta_payload(name: str, year: str | None) -> dict:
    return {"meta": {"name": name, **({"year": year} if year else {})}}


def _torrent(name: str) -> dict:
    return {"name": name, "percent_done": 1.0, "files": [], "size": 0}


class _StubTraktService:
    """Minimal TraktService stub exposing the slug/translation lookups."""

    def __init__(self, media=None, translation=None):
        self.media = media
        self.translation = translation
        self.requested = []

    async def get_movie_meta(self, imdb_id):
        self.requested.append(("movie_meta", imdb_id))
        return self.media

    async def get_show_meta(self, imdb_id):
        self.requested.append(("show_meta", imdb_id))
        return self.media

    async def get_french_translation(self, media_type, slug):
        self.requested.append(("translation", media_type, slug))
        return self.translation


@pytest_asyncio.fixture
async def http_session() -> AsyncGenerator[None]:
    """Initialise the shared aiohttp session for the duration of each test."""
    await init_http_session()
    try:
        yield
    finally:
        from http_client import close_http_session

        await close_http_session()


@pytest_asyncio.fixture
async def service(http_session: None) -> StremioOrchestrationService:
    """An orchestrator without tracker, BetaSeries or Trakt clients."""
    return StremioOrchestrationService("http://librebox", "token")


@pytest.fixture
def cinemeta_api() -> AsyncGenerator[aioresponses_ctx]:
    """Mock the Cinemeta HTTP API for the duration of a test."""
    with aioresponses_ctx() as mocked:
        yield mocked


@pytest.mark.asyncio
async def test_has_bauxite_torrent_matches_movie_by_title_and_year(
    service, cinemeta_api
):
    cinemeta_api.get(
        f"{CINEMETA_BASE_URL}/movie/tt1375666.json",
        payload=_cinemeta_payload("Inception", "2010–"),
    )
    hashes = {"abc123": _torrent("Inception.2010.1080p.BluRay.x264")}

    assert await service.has_bauxite_torrent(hashes, "tt1375666", "movie") is True


@pytest.mark.asyncio
async def test_has_bauxite_torrent_returns_false_when_no_title_match(
    service, cinemeta_api
):
    cinemeta_api.get(
        f"{CINEMETA_BASE_URL}/movie/tt1375666.json",
        payload=_cinemeta_payload("Inception", "2010–"),
    )
    hashes = {"abc123": _torrent("Interstellar.2014.1080p.BluRay.x264")}

    assert await service.has_bauxite_torrent(hashes, "tt1375666", "movie") is False


@pytest.mark.asyncio
async def test_has_bauxite_torrent_matches_series_episode(service, cinemeta_api):
    cinemeta_api.get(
        f"{CINEMETA_BASE_URL}/series/tt1234567.json",
        payload=_cinemeta_payload("Some Show", "2020–2024"),
    )
    hashes = {
        "abc123": _torrent("Some.Show.S01E01.1080p.WEB.h264"),
        "def456": _torrent("Some.Show.S01E02.1080p.WEB.h264"),
    }

    assert (
        await service.has_bauxite_torrent(
            hashes, "tt1234567", "series", season=1, episode=2
        )
        is True
    )
    assert (
        await service.has_bauxite_torrent(
            hashes, "tt1234567", "series", season=1, episode=3
        )
        is False
    )


@pytest.mark.asyncio
async def test_has_bauxite_torrent_returns_false_when_title_unknown(
    service, cinemeta_api
):
    cinemeta_api.get(
        f"{CINEMETA_BASE_URL}/movie/tt1375666.json",
        payload={},
    )
    hashes = {"abc123": _torrent("Inception.2010.1080p.BluRay.x264")}

    assert await service.has_bauxite_torrent(hashes, "tt1375666", "movie") is False


@pytest.mark.asyncio
async def test_has_bauxite_torrent_returns_false_on_cinemeta_error(
    service, cinemeta_api
):
    cinemeta_api.get(
        f"{CINEMETA_BASE_URL}/movie/tt1375666.json",
        exception=aiohttp.ClientConnectionError(),
    )
    hashes = {"abc123": _torrent("Inception.2010.1080p.BluRay.x264")}

    assert await service.has_bauxite_torrent(hashes, "tt1375666", "movie") is False


@pytest.mark.asyncio
async def test_has_bauxite_torrent_returns_false_with_empty_library(
    service, cinemeta_api
):
    hashes = {}

    assert await service.has_bauxite_torrent(hashes, "tt1375666", "movie") is False


@pytest.mark.asyncio
async def test_has_bauxite_torrent_matches_movie_on_french_title(
    http_session, cinemeta_api
):
    """A movie torrent named with the French title matches via Trakt."""
    service = StremioOrchestrationService(
        "http://librebox",
        "token",
        trakt_service=_StubTraktService(
            media=TraktMovie(ids=TraktMovieIds(slug="frozen-ii-2019"), title="Frozen II"),
            translation={"title": "La Reine des Neiges 2", "overview": None, "tagline": None},
        ),
    )
    cinemeta_api.get(
        f"{CINEMETA_BASE_URL}/movie/tt4520988.json",
        payload=_cinemeta_payload("Frozen II", "2019"),
    )
    hashes = {
        "abc123": _torrent(
            "La.Reine.Des.Neiges.2.2019.MULTi.UHD.BluRay.2160p.HEVC-DDR.mkv"
        )
    }

    assert await service.has_bauxite_torrent(hashes, "tt4520988", "movie") is True


@pytest.mark.asyncio
async def test_french_title_lookup_uses_movie_slug_and_translation(
    http_session, cinemeta_api
):
    """The movie lookup goes through get_movie_meta then the fr translation."""
    trakt = _StubTraktService(
        media=TraktMovie(ids=TraktMovieIds(slug="frozen-ii-2019"), title="Frozen II"),
        translation={"title": "La Reine des Neiges 2", "overview": None, "tagline": None},
    )
    service = StremioOrchestrationService(
        "http://librebox", "token", trakt_service=trakt
    )
    cinemeta_api.get(
        f"{CINEMETA_BASE_URL}/movie/tt4520988.json",
        payload=_cinemeta_payload("Frozen II", "2019"),
    )
    hashes = {"abc123": _torrent("Frozen 2 (2019) MULTi 2160p BluRay x265-QTZ.mkv")}

    assert await service.has_bauxite_torrent(hashes, "tt4520988", "movie") is True
    assert trakt.requested == [
        ("movie_meta", "tt4520988"),
        ("translation", "movie", "frozen-ii-2019"),
    ]


@pytest.mark.asyncio
async def test_has_bauxite_torrent_matches_series_on_french_title(
    http_session, cinemeta_api
):
    """A series torrent named with the French title matches via Trakt."""
    trakt = _StubTraktService(
        media=TraktShow(ids=TraktShowIds(slug="some-show"), title="Some Show"),
        translation={"title": "Un Show Quelconque", "overview": None, "tagline": None},
    )
    service = StremioOrchestrationService(
        "http://librebox", "token", trakt_service=trakt
    )
    cinemeta_api.get(
        f"{CINEMETA_BASE_URL}/series/tt1234567.json",
        payload=_cinemeta_payload("Some Show", "2020"),
    )
    hashes = {
        "abc123": _torrent("Un.Show.Quelconque.S01E01.1080p.WEB.h264"),
    }

    assert (
        await service.has_bauxite_torrent(
            hashes, "tt1234567", "series", season=1, episode=1
        )
        is True
    )
    assert trakt.requested == [
        ("show_meta", "tt1234567"),
        ("translation", "show", "some-show"),
    ]


@pytest.mark.asyncio
async def test_french_title_none_without_trakt_service(http_session, cinemeta_api):
    """Without a Trakt client the French title is None; English still matches."""
    cinemeta_api.get(
        f"{CINEMETA_BASE_URL}/movie/tt1375666.json",
        payload=_cinemeta_payload("Inception", "2010"),
    )
    service = StremioOrchestrationService("http://librebox", "token")
    hashes = {"abc123": _torrent("Inception.2010.1080p.BluRay.x264")}

    assert await service.has_bauxite_torrent(hashes, "tt1375666", "movie") is True


@pytest.mark.asyncio
async def test_french_title_none_when_no_translation(http_session, cinemeta_api):
    """A movie without a French translation falls back to the English title."""
    trakt = _StubTraktService(
        media=TraktMovie(ids=TraktMovieIds(slug="inception-2010"), title="Inception"),
        translation=None,
    )
    service = StremioOrchestrationService(
        "http://librebox", "token", trakt_service=trakt
    )
    cinemeta_api.get(
        f"{CINEMETA_BASE_URL}/movie/tt1375666.json",
        payload=_cinemeta_payload("Inception", "2010"),
    )
    hashes = {"abc123": _torrent("Inception.2010.1080p.BluRay.x264")}

    assert await service.has_bauxite_torrent(hashes, "tt1375666", "movie") is True
