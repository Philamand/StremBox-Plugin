from cache import cached_call
from constants import MANIFEST
from schemas.catalog import StremioCatalogResponse, StremioMetaPreview
from services.bauxite import BauxiteService
from services.betaseries import BetaSeriesService
from utils.stremio import extract_title_info, torrent_is_video



class CatalogService:
    """Build the Stremio catalog of the media available on a user's seedbox.

    Torrent names are parsed with ``extract_title_info`` and each unique
    title is resolved to an IMDb id via the BetaSeries search API (two
    calls per title: search, then details for the IMDb id). The catalog is
    always built from a fresh Bauxite listing so it stays up to date; the
    individual title resolutions are cached in Redis for a day because the
    mapping rarely changes. Movie titles are displayed in French using the
    BetaSeries ``alias_title`` when available.
    """

    def __init__(
        self,
        librebox_url: str,
        librebox_token: str,
        betaseries_service: BetaSeriesService,
    ):
        self.bauxite_service = BauxiteService(librebox_url, librebox_token)
        self.betaseries_service = betaseries_service

    async def get_catalog(self, media_type: str, search: str | None = None) -> StremioCatalogResponse:
        """Return the list of metas of *media_type* present on the seedbox.

        Args:
            media_type: ``"movie"`` or ``"series"`` (must be declared in the
                manifest catalogs).
            search: Optional search query from Stremio to filter the titles.

        Returns:
            A ``StremioCatalogResponse`` with one meta preview per resolved
            title.
        """
        if media_type not in MANIFEST["types"]:
            raise ValueError(f"Unsupported catalog type: {media_type}")

        query = search.lower() if search else None

        # Always built from a fresh Bauxite listing so the catalog stays up
        # to date with the seedbox; only per-title resolutions are cached.
        hashes = await self.bauxite_service.get_torrent_hashes()
        metas: list[dict] = []
        seen_imdb_ids: set[str] = set()

        for info_hash, torrent in hashes.items():
            if not torrent_is_video(torrent["name"], torrent.get("files") or []):
                continue
            info = extract_title_info(torrent["name"])
            if info.type != media_type:
                continue

            if query and query not in info.title.lower():
                continue

            imdb_id, name, poster = await self._resolve(info)
            if not imdb_id or imdb_id in seen_imdb_ids:
                continue
            seen_imdb_ids.add(imdb_id)

            metas.append(
                {"id": imdb_id, "type": media_type, "name": name, "poster": poster}
            )

        previews = [StremioMetaPreview.model_validate(meta) for meta in metas]
        return StremioCatalogResponse(metas=previews)

    async def _resolve(
        self, info
    ) -> tuple[str | None, str | None, str | None]:
        """Resolve a parsed torrent title via the BetaSeries search API.

        The first search result with an IMDb id wins. For movies the French
        title (``alias_title``) is preferred over the original one.

        Results (including misses) are cached per title/type/year for a day.

        Returns:
            A ``(imdb_id, display_name, poster)`` tuple; the name is the
            French title for movies when BetaSeries provides one and the
            poster comes with the BetaSeries search result.
        """
        cache_key = f"betaseries:resolve:{info.type}:{info.title}:{info.year}"

        async def fetch() -> list | None:
            if info.type == "series":
                results = await self.betaseries_service.search_shows(
                    info.title, year=info.year, limit=5
                )
                for show in results:
                    imdb_id = await self.betaseries_service.get_show_imdb_id(show.id)
                    if imdb_id:
                        return [imdb_id, show.title, show.poster]
            else:
                results = await self.betaseries_service.search_movies(
                    info.title, year=info.year, limit=5
                )
                for movie in results:
                    imdb_id = await self.betaseries_service.get_movie_imdb_id(movie.id)
                    if imdb_id:
                        return [
                            imdb_id,
                            movie.alias_title or movie.title,
                            movie.poster,
                        ]
            return None

        cached = await cached_call(cache_key, 86400, fetch, cache_none=True)
        if cached is None:
            return None, None, None
        # Tolerate cache entries written before the poster field existed
        # (they only hold [imdb_id, name]).
        while len(cached) < 3:
            cached.append(None)
        return cached[0], cached[1], cached[2]
