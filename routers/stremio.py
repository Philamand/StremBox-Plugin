from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from constants import MANIFEST, TRENDING_CATALOG_ID
from dependencies import (
    check_user_key,
    get_betaseries_service,
    get_trakt_service,
)
from schemas.catalog import StremioCatalogResponse
from schemas.stremio import StremioStreamsResponse
from schemas.users import UserData
from services.betaseries import BetaSeriesService
from services.trakt import TraktService
from services.catalog import CatalogService
from services.stremio import StremioOrchestrationService
from services.betaseries import BetaSeriesService
from services.trakt import TraktService

router = APIRouter(dependencies=[Depends(check_user_key)])


@router.get("/{user_key}/manifest.json")
async def get_manifest():
    """Return the manifest.json file."""
    return MANIFEST


@router.get("/{user_key}/stream/{type}/{id}.json")
async def get_torrent_streams(
    request: Request,
    betaseries_service: Annotated[BetaSeriesService, Depends(get_betaseries_service)],
    type: str,
    id: str,
) -> StremioStreamsResponse:
    """
    Return Stremio-compatible stream entries for a movie or series.

    Path parameters:
    - type: ``"movie"`` or ``"series"`` (must be declared in the manifest).
    - id: IMDb id for movies (e.g. ``"tt1234567"``); for series the combined
      form ``"{imdbid}:{season}:{episode}"`` (e.g. ``"tt1234567:1:2"``).

    Results are cached in Redis for one hour. An empty stream list is not
    cached so transient failures do not poison the cache.
    """
    if type not in MANIFEST["types"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    user: UserData = request.state.user

    stremio_service = StremioOrchestrationService(
        user.librebox_url,
        user.librebox_token,
        betaseries_service=betaseries_service,
    )

    response = await stremio_service.get_bauxite_streams(type=type, id=id)

    return response


@router.get("/{user_key}/catalog/{type}/{catalog_id}.json")
async def get_catalog(
    trakt_service: Annotated[TraktService, Depends(get_trakt_service)],
    type: str,
    catalog_id: str,
    search: str | None = None,
) -> StremioCatalogResponse:
    """Return the trending catalog of movies/series.

    Path parameters:
    - type: ``"movie"`` or ``"series"`` (must be declared in the manifest).
    - catalog_id: The catalog id declared in the manifest (``"trending"``).

    Query parameters:
    - search: Optional search query sent by Stremio; served through the
      Trakt text search instead of the trending list.

    The trending lists come from the Trakt trending endpoints and are
    cached for an hour (they are identical for every user).
    """
    if type not in MANIFEST["types"] or catalog_id != TRENDING_CATALOG_ID:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    catalog_service = CatalogService(trakt_service=trakt_service)

    return await catalog_service.get_catalog(catalog_id, type, search=search)
