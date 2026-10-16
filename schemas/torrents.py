from pydantic import BaseModel


class TorrentTitleInfo(BaseModel):
    """Structured information extracted from a raw torrent name.

    Produced by ``utils.stremio.extract_title_info`` and consumed by the
    title resolution pipeline (Trakt/BetaSeries lookups, caching, catalog
    persistence).
    """

    title: str | None = None
    year: int | None = None
    type: str | None = None
    is_season_pack: bool = False
