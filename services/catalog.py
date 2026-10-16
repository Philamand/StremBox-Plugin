from constants import MANIFEST, TRENDING_CATALOG_ID
from schemas.catalog import StremioCatalogResponse, StremioMetaPreview
from services.trakt import TraktService
from utils.stremio import normalize_poster_url


class CatalogService:
    """Build the Stremio catalogs.

    The trending catalogs are served from the Trakt trending endpoints;
    the lists are identical for every user and cached inside the Trakt
    service, so a catalog request is at most one Trakt call per hour.
    """

    def __init__(self, trakt_service: TraktService):
        self.trakt_service = trakt_service

    async def get_catalog(
        self,
        catalog_id: str,
        media_type: str,
    ) -> StremioCatalogResponse:
        """Return the metas of a catalog.

        Args:
            catalog_id: ``"trending"`` (Trakt trending movies or shows).
            media_type: ``"movie"`` or ``"series"``.

        Returns:
            A ``StremioCatalogResponse`` with one meta preview per entry.
        """
        if media_type not in MANIFEST["types"]:
            raise ValueError(f"Unsupported catalog type: {media_type}")
        if catalog_id != TRENDING_CATALOG_ID:
            raise ValueError(f"Unknown catalog: {catalog_id}")

        if media_type == "series":
            return await self._get_trending_shows()
        return await self._get_trending_movies()

    async def _get_trending_movies(self) -> StremioCatalogResponse:
        """Return the Trakt trending movies catalog (English titles)."""
        trending = await self.trakt_service.get_trending_movies(limit=40)
        metas = []
        for entry in trending:
            if not entry.movie.ids.imdb:
                continue
            poster = None
            if entry.movie.images and entry.movie.images.poster:
                poster = normalize_poster_url(entry.movie.images.poster[0])
            metas.append(
                StremioMetaPreview(
                    id=entry.movie.ids.imdb,
                    type="movie",
                    name=entry.movie.title,
                    poster=poster,
                )
            )
        return StremioCatalogResponse(metas=metas)

    async def _get_trending_shows(self) -> StremioCatalogResponse:
        """Return the Trakt trending shows catalog (English titles)."""
        trending = await self.trakt_service.get_trending_shows(limit=40)
        metas = []
        for entry in trending:
            if not entry.show.ids.imdb:
                continue
            poster = None
            if entry.show.images and entry.show.images.poster:
                poster = normalize_poster_url(entry.show.images.poster[0])
            metas.append(
                StremioMetaPreview(
                    id=entry.show.ids.imdb,
                    type="series",
                    name=entry.show.title,
                    poster=poster,
                )
            )
        return StremioCatalogResponse(metas=metas)
