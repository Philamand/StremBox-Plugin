from http_client import get_session
from schemas.betaseries import (
    BetaSeriesSearchMovie,
    BetaSeriesSearchShow,
)


class BetaSeriesService:
    """Client for the BetaSeries API."""

    def __init__(self, api_key: str | None):
        self.base_url = "https://api.betaseries.com"
        self.api_key = api_key

    async def get_show_french_title(self, imdb_id) -> str | None:
        if self.api_key is None:
            return None

        url = f"{self.base_url}/shows/display"
        params = {"imdb_id": imdb_id, "summary": "true"}

        session = get_session()
        headers = {"X-BetaSeries-Key": self.api_key}
        async with session.get(url, params=params, headers=headers) as response:
            data = await response.json()
            return data.get("show", {}).get("title")

    async def get_tmdb_id(self, imdb_id: str, movie: bool = False) -> str | None:
        if self.api_key is None:
            return None

        if movie:
            url = f"{self.base_url}/movies/movie"
        else:
            url = f"{self.base_url}/shows/display"
        params = {"imdb_id": imdb_id, "summary": "true"}

        session = get_session()
        headers = {"X-BetaSeries-Key": self.api_key}
        async with session.get(url, params=params, headers=headers) as response:
            data = await response.json()
            if movie:
                return data.get("movie", {}).get("tmdb_id")
            return data.get("show", {}).get("themoviedb_id")


    async def _get_json(self, url: str, params: dict) -> dict | None:
        """Fetch a BetaSeries endpoint, returning None without an API key."""
        if self.api_key is None:
            return None
        session = get_session()
        headers = {"X-BetaSeries-Key": self.api_key}
        async with session.get(url, params=params, headers=headers) as response:
            return await response.json()

    async def search_movies(
        self, text: str, year: int | None = None, limit: int = 5
    ) -> list[BetaSeriesSearchMovie]:
        """Search movies by title, optionally filtering on release year.

        Args:
            text: Title to search for.
            year: Optional release year (``releases`` parameter).
            limit: Maximum number of results (``nbpp``).

        Returns:
            Matching movies; empty when no API key is configured.
        """
        url = f"{self.base_url}/search/movies"
        params = {"text": text, "nbpp": limit}
        if year:
            params["releases"] = year
        data = await self._get_json(url, params) or {}
        movies = data.get("movies") or []
        return [BetaSeriesSearchMovie.model_validate(m) for m in movies]

    async def search_shows(
        self, text: str, year: int | None = None, limit: int = 5
    ) -> list[BetaSeriesSearchShow]:
        """Search shows by title, optionally filtering on creation year.

        Args:
            text: Title to search for.
            year: Optional creation year (``creations`` parameter).
            limit: Maximum number of results (``nbpp``).

        Returns:
            Matching shows; empty when no API key is configured.
        """
        url = f"{self.base_url}/search/shows"
        params = {"text": text, "nbpp": limit}
        if year:
            params["creations"] = year
        data = await self._get_json(url, params) or {}
        shows = data.get("shows") or []
        return [BetaSeriesSearchShow.model_validate(s) for s in shows]

    async def get_movie_imdb_id(self, movie_id: int) -> str | None:
        """Return the IMDb id of a BetaSeries movie."""
        url = f"{self.base_url}/movies/movie"
        data = await self._get_json(url, {"id": movie_id}) or {}
        return (data.get("movie") or {}).get("imdb_id")

    async def get_show_imdb_id(self, show_id: int) -> str | None:
        """Return the IMDb id of a BetaSeries show."""
        url = f"{self.base_url}/shows/display"
        data = await self._get_json(url, {"id": show_id}) or {}
        return (data.get("show") or {}).get("imdb_id")
