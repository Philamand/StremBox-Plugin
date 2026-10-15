from cache import cached_call
from constants import MANIFEST
from schemas.catalog import StremioCatalogResponse, StremioMetaPreview
from services.bauxite import BauxiteService
from services.trakt import TraktService
from utils.stremio import extract_title_info, torrent_is_video



class CatalogService:
    """Build the Stremio catalog of the media available on a user's seedbox.

    Torrent names are parsed with ``extract_title_info`` and each unique
    title is resolved to an IMDb id with the Trakt text search. The catalog
    is always built from a fresh Bauxite listing so it stays up to date;
    only the individual title resolutions are cached in Redis (for a day)
    because the title to IMDb id mapping rarely changes.
    """

    def __init__(self, librebox_url: str, librebox_token: str, trakt_service: TraktService):
        self.bauxite_service = BauxiteService(librebox_url, librebox_token)
        self.trakt_service = trakt_service

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

            imdb_id = await self._resolve(info)
            if not imdb_id or imdb_id in seen_imdb_ids:
                continue
            seen_imdb_ids.add(imdb_id)

            metas.append({"id": imdb_id, "type": media_type, "name": info.title})

        previews = [StremioMetaPreview.model_validate(meta) for meta in metas]
        return StremioCatalogResponse(metas=previews)

    async def _resolve(self, info) -> str | None:
        """Resolve a parsed torrent title to an IMDb id via Trakt search.

        Results (including misses) are cached per title/type/year for a day.
        """
        media_type = "show" if info.type == "series" else "movie"
        cache_key = f"trakt:resolve:{media_type}:{info.title}:{info.year}"

        async def fetch() -> str | None:
            results = await self.trakt_service.search_media(
                info.title, media_type, year=info.year, limit=5
            )
            for result in results:
                media = getattr(result, media_type)
                if media and media.ids and media.ids.imdb:
                    return media.ids.imdb
            return None

        return await cached_call(cache_key, 86400, fetch, cache_none=True)
