from cache import cached_call
from constants import (
    LIBRARY_CATALOG_ID,
    MANIFEST,
    TRENDING_CATALOG_ID,
)
from schemas.catalog import (
    StremioCatalogResponse,
    StremioMeta,
    StremioMetaPreview,
    StremioMetaResponse,
)
from services.trakt import TraktService
from schemas.trakt import TraktFavoriteMovie, TraktFavoriteShow
from utils.stremio import normalize_poster_url


class CatalogService:
    """Build the Stremio catalogs.

    The trending catalogs are served from the Trakt trending endpoints;
    the lists are identical for every user and cached inside the Trakt
    service, so a catalog request is at most one Trakt call per hour.
    """

    def __init__(
        self,
        trakt_service: TraktService,
        *,
        user_slug: str | None = None,
        librebox_url: str | None = None,
        librebox_token: str | None = None,
        betaseries_service=None,
    ):
        self.trakt_service = trakt_service
        self.user_slug = user_slug
        if librebox_url and librebox_token:
            from services.stremio import StremioOrchestrationService

            self.bauxite_matcher = StremioOrchestrationService(
                librebox_url,
                librebox_token,
                betaseries_service=betaseries_service,
            )
            from services.bauxite import BauxiteService

            self.bauxite_service = BauxiteService(librebox_url, librebox_token)
        else:
            self.bauxite_matcher = None
            self.bauxite_service = None

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

        if catalog_id == LIBRARY_CATALOG_ID:
            return await self._get_library(media_type)

        if catalog_id != TRENDING_CATALOG_ID:
            raise ValueError(f"Unknown catalog: {catalog_id}")

        if search:
            return await self._search(media_type, search)

        if media_type == "series":
            return await self._get_trending_shows()
        return await self._get_trending_movies()

    async def _get_library(self, media_type: str) -> StremioCatalogResponse:
        """Return the user's Trakt library: downloadable watchlist then favorites.

        Watchlist entries come first, included only when a matching
        torrent exists on the user's seedbox; that check is re-evaluated
        on every request. Favorites follow, cached an hour per user.
        """
        metas: list[StremioMetaPreview] = []

        # Watchlist: only entries already present in Bauxite.
        if self.bauxite_matcher and self.user_slug:
            if media_type == "series":
                watchlist = await self.trakt_service.get_unwatched_shows(
                    self.user_slug
                )
            else:
                watchlist = await self.trakt_service.get_unwatched_movies(
                    self.user_slug
                )

            hashes = await self.bauxite_service.get_torrent_hashes()
            for entry in watchlist:
                media = entry.show if media_type == "series" else entry.movie
                if not media.ids.imdb:
                    continue
                if not await self.bauxite_matcher.has_bauxite_torrent(
                    hashes, media.ids.imdb, media_type
                ):
                    continue
                metas.append(await self._meta_preview(media.ids.imdb, media_type, media.title))

        # Favorites: identical for an hour, cached.
        if self.user_slug:
            if media_type == "series":
                favorites = await self._get_favorite_shows()
            else:
                favorites = await self._get_favorite_movies()

            existing_ids = {meta.id for meta in metas}
            for media in favorites:
                if not media.ids.imdb or media.ids.imdb in existing_ids:
                    continue
                metas.append(await self._meta_preview(media.ids.imdb, media_type, media.title))

        return StremioCatalogResponse(metas=metas)

    async def _meta_preview(
        self, imdb_id: str, media_type: str, title: str
    ) -> StremioMetaPreview:
        """Build a meta preview, fetching the poster from Trakt metadata.

        The metadata lookups are cached for a day, so a library entry
        costs at most one Trakt call per day.
        """
        if media_type == "series":
            media = await self.trakt_service.get_show_meta(imdb_id)
        else:
            media = await self.trakt_service.get_movie_meta(imdb_id)

        poster = None
        if media and media.images and media.images.poster:
            poster = normalize_poster_url(media.images.poster[0])

        return StremioMetaPreview(
            id=imdb_id, type=media_type, name=title, poster=poster
        )

    async def _get_favorite_movies(self):
        """Fetch the user's favorite movies, cached an hour."""
        async def fetch():
            entries = await self.trakt_service.get_favorite_movies(self.user_slug)
            return [e.movie.model_dump() for e in entries]

        cached = await cached_call(
            f"trakt:favorites:movie:{self.user_slug}", 3600, fetch, cache_none=True
        )
        return [TraktFavoriteMovie.model_validate(item) for item in cached or []]

    async def _get_favorite_shows(self):
        """Fetch the user's favorite shows, cached an hour."""
        async def fetch():
            entries = await self.trakt_service.get_favorite_shows(self.user_slug)
            return [e.show.model_dump() for e in entries]

        cached = await cached_call(
            f"trakt:favorites:show:{self.user_slug}", 3600, fetch, cache_none=True
        )
        return [TraktFavoriteShow.model_validate(item) for item in cached or []]

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
