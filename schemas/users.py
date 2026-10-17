import uuid

from pydantic import BaseModel


class UserCreateData(BaseModel):
    """Data for creating a user."""

    librebox_url: str
    librebox_token: str
    c411_key: str | None = None
    tr4ker_key: str | None = None
    lacale_key: str | None = None
    trakt_slug: str | None = None
    certification: str | None = None


class UserData(BaseModel):
    """Data for user."""

    id: uuid.UUID
    librebox_url: str
    librebox_token: str
    c411_key: str | None = None
    tr4ker_key: str | None = None
    lacale_key: str | None = None
    trakt_slug: str | None = None
    certification: str | None = None
