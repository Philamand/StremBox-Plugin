# This file is AI-generated
"""Tests for ``StremioOrchestrationService.has_bauxite_torrent``.

The matching relies on two metadata lookups: the Cinemeta title/year
(``utils.stremio.get_torrent_name``) and, for series, the French title from
``BetaSeriesService.get_show_french_title``. Both are reached through the
shared aiohttp session, so ``aioresponses`` replays canned payloads and no
real network call is made. No Redis cache is involved.

Torrents already in Bauxite are passed in as a plain ``dict`` keyed by info
hash, mirroring what ``BauxiteService.get_torrent_hashes`` returns.
"""

from collections.abc import AsyncGenerator

import aiohttp
import pytest
import pytest_asyncio
from aioresponses import aioresponses as aioresponses_ctx

from http_client import init_http_session
from services.stremio import StremioOrchestrationService

CINEMETA_BASE_URL = "https://v3-cinemeta.strem.io/meta"


def _cinemeta_payload(name: str, year: str | None) -> dict:
    return {"meta": {"name": name, **({"year": year} if year else {})}}


def _torrent(name: str) -> dict:
    return {"name": name, "percent_done": 1.0, "files": [], "size": 0}


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
    """An orchestrator without tracker or BetaSeries clients."""
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
