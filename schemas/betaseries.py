from pydantic import BaseModel


class BetaSeriesSearchSvod(BaseModel):
    """A streaming platform entry in a BetaSeries search result."""

    id: int
    name: str


class BetaSeriesSearchMovie(BaseModel):
    """A movie entry from the BetaSeries search endpoint."""

    id: int
    slug: str | None = None
    release_date: int | None = None
    poster: str | None = None
    alias_title: str | None = None
    title: str


class BetaSeriesSearchShow(BaseModel):
    """A show entry from the BetaSeries search endpoint."""

    id: int
    slug: str | None = None
    release_date: int | None = None
    poster: str | None = None
    alias_title: str | None = None
    title: str


class BetaSeriesMovieDetails(BaseModel):
    """A movie details payload from the BetaSeries movie endpoint."""

    id: int
    imdb_id: str | None = None
    title: str


class BetaSeriesShowDetails(BaseModel):
    """A show details payload from the BetaSeries show endpoint."""

    id: int
    imdb_id: str | None = None
    title: str
