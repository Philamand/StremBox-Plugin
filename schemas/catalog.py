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


class StremioMeta(BaseModel):
    """Meta detail of a single movie or series as consumed by Stremio."""

    id: str
    type: str
    name: str
    poster: str | None = None
    background: str | None = None


class StremioMetaResponse(BaseModel):
    """Response of the Stremio ``meta`` resource."""

    meta: StremioMeta
