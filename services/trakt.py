import os
from datetime import UTC, datetime, timedelta

from http_client import get_session
from schemas.trakt import (
    TraktEpisode,
    TraktFavoriteMovieEntry,
    TraktFavoriteShowEntry,
    TraktHistoryEntry,
    TraktMovieHistoryEntry,
    TraktSeason,
    TraktWatchedShow,
    TraktWatchlistMovie,
    TraktWatchlistShow,
)


class TraktError(Exception):
    pass


class TraktService:
    def __init__(self):
        self.base_url = "https://api.trakt.tv"
        self.api_key = os.environ.get("TRAKT_API_KEY", None)
        self.access_token = os.environ.get("TRAKT_ACCESS_TOKEN", None)

    def _get_headers(self) -> dict:
        if not self.api_key or not self.access_token:
            raise TraktError("Missing Trakt API key or access token")
        return {
            "accept": "application/json",
            "User-Agent": "readme/1.0",
            "trakt-api-version": "2",
            "trakt-api-key": self.api_key,
            "authorization": f"Bearer {self.access_token}",
        }

    async def get_unwatched_movies(self, user_slug: str) -> list[TraktWatchlistMovie]:
        url = f"{self.base_url}/users/{user_slug}/watchlist/movies/title"
        params = {"hide": "unreleased"}

        session = get_session()
        async with session.get(
            url, params=params, headers=self._get_headers()
        ) as response:
            data = await response.json()
            return [TraktWatchlistMovie.model_validate(item) for item in data]

    async def get_unwatched_shows(self, user_slug: str) -> list[TraktWatchlistShow]:
        url = f"{self.base_url}/users/{user_slug}/watchlist/shows/title"
        params = {"hide": "unreleased"}

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
        url = f"{self.base_url}/shows/{show_id}/seasons"
        params = {"extended": "episodes"}

        session = get_session()
        async with session.get(
            url, params=params, headers=self._get_headers()
        ) as response:
            data = await response.json()
            return [TraktSeason.model_validate(season) for season in data]

    async def get_all_episodes_season(self, id: str, season: int) -> list[TraktEpisode]:
        url = f"{self.base_url}/shows/{id}/seasons/{season}"

        session = get_session()
        async with session.get(url, headers=self._get_headers()) as response:
            data = await response.json()
            return [TraktEpisode.model_validate(episode) for episode in data]

    async def get_show_history(
        self, user_slug: str, item_id: str
    ) -> list[TraktHistoryEntry]:
        url = f"{self.base_url}/users/{user_slug}/history/shows/{item_id}"

        session = get_session()
        async with session.get(url, headers=self._get_headers()) as response:
            data = await response.json()
            return [TraktHistoryEntry.model_validate(entry) for entry in data]

    async def get_favorite_movies(
        self, user_slug: str, sort: str = "rank"
    ) -> list[TraktFavoriteMovieEntry]:
        url = f"{self.base_url}/users/{user_slug}/favorites/movies/{sort}"

        session = get_session()
        async with session.get(url, headers=self._get_headers()) as response:
            data = await response.json()
            return [TraktFavoriteMovieEntry.model_validate(item) for item in data]

    async def get_favorite_shows(
        self, user_slug: str, sort: str = "rank"
    ) -> list[TraktFavoriteShowEntry]:
        url = f"{self.base_url}/users/{user_slug}/favorites/shows/{sort}"

        session = get_session()
        async with session.get(url, headers=self._get_headers()) as response:
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

        watched_ids = {
            entry.episode.ids.trakt
            for entry in history
            if entry.episode.ids.trakt is not None
        }

        for season in sorted(seasons, key=lambda s: s.number):
            if season.number == 0:
                continue
            for episode in sorted(season.episodes, key=lambda e: e.number):
                if episode.ids.trakt not in watched_ids:
                    return episode
        return None
