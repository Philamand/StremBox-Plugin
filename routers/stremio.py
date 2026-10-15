from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from constants import CATALOG_ID, MANIFEST
from dependencies import (
    check_user_key,
    get_betaseries_service,
    get_trakt_service,
)
from schemas.catalog import StremioCatalogResponse, StremioMetaResponse
from schemas.stremio import StremioStreamsResponse
from schemas.users import UserData
from services.betaseries import BetaSeriesService
from services.catalog import CatalogService
from services.stremio import StremioOrchestrationService
from services.trakt import TraktError, TraktService

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
    request: Request,
    trakt_service: Annotated[TraktService, Depends(get_trakt_service)],
    type: str,
    catalog_id: str,
    search: str | None = None,
) -> StremioCatalogResponse:
    """Return the catalog of movies/series available on the user's seedbox.

    Path parameters:
    - type: ``"movie"`` or ``"series"`` (must be declared in the manifest).
    - catalog_id: The catalog id declared in the manifest (``"bauxite"``).

    Query parameters:
    - search: Optional search query sent by Stremio.

    Torrent names are parsed and resolved to IMDb ids via Trakt; the
    catalog is rebuilt from a fresh Bauxite listing on every request so
    it always reflects the seedbox. Unresolvable or non-video torrents
    are skipped.
    """
    if type not in MANIFEST["types"] or catalog_id != CATALOG_ID:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    user: UserData = request.state.user

    catalog_service = CatalogService(
        user.librebox_url, user.librebox_token, trakt_service=trakt_service
    )

    try:
        return await catalog_service.get_catalog(type, search=search)
    except TraktError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trakt search unavailable",
        )


@router.get("/{user_key}/meta/{type}/{id}.json")
async def get_meta(
    request: Request,
    trakt_service: Annotated[TraktService, Depends(get_trakt_service)],
    type: str,
    id: str,
) -> StremioMetaResponse:
    """Return the meta of a movie/series from the user's catalog.

    Stremio hydrates posters and synopsis from Cinemeta; only the id, type
    and name are provided here.
    """
    if type not in MANIFEST["types"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    user: UserData = request.state.user

    catalog_service = CatalogService(
        user.librebox_url, user.librebox_token, trakt_service=trakt_service
    )

    try:
        return await catalog_service.get_meta(type, id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
