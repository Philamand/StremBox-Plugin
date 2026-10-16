from constants import MANIFEST, TRENDING_CATALOG_ID
from schemas.catalog import (
    StremioCatalogResponse,
    StremioMeta,
    StremioMetaPreview,
    StremioMetaResponse,
)
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
        search: str | None = None,
    ) -> StremioCatalogResponse:
        """Return the metas of a catalog.

        Args:
            catalog_id: ``"trending"`` (Trakt trending movies or shows).
            media_type: ``"movie"`` or ``"series"``.
            search: Optional search query from Stremio; when given, the
                Trakt text search is used instead of the trending list.

        Returns:
            A ``StremioCatalogResponse`` with one meta preview per entry.
        """
        if media_type not in MANIFEST["types"]:
            raise ValueError(f"Unsupported catalog type: {media_type}")
        if catalog_id != TRENDING_CATALOG_ID:
            raise ValueError(f"Unknown catalog: {catalog_id}")

        if search:
            return await self._search(media_type, search)

        if media_type == "series":
            return await self._get_trending_shows()
        return await self._get_trending_movies()

    async def get_meta(self, media_type: str, imdb_id: str) -> StremioMetaResponse:
        """Return the full metadata of a movie or series.

        Served from Trakt (``extended=full``), cached for a day. Posters
        and fanart are scheme-normalised; the fanart doubles as the
        background image.
        """
        if media_type == "series":
            media = await self.trakt_service.get_show_meta(imdb_id)
        else:
            media = await self.trakt_service.get_movie_meta(imdb_id)

        if media is None:
            raise ValueError(f"Metadata not found: {imdb_id}")

        poster = None
        background = None
        if media.images:
            if media.images.poster:
                poster = normalize_poster_url(media.images.poster[0])
            if media.images.fanart:
                background = normalize_poster_url(media.images.fanart[0])

        release_info = str(media.year) if media.year else None
        runtime = f"{int(media.runtime)} min" if media.runtime else None

        return StremioMetaResponse(
            meta=StremioMeta(
                id=imdb_id,
                type=media_type,
                name=media.title,
                poster=poster,
                background=background,
                description=media.overview,
                releaseInfo=release_info,
                genres=media.genres,
                runtime=runtime,
                trailer=media.trailer,
            )
        )

    async def _search(
        self, media_type: str, search: str
    ) -> StremioCatalogResponse:
        """Search movies or shows by title via the Trakt text search."""
        trakt_type = "show" if media_type == "series" else "movie"
        results = await self.trakt_service.search_media(
            search, trakt_type, limit=40
        )
        metas = []
        for result in results:
            media = getattr(result, trakt_type)
            if not media or not media.ids.imdb:
                continue
            poster = None
            if media.images and media.images.poster:
                poster = normalize_poster_url(media.images.poster[0])
            metas.append(
                StremioMetaPreview(
                    id=media.ids.imdb,
                    type=media_type,
                    name=media.title,
                    poster=poster,
                )
            )
        return StremioCatalogResponse(metas=metas)

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
