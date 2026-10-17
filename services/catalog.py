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
    StremioVideo,
)
from schemas.trakt import (
    TraktEpisode,
    TraktFavoriteMovie,
    TraktFavoriteShow,
    TraktWatchlistMovie,
    TraktWatchlistShow,
)
from services.trakt import TraktService
from utils.stremio import normalize_poster_url


class CatalogService:
    """Build the Stremio catalogs.

    The trending catalogs are served from the Trakt trending endpoints;
    the lists are identical for every user sharing a certification and
    cached inside the Trakt service, so a catalog request is at most one
    Trakt call per hour per certification.
    """

    def __init__(
        self,
        trakt_service: TraktService,
        *,
        user_slug: str | None = None,
        certification: str | None = None,
        librebox_url: str | None = None,
        librebox_token: str | None = None,
        betaseries_service=None,
    ):
        self.trakt_service = trakt_service
        self.user_slug = user_slug
        self.certification = certification
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
        on every request. Favorites follow, cached an hour per user. Both
        lists are requested with ``extended=full`` so the posters come
        with the entries.
        """
        metas: list[StremioMetaPreview] = []

        # Watchlist: only entries already present in Bauxite.
        if self.bauxite_matcher and self.bauxite_service and self.user_slug:
            if media_type == "series":
                watchlist = await self.trakt_service.get_unwatched_shows(
                    self.user_slug, extended=True
                )
            else:
                watchlist = await self.trakt_service.get_unwatched_movies(
                    self.user_slug, extended=True
                )

            hashes = await self.bauxite_service.get_torrent_hashes()
            for entry in watchlist:
                if media_type == "series":
                    if not isinstance(entry, TraktWatchlistShow):
                        continue
                    media = entry.show
                else:
                    if not isinstance(entry, TraktWatchlistMovie):
                        continue
                    media = entry.movie
                if not media.ids.imdb:
                    continue
                if not await self.bauxite_matcher.has_bauxite_torrent(
                    hashes, media.ids.imdb, media_type
                ):
                    continue
                trakt_type = "show" if media_type == "series" else "movie"
                metas.append(await self._french_preview(media, trakt_type, media_type))

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
                trakt_type = "show" if media_type == "series" else "movie"
                metas.append(await self._french_preview(media, trakt_type, media_type))

        return StremioCatalogResponse(metas=metas)

    @staticmethod
    def _preview_from_media(media, imdb_id: str, media_type: str) -> StremioMetaPreview:
        """Build a meta preview from a Trakt media object with images."""
        poster = None
        if media.images and media.images.poster:
            poster = normalize_poster_url(media.images.poster[0])
        return StremioMetaPreview(
            id=imdb_id, type=media_type, name=media.title, poster=poster
        )

    async def _french_name(self, media_type: str, media) -> str:
        """Return the French (France) title of a media, English fallback.

        Translations are cached for a month; items without a French
        translation keep their original title.
        """
        slug = getattr(media.ids, "slug", None)
        if not slug:
            return media.title
        translation = await self.trakt_service.get_french_translation(media_type, slug)
        if translation and translation.get("title"):
            return translation["title"]
        return media.title

    async def _french_preview(
        self, media, trakt_type: str, stremio_type: str | None = None
    ) -> StremioMetaPreview:
        """Build a meta preview with the French (France) title.

        Args:
            media: A Trakt media object (movie or show) with images.
            trakt_type: ``"movie"`` or ``"show"``.
            stremio_type: ``"movie"`` or ``"series"``; defaults to the
                Stremio equivalent of *trakt_type*.
        """
        if stremio_type is None:
            stremio_type = "series" if trakt_type == "show" else "movie"
        preview = self._preview_from_media(media, media.ids.imdb, stremio_type)
        preview.name = await self._french_name(trakt_type, media)
        return preview

    async def _get_favorite_movies(self):
        """Fetch the user's favorite movies, cached an hour."""

        if not self.user_slug:
            return []
        slug = self.user_slug

        async def fetch():
            entries = await self.trakt_service.get_favorite_movies(slug, extended=True)
            return [e.movie.model_dump() for e in entries]

        cached = await cached_call(
            f"trakt:favorites:movie:{slug}", 3600, fetch, cache_none=True
        )
        return [TraktFavoriteMovie.model_validate(item) for item in cached or []]

    async def _get_favorite_shows(self):
        """Fetch the user's favorite shows, cached an hour."""

        if not self.user_slug:
            return []
        slug = self.user_slug

        async def fetch():
            entries = await self.trakt_service.get_favorite_shows(slug, extended=True)
            return [e.show.model_dump() for e in entries]

        cached = await cached_call(
            f"trakt:favorites:show:{slug}", 3600, fetch, cache_none=True
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
        videos = None
        if media_type == "series":
            videos = await self._get_series_videos(imdb_id)

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
                videos=videos,
            )
        )

    async def _get_series_videos(self, imdb_id: str) -> list[StremioVideo]:
        """Build the Stremio video list of a series from the Trakt seasons."""
        show = await self.trakt_service.get_show_meta(imdb_id)
        if show is None or not show.ids.trakt:
            return []
        seasons = await self.trakt_service.get_all_seasons(str(show.ids.trakt))
        videos = []
        for season in sorted(seasons, key=lambda s: s.number):
            for episode in sorted(season.episodes, key=lambda e: e.number):
                videos.append(
                    StremioVideo(
                        id=f"{imdb_id}:{episode.season}:{episode.number}",
                        title=episode.title or f"Episode {episode.number}",
                        released=self._episode_released(episode),
                        season=episode.season,
                        episode=episode.number,
                    )
                )
        return videos

    @staticmethod
    def _episode_released(episode: TraktEpisode) -> str:
        """Return an ISO 8601 release date, falling back to a safe default."""
        if episode.first_aired:
            return episode.first_aired
        return "2000-01-01T00:00:00.000Z"

    async def _search(self, media_type: str, search: str) -> StremioCatalogResponse:
        """Search movies or shows by title via the Trakt text search."""
        trakt_type = "show" if media_type == "series" else "movie"
        results = await self.trakt_service.search_media(search, trakt_type, limit=40)
        metas = []
        for result in results:
            media = getattr(result, trakt_type)
            if not media or not media.ids.imdb:
                continue
            metas.append(await self._french_preview(media, trakt_type, media_type))
        return StremioCatalogResponse(metas=metas)

    async def _get_trending_movies(self) -> StremioCatalogResponse:
        """Return the Trakt trending movies catalog (French titles)."""
        trending = await self.trakt_service.get_trending_movies(
            limit=40, certification=self.certification
        )
        metas = []
        for entry in trending:
            if not entry.movie.ids.imdb:
                continue
            metas.append(await self._french_preview(entry.movie, "movie"))
        return StremioCatalogResponse(metas=metas)

    async def _get_trending_shows(self) -> StremioCatalogResponse:
        """Return the Trakt trending shows catalog (French titles)."""
        trending = await self.trakt_service.get_trending_shows(
            limit=40, certification=self.certification
        )
        metas = []
        for entry in trending:
            if not entry.show.ids.imdb:
                continue
            metas.append(await self._french_preview(entry.show, "show"))
        return StremioCatalogResponse(metas=metas)
