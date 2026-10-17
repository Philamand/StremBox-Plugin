from pydantic import BaseModel


class TraktPlexIds(BaseModel):
    guid: str | None = None
    slug: str | None = None


class TraktImages(BaseModel):
    fanart: list[str] | None = None
    poster: list[str] | None = None
    logo: list[str] | None = None
    clearart: list[str] | None = None
    banner: list[str] | None = None
    thumb: list[str] | None = None


class TraktSocialIds(BaseModel):
    twitter: str | None = None
    facebook: str | None = None
    instagram: str | None = None
    wikipedia: str | None = None


class TraktColors(BaseModel):
    poster: list[str] | None = None


class TraktAirs(BaseModel):
    day: str | None = None
    time: str | None = None
    timezone: str | None = None


class TraktSeasonIds(BaseModel):
    plex: TraktPlexIds | None = None
    tmdb: int | None = None
    tvdb: int | None = None
    trakt: int | None = None


class TraktEpisodeIds(BaseModel):
    imdb: str | None = None
    plex: TraktPlexIds | None = None
    tmdb: int | None = None
    tvdb: int | None = None
    trakt: int | None = None


class TraktEpisode(BaseModel):
    ids: TraktEpisodeIds
    title: str | None = None
    number: int
    season: int
    first_aired: str | None = None


class TraktSeason(BaseModel):
    ids: TraktSeasonIds
    number: int
    episodes: list[TraktEpisode]


class TraktShowIds(BaseModel):
    imdb: str | None = None
    plex: TraktPlexIds | None = None
    slug: str | None = None
    tmdb: int | None = None
    tvdb: int | None = None
    trakt: int | None = None


class TraktShow(BaseModel):
    ids: TraktShowIds
    title: str
    year: int | None = None
    aired_episodes: int | None = None
    images: TraktImages | None = None
    overview: str | None = None
    genres: list[str] | None = None
    runtime: float | None = None
    status: str | None = None
    network: str | None = None
    country: str | None = None
    trailer: str | None = None
    homepage: str | None = None
    certification: str | None = None


class TraktFavoriteShow(BaseModel):
    ids: TraktShowIds
    title: str
    year: int | None = None
    images: TraktImages | None = None
    tagline: str | None = None
    overview: str | None = None
    first_aired: str | None = None
    last_aired: str | None = None
    airs: TraktAirs | None = None
    runtime: int | None = None
    total_runtime: int | None = None
    certification: str | None = None
    network: str | None = None
    country: str | None = None
    status: str | None = None
    rating: float | None = None
    votes: int | None = None
    comment_count: int | None = None
    trailer: str | None = None
    homepage: str | None = None
    updated_at: str | None = None
    language: str | None = None
    languages: list[str] | None = None
    available_translations: list[str] | None = None
    genres: list[str] | None = None
    subgenres: list[str] | None = None
    original_title: str | None = None
    aired_episodes: int | None = None
    images: TraktImages | None = None
    colors: TraktColors | None = None
    social_ids: TraktSocialIds | None = None


class TraktFavoriteShowEntry(BaseModel):
    id: int
    listed_at: str
    notes: str | None = None
    rank: int
    type: str
    show: TraktFavoriteShow


class TraktHistoryEntry(BaseModel):
    id: int
    watched_at: str
    action: str
    type: str
    episode: TraktEpisode
    show: TraktShow


class TraktMovieIds(BaseModel):
    imdb: str | None = None
    plex: TraktPlexIds | None = None
    slug: str | None = None
    tmdb: int | None = None
    trakt: int | None = None


class TraktMovie(BaseModel):
    ids: TraktMovieIds
    title: str
    year: int | None = None
    images: TraktImages | None = None
    overview: str | None = None
    genres: list[str] | None = None
    runtime: float | None = None
    status: str | None = None
    country: str | None = None
    trailer: str | None = None
    homepage: str | None = None
    certification: str | None = None
    tagline: str | None = None
    released: str | None = None


class TraktFavoriteMovie(BaseModel):
    ids: TraktMovieIds
    title: str
    year: int | None = None
    images: TraktImages | None = None
    tagline: str | None = None
    overview: str | None = None
    released: str | None = None
    runtime: int | None = None
    country: str | None = None
    status: str | None = None
    rating: float | None = None
    votes: int | None = None
    comment_count: int | None = None
    trailer: str | None = None
    homepage: str | None = None
    updated_at: str | None = None
    language: str | None = None
    languages: list[str] | None = None
    available_translations: list[str] | None = None
    genres: list[str] | None = None
    subgenres: list[str] | None = None
    certification: str | None = None
    original_title: str | None = None
    after_credits: bool | None = None
    during_credits: bool | None = None
    images: TraktImages | None = None
    colors: TraktColors | None = None
    social_ids: TraktSocialIds | None = None


class TraktFavoriteMovieEntry(BaseModel):
    id: int
    listed_at: str
    notes: str | None = None
    rank: int
    type: str
    movie: TraktFavoriteMovie


class TraktMovieHistoryEntry(BaseModel):
    id: int
    watched_at: str
    action: str
    type: str
    movie: TraktMovie


class TraktWatchlistMovie(BaseModel):
    type: str
    movie: TraktMovie
    rank: int
    id: int
    listed_at: str
    notes: str | None = None
    my_rating: int | None = None


class TraktWatchlistShow(BaseModel):
    type: str
    show: TraktShow
    rank: int
    id: int
    listed_at: str
    notes: str | None = None
    my_rating: int | None = None


class TraktWatchedShow(BaseModel):
    plays: int
    last_watched_at: str
    last_updated_at: str
    reset_at: str | None = None
    show: TraktShow


class TraktSearchResult(BaseModel):
    """Entry from the Trakt text search endpoint."""

    type: str
    score: float | None = None
    movie: TraktMovie | None = None
    show: TraktShow | None = None


class TraktTrendingMovie(BaseModel):
    """A movie entry from the Trakt trending endpoint."""

    watchers: int | None = None
    movie: TraktMovie


class TraktTrendingShow(BaseModel):
    """A show entry from the Trakt trending endpoint."""

    watchers: int | None = None
    show: TraktShow
