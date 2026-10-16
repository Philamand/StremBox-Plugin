from datetime import UTC, datetime, timedelta

from cache import cached_call
from http_client import get_session
from schemas.trakt import (
    TraktEpisode,
    TraktFavoriteMovieEntry,
    TraktFavoriteShowEntry,
    TraktHistoryEntry,
    TraktMovie,
    TraktMovieHistoryEntry,
    TraktSearchResult,
    TraktSeason,
    TraktShow,
    TraktTrendingMovie,
    TraktTrendingShow,
    TraktWatchedShow,
    TraktWatchlistMovie,
    TraktWatchlistShow,
)


class TraktError(Exception):
    pass


class TraktService:
    def __init__(self, api_key: str | None):
        self.base_url = "https://api.trakt.tv"
        self.api_key = api_key

    def _get_headers(self) -> dict:
        if not self.api_key:
            raise TraktError("Missing Trakt API key")
        return {
            "accept": "application/json",
            "User-Agent": "readme/1.0",
            "trakt-api-version": "2",
            "trakt-api-key": self.api_key,
        }

    async def search_media(
        self,
        query: str,
        media_type: str,
        *,
        year: int | None = None,
        limit: int = 5,
    ) -> list[TraktSearchResult]:
        """Search Trakt for a movie or show by title.

        Args:
            query: Title to search for (``fields=title`` search).
            media_type: ``"movie"`` or ``"show"``.
            year: Optional release year used to prefer an exact match among
                the results (Trakt text search cannot filter on it).
            limit: Maximum number of results to request.

        Returns:
            Search results ordered by Trakt score; when *year* is given,
                results matching that year are ranked first.
        """
        url = f"{self.base_url}/search/{media_type}"
        params = {"query": query, "fields": "title", "limit": limit}

        session = get_session()
        async with session.get(
            url, params=params, headers=self._get_headers()
        ) as response:
            data = await response.json()
            results = [TraktSearchResult.model_validate(item) for item in data]

        if year is not None:
            media_key = media_type if media_type != "show" else "show"
            results.sort(
                key=lambda r: (getattr(r, media_key).year == year), reverse=True
            )

        return results

    async def get_movie_meta(self, imdb_id: str) -> TraktMovie | None:
        """Fetch the full metadata of a movie by its IMDb id.

        Uses the Trakt ID lookup (``/search/imdb/{id}``) with
        ``extended=full``; the result is cached in Redis for a day.
        """
        async def fetch() -> dict | None:
            url = f"{self.base_url}/search/imdb/{imdb_id}"
            params = {"type": "movie", "extended": "full"}

            session = get_session()
            async with session.get(
                url, params=params, headers=self._get_headers()
            ) as response:
                data = await response.json()
                for item in data:
                    if item.get("type") == "movie" and item.get("movie"):
                        return TraktMovie.model_validate(item["movie"]).model_dump()
                return None

        cached = await cached_call(
            f"trakt:meta:movie:{imdb_id}", 86400, fetch, cache_none=True
        )
        if cached is None:
            return None
        return TraktMovie.model_validate(cached)

    async def get_show_meta(self, imdb_id: str) -> TraktShow | None:
        """Fetch the full metadata of a show by its IMDb id.

        Uses the Trakt ID lookup (``/search/imdb/{id}``) with
        ``extended=full``; the result is cached in Redis for a day.
        """
        async def fetch() -> dict | None:
            url = f"{self.base_url}/search/imdb/{imdb_id}"
            params = {"type": "show", "extended": "full"}

            session = get_session()
            async with session.get(
                url, params=params, headers=self._get_headers()
            ) as response:
                data = await response.json()
                for item in data:
                    if item.get("type") == "show" and item.get("show"):
                        return TraktShow.model_validate(item["show"]).model_dump()
                return None

        cached = await cached_call(
            f"trakt:meta:show:{imdb_id}", 86400, fetch, cache_none=True
        )
        if cached is None:
            return None
        return TraktShow.model_validate(cached)

    async def get_trending_movies(self, limit: int = 40) -> list[TraktTrendingMovie]:
        """Get the trending movies on Trakt.

        The list is identical for every user, so it is cached in Redis for
        an hour regardless of the caller.

        Args:
            limit: Maximum number of movies to return.

        Returns:
            Trending movies ordered by watcher count.
        """
        async def fetch() -> list[dict]:
            url = f"{self.base_url}/movies/trending"
            params = {"limit": limit, "extended": "full"}

            session = get_session()
            async with session.get(
                url, params=params, headers=self._get_headers()
            ) as response:
                data = await response.json()
                return [
                    TraktTrendingMovie.model_validate(item).model_dump()
                    for item in data
                ]

        cached = await cached_call(
            "trakt:trending:movies", 3600, fetch, cache_none=True
        )
        return [TraktTrendingMovie.model_validate(item) for item in cached]

    async def get_trending_shows(self, limit: int = 40) -> list[TraktTrendingShow]:
        """Get the trending shows on Trakt.

        The list is identical for every user, so it is cached in Redis for
        an hour regardless of the caller.

        Args:
            limit: Maximum number of shows to return.

        Returns:
            Trending shows ordered by watcher count.
        """
        async def fetch() -> list[dict]:
            url = f"{self.base_url}/shows/trending"
            params = {"limit": limit, "extended": "full"}

            session = get_session()
            async with session.get(
                url, params=params, headers=self._get_headers()
            ) as response:
                data = await response.json()
                return [
                    TraktTrendingShow.model_validate(item).model_dump()
                    for item in data
                ]

        cached = await cached_call(
            "trakt:trending:shows", 3600, fetch, cache_none=True
        )
        return [TraktTrendingShow.model_validate(item) for item in cached]

    async def get_unwatched_movies(
        self, user_slug: str, *, extended: bool = False
    ) -> list[TraktWatchlistMovie]:
        """Get the movies in the user's watchlist.

        Args:
            user_slug: The user's Trakt slug.
            extended: When true, request ``extended=full`` so the
                entries include images and other full metadata.
        """
        url = f"{self.base_url}/users/{user_slug}/watchlist/movies/title/desc"
        params = {"hide": "unreleased"}
        if extended:
            params["extended"] = "full"

        session = get_session()
        async with session.get(
            url, params=params, headers=self._get_headers()
        ) as response:
            data = await response.json()
            return [TraktWatchlistMovie.model_validate(item) for item in data]

    async def get_unwatched_shows(
        self, user_slug: str, *, extended: bool = False
    ) -> list[TraktWatchlistShow]:
        """Get the shows in the user's watchlist.

        Args:
            user_slug: The user's Trakt slug.
            extended: When true, request ``extended=full`` so the
                entries include images and other full metadata.
        """
        url = f"{self.base_url}/users/{user_slug}/watchlist/shows/title/desc"
        params = {"hide": "unreleased"}
        if extended:
            params["extended"] = "full"

        session = get_session()
        async with session.get(
            url, params=params, headers=self._get_headers()
        ) as response:
            data = await response.json()
            return [TraktWatchlistShow.model_validate(item) for item in data]

    async def get_unfinished_shows(self, user_slug: str) -> list[TraktWatchedShow]:
        url = f"{self.base_url}/users/{user_slug}/watched/shows"
        params = {"hidden": "false", "specials": "false"}

        session = get_session()
        async with session.get(
            url, params=params, headers=self._get_headers()
        ) as response:
            data = await response.json()
            return [
                TraktWatchedShow.model_validate(item)
                for item in data
                if item["plays"] < item["show"]["aired_episodes"]
            ]

    async def get_all_seasons(self, show_id: str) -> list[TraktSeason]:
        async def fetch() -> list[dict]:
            url = f"{self.base_url}/shows/{show_id}/seasons"
            params = {"extended": "episodes"}

            session = get_session()
            async with session.get(
                url, params=params, headers=self._get_headers()
            ) as response:
                data = await response.json()
                return [
                    TraktSeason.model_validate(season).model_dump() for season in data
                ]

        cached = await cached_call(
            f"trakt:seasons:{show_id}", 86400, fetch, cache_none=True
        )
        return [TraktSeason.model_validate(season) for season in cached]

    async def get_all_episodes_season(self, id: str, season: int) -> list[TraktEpisode]:
        async def fetch() -> list[dict]:
            url = f"{self.base_url}/shows/{id}/seasons/{season}"

            session = get_session()
            async with session.get(url, headers=self._get_headers()) as response:
                data = await response.json()
                return [
                    TraktEpisode.model_validate(episode).model_dump()
                    for episode in data
                ]

        cached = await cached_call(
            f"trakt:episodes:{id}:{season}", 86400, fetch, cache_none=True
        )
        return [TraktEpisode.model_validate(episode) for episode in cached]

    async def get_show_history(
        self, user_slug: str, item_id: str
    ) -> list[TraktHistoryEntry]:
        url = f"{self.base_url}/users/{user_slug}/history/shows/{item_id}"

        session = get_session()
        async with session.get(url, headers=self._get_headers()) as response:
            data = await response.json()
            return [TraktHistoryEntry.model_validate(entry) for entry in data]

    async def get_favorite_movies(
        self, user_slug: str, sort: str = "rank", *, extended: bool = False
    ) -> list[TraktFavoriteMovieEntry]:
        """Get the user's favorite movies.

        Args:
            user_slug: The user's Trakt slug.
            sort: Order of the favorites.
            extended: When true, request ``extended=full`` so the
                entries include images and other full metadata.
        """
        url = f"{self.base_url}/users/{user_slug}/favorites/movies/{sort}"
        params = {}
        if extended:
            params["extended"] = "full"

        session = get_session()
        async with session.get(
            url, params=params, headers=self._get_headers()
        ) as response:
            data = await response.json()
            return [TraktFavoriteMovieEntry.model_validate(item) for item in data]

    async def get_favorite_shows(
        self, user_slug: str, sort: str = "rank", *, extended: bool = False
    ) -> list[TraktFavoriteShowEntry]:
        """Get the user's favorite shows.

        Args:
            user_slug: The user's Trakt slug.
            sort: Order of the favorites.
            extended: When true, request ``extended=full`` so the
                entries include images and other full metadata.
        """
        url = f"{self.base_url}/users/{user_slug}/favorites/shows/{sort}"
        params = {}
        if extended:
            params["extended"] = "full"

        session = get_session()
        async with session.get(
            url, params=params, headers=self._get_headers()
        ) as response:
            data = await response.json()
            return [TraktFavoriteShowEntry.model_validate(item) for item in data]

    async def get_movie_watched_history(
        self, user_slug: str
    ) -> list[TraktMovieHistoryEntry]:
        url = f"{self.base_url}/users/{user_slug}/history/movies"

        today = datetime.now(UTC).date()
        params = {
            "start_at": (today - timedelta(weeks=3)).strftime("%Y-%m-%d"),
            "end_at": (today - timedelta(weeks=2)).strftime("%Y-%m-%d"),
        }

        session = get_session()
        async with session.get(
            url, params=params, headers=self._get_headers()
        ) as response:
            data = await response.json()
            return [TraktMovieHistoryEntry.model_validate(entry) for entry in data]

    async def get_show_watched_history(self, user_slug: str) -> list[TraktHistoryEntry]:
        url = f"{self.base_url}/users/{user_slug}/history/shows"

        today = datetime.now(UTC).date()
        params = {
            "start_at": (today - timedelta(weeks=3)).strftime("%Y-%m-%d"),
            "end_at": (today - timedelta(weeks=2)).strftime("%Y-%m-%d"),
        }

        session = get_session()
        async with session.get(
            url, params=params, headers=self._get_headers()
        ) as response:
            data = await response.json()
            return [TraktHistoryEntry.model_validate(entry) for entry in data]

    async def get_next_episode(
        self, user_slug: str, show_id: str
    ) -> TraktEpisode | None:
        seasons = await self.get_all_seasons(show_id)
        history = await self.get_show_history(user_slug, show_id)

        all_episodes: list[TraktEpisode] = [
            episode
            for season in sorted(seasons, key=lambda s: s.number)
            if season.number != 0
            for episode in sorted(season.episodes, key=lambda e: e.number)
        ]

        if not all_episodes:
            return None

        if not history:
            return all_episodes[0]

        last_watched = max(
            history,
            key=lambda entry: (entry.episode.season, entry.episode.number),
        )
        last_season = last_watched.episode.season
        last_number = last_watched.episode.number

        for i, episode in enumerate(all_episodes):
            if episode.season == last_season and episode.number == last_number:
                if i + 1 < len(all_episodes):
                    return all_episodes[i + 1]
                return None

        for episode in all_episodes:
            if (episode.season, episode.number) > (last_season, last_number):
                return episode
        return None
