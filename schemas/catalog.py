from pydantic import BaseModel


class StremioMetaPreview(BaseModel):
    """A catalog entry (meta preview) as consumed by Stremio."""

    id: str
    type: str
    name: str
    poster: str | None = None


class StremioCatalogResponse(BaseModel):
    """Response of the Stremio ``catalog`` resource."""

    metas: list[StremioMetaPreview]


class StremioVideo(BaseModel):
    """An episode entry of a series meta as consumed by Stremio."""

    id: str
    title: str
    released: str
    season: int
    episode: int
    overview: str | None = None


class StremioMeta(BaseModel):
    """Meta detail of a single movie or series as consumed by Stremio."""

    id: str
    type: str
    name: str
    poster: str | None = None
    background: str | None = None
    description: str | None = None
    releaseInfo: str | None = None
    genres: list[str] | None = None
    runtime: str | None = None
    trailer: str | None = None
    videos: list[StremioVideo] | None = None


class StremioMetaResponse(BaseModel):
    """Response of the Stremio ``meta`` resource."""

    meta: StremioMeta
