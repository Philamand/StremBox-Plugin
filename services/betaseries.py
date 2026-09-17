from http_client import get_session


class BetaSeriesService:
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
