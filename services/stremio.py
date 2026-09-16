import asyncio
import json
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import aiohttp
from aiohttp import ClientTimeout

from cache import cached_call
from http_client import get_session
from schemas.stremio import (
    StremioStreamData,
    StremioStreamsResponse,
)
from schemas.users import UserData
from services.bauxite import BauxiteService
from services.betaseries import BetaSeriesService
from utils.stremio import (
    check_season_episode,
    extract_download_params,
    parse_torrent_name,
    sort_dicts_by_seeders_desc,
)


def _strip_apikey(url: str | None) -> str | None:
    """Return *url* with its `apikey` query parameter removed.

    The apikey is the only user-specific value in tracker download links, so
    stripping it lets the same search results be cached and shared across users.
    """
    if not url:
        return url
    parsed = urlparse(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key != "apikey"
    ]
    return urlunparse(parsed._replace(query=urlencode(query)))


def _reinject_apikey(url: str | None, apikey: str) -> str | None:
    """Return *url* with *apikey* appended back to its query string."""
    if not url:
        return url
    parsed = urlparse(url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.append(("apikey", apikey))
    return urlunparse(parsed._replace(query=urlencode(query)))


class C411Service:
    """
    Client for the C411 torznab-style API.

    This class encapsulates contacting the C411 API and converting returned
    results into normalized Python dictionaries suitable for downstream code.

    Args:
        apikey: API key string to attach to requests. If falsy, searches will
                short-circuit and return an empty list.

    Example:
        svc = C411Service(apikey="...")    # constructed by dependency provider
        results = await svc.search_movie(title="Inception", year=2010)
    """

    apikey: str
    base_url: str

    def __init__(self, apikey: str) -> None:
        """
        Initialize the C411Service with an API key.

        Args:
            apikey (str): The API key required for C411 API authentication.
        """
        self.apikey = apikey
        self.base_url = "https://c411.org/api"

    async def search(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Perform a generic search against the C411 API and normalize the response.

        The method expects `params` to contain query parameters appropriate for
        the c411 API. The API key and JSON output format are automatically added.

        Behavior and error handling:
        - If the client was created without an API key, returns an empty list.
        - On non-200 responses or exceptions, logs details and returns an empty list.
        - Normalizes the XML->JSON response variations (single item -> list,
          torznab attributes as dict vs list).

        Args:
            params: Query parameters for the C411 API call.

        Returns:
            A list of normalized result dictionaries. Each dictionary contains
            keys such as "name", "size", "tracker_name", "info_hash", "magnet",
            "link", "source", "seeders", "leechers".
        """
        if not self.apikey:
            return []

        params["apikey"] = self.apikey
        params["o"] = "json"

        cache_key = "c411:search:" + json.dumps(
            {k: v for k, v in params.items() if k != "apikey"},
            sort_keys=True,
            default=str,
        )

        async def fetch() -> list[dict[str, Any]] | None:
            session = get_session()
            try:
                async with session.get(
                    self.base_url, params=params, timeout=ClientTimeout(total=20)
                ) as response:
                    if response.status != 200:
                        return None
                    data = await response.json()
                    channel = data.get("channel", {})
                    items = channel.get("item", [])

                    # Handle single item case (JSON conversion of XML sometimes makes single item an object instead of list)
                    if isinstance(items, dict):
                        items = [items]

                    normalized = []
                    for res in items:
                        # Extract torznab attributes
                        attrs = res.get("torznab:attr", [])
                        if isinstance(attrs, dict):
                            attrs = [attrs]

                        info_hash = None
                        seeders = 0
                        leechers = 0

                        for attr in attrs:
                            attr_data = attr.get("@attributes", {})
                            name = attr_data.get("name")
                            value = attr_data.get("value")

                            if name == "infohash":
                                info_hash = value
                            elif name == "seeders":
                                seeders = int(value) if value else 0
                                if leechers != 0:
                                    leechers -= seeders
                            elif name == "peers":
                                if seeders != 0 and value:
                                    leechers = int(value) - seeders
                                else:
                                    leechers = int(value) if value else 0

                        # Fallback hash to guid if infohash not found (guid is often hash in torznab)
                        if not info_hash:
                            info_hash = res.get("guid")

                        enclosure = res.get("enclosure", {}).get("@attributes", {})
                        download_link = enclosure.get("url")

                        item = {
                            "name": res.get("title"),
                            "size": int(res.get("size", 0)),
                            "tracker_name": "C411",
                            "info_hash": info_hash,
                            "magnet": None,
                            "link": _strip_apikey(download_link),
                            "source": "c411",
                            "seeders": seeders,
                            "leechers": leechers,
                        }
                        normalized.append(item)
                    return normalized or None
            except TimeoutError, aiohttp.ClientError, ValueError:
                return None

        cached = await cached_call(cache_key, 900, fetch, cache_none=False)
        results = cached or []
        for result in results:
            result["link"] = _reinject_apikey(result["link"], self.apikey)
        return results

    async def search_movie(
        self,
        title: str | None = None,
        year: int | None = None,
        imdb_id: str | None = None,
        tmdb_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for movies using title/year or external identifiers.

        The method prefers external identifiers when provided (IMDb or TMDB).
        If an IMDb id is supplied without the leading "tt" it will be prepended.

        Args:
            title: Optional movie title (used when no external id is provided).
            year: Optional release year.
            imdb_id: Optional IMDb id (with or without "tt" prefix).
            tmdb_id: Optional TMDB id.

        Returns:
            A list of normalized result dictionaries as returned by `search`.
        """
        params = {"t": "movie"}
        if imdb_id:
            if not str(imdb_id).startswith("tt"):
                imdb_id = f"tt{imdb_id}"
            params["imdbid"] = imdb_id
        elif tmdb_id:
            params["tmdbid"] = tmdb_id
        else:
            params["q"] = f"{title} {year}"

        return await self.search(params)

    async def search_series(
        self,
        title: str | None = None,
        season: int | None = None,
        episode: int | None = None,
        imdb_id: str | None = None,
        tmdb_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for TV series torrents (optionally constrained by season/episode).

        If `imdb_id` or `tmdb_id` is provided it will use those identifiers;
        otherwise it will use a text query (title) and optionally include season
        and episode filters where supported by the tracker.

        Args:
            title: Optional series title (used when no external id provided).
            season: Optional season number.
            episode: Optional episode number.
            imdb_id: Optional IMDb id (prepended with "tt" if necessary).
            tmdb_id: Optional TMDB id.

        Returns:
            A list of normalized result dictionaries as returned by `search`.
        """
        params = {"t": "tvsearch"}
        if imdb_id:
            if not str(imdb_id).startswith("tt"):
                imdb_id = f"tt{imdb_id}"
            params["imdbid"] = imdb_id
        elif tmdb_id:
            params["tmdbid"] = tmdb_id
        elif title:
            params["q"] = title

        # Torznab filters for season/episode if supported by tracker
        if season is not None:
            params["season"] = str(season)
        if episode is not None:
            params["episode"] = str(episode)

        return await self.search(params)


class Tr4kerService:
    def __init__(self, apikey):
        self.apikey = apikey
        self.base_url = "https://tr4ker.net/torznab"

    async def search(self, params):
        if not self.apikey:
            return []

        params["apikey"] = self.apikey

        cache_key = "tr4ker:search:" + json.dumps(
            {k: v for k, v in params.items() if k != "apikey"},
            sort_keys=True,
            default=str,
        )

        async def fetch() -> list[dict[str, Any]] | None:
            session = get_session()
            try:
                async with session.get(
                    self.base_url,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as response:
                    if response.status != 200:
                        return None
                    text = await response.text()
                    results = self._parse_xml(text)
                    for result in results:
                        result["link"] = _strip_apikey(result["link"])
                    return results or None
            except TimeoutError, aiohttp.ClientError:
                return None

        cached = await cached_call(cache_key, 900, fetch, cache_none=False)
        results = cached or []
        for result in results:
            result["link"] = _reinject_apikey(result["link"], self.apikey)
        return results

    def _parse_xml(self, xml_text):
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        ns = {"torznab": "http://torznab.com/schemas/2015/feed"}
        items = root.findall(".//item")

        results = []
        for item in items:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            enclosure = item.find("enclosure")
            download_link = enclosure.get("url", "") if enclosure is not None else link
            size = int(enclosure.get("length", 0)) if enclosure is not None else 0

            info_hash = None
            seeders = 0
            leechers = 0

            for attr in item.findall("torznab:attr", ns):
                name = attr.get("name")
                value = attr.get("value")
                if name == "infohash":
                    info_hash = value.lower() if value else None
                elif name == "seeders":
                    seeders = int(value) if value else 0
                elif name == "leechers":
                    leechers = int(value) if value else 0
                elif name == "size" and value:
                    size = int(value)

            results.append(
                {
                    "name": title,
                    "size": size,
                    "tracker_name": "Tr4ker",
                    "info_hash": info_hash,
                    "magnet": None,
                    "link": download_link,
                    "source": "tr4ker",
                    "seeders": seeders,
                    "leechers": leechers,
                }
            )

        return results

    async def search_movie(self, title=None, year=None, imdb_id=None, tmdb_id=None):
        if tmdb_id:
            return await self.search({"t": "movie", "tmdbid": tmdb_id})
        return await self.search({"t": "search", "q": f"{title} {year}".strip()})

    async def search_series(
        self, title=None, season=None, episode=None, imdb_id=None, tmdb_id=None
    ):
        if tmdb_id:
            params = {"t": "tvsearch", "tmdbid": tmdb_id}
            if season is not None:
                params["season"] = season
            if episode is not None:
                params["episode"] = episode
            results = await self.search(params)
        else:
            if season is not None and episode is not None:
                q = f"{title} S{int(season):02d}E{int(episode):02d}"
            elif season is not None:
                q = f"{title} S{int(season):02d}"
            else:
                q = title
            results = await self.search({"t": "search", "q": q})

        if season is not None:
            results = [
                r
                for r in results
                if check_season_episode(r.get("name", ""), season, episode)
            ]
        return results


class StremioOrchestrationService:
    """
    Orchestrates tracker searches, DB torrent upserts, and stream-link creation.

    This service is the single entry point for the Stremio stream endpoint.
    It delegates to the underlying tracker clients and DB-backed services, keeping
    all business logic out of the router.

    Args:
        c411_service: Configured C411 tracker client.
        tr4ker_service: Configured Tr4ker tracker client.
        torrent_service: DB-backed torrent service (get/create records).
        stream_service: Redis-backed stream link service.
    """

    def __init__(
        self,
        librebox_url: str,
        librebox_token: str,
        c411_service: C411Service | None = None,
        tr4ker_service: Tr4kerService | None = None,
    ) -> None:
        self.c411 = c411_service
        self.tr4ker = tr4ker_service
        self.librebox_url = librebox_url
        self.librebox_token = librebox_token

    async def search_movie(self, imdb_id: str) -> list[dict]:
        """Run parallel C411 + Tr4ker searches for a movie and return deduplicated results."""
        if self.tr4ker:
            betaseries_service = BetaSeriesService()
            tmdb_id = await betaseries_service.get_tmdb_id(imdb_id, movie=True)
        if self.c411 and self.tr4ker:
            c411_results, tr4ker_results = await asyncio.gather(
                self.c411.search_movie(imdb_id=imdb_id),
                self.tr4ker.search_movie(tmdb_id=tmdb_id),
            )
        elif self.c411:
            c411_results = await self.c411.search_movie(imdb_id=imdb_id)
            tr4ker_results = []
        elif self.tr4ker:
            tr4ker_results = await self.tr4ker.search_movie(tmdb_id=tmdb_id)
            c411_results = []
        else:
            return []
        results: list[dict] = c411_results + tr4ker_results
        return results

    async def search_serie(self, imdb_id: str, season: int, episode: int) -> list[dict]:
        """Run parallel C411 + Tr4ker searches for a series episode and return deduplicated results."""
        if self.tr4ker:
            betaseries_service = BetaSeriesService()
            tmdb_id = await betaseries_service.get_tmdb_id(imdb_id)
        if self.c411 and self.tr4ker:
            c411_results, tr4ker_results = await asyncio.gather(
                self.c411.search_series(
                    season=season, episode=episode, imdb_id=imdb_id
                ),
                self.tr4ker.search_series(
                    season=season, episode=episode, tmdb_id=tmdb_id
                ),
            )
        elif self.c411:
            c411_results = await self.c411.search_series(
                season=season, episode=episode, imdb_id=imdb_id
            )
            tr4ker_results = []
        elif self.tr4ker:
            tr4ker_results = await self.tr4ker.search_series(
                season=season, episode=episode, tmdb_id=tmdb_id
            )
            c411_results = []
        else:
            return []
        results: list[dict] = []
        for r in c411_results:
            if check_season_episode(r["name"], season, episode):
                results.append(r)
        for r in tr4ker_results:
            if check_season_episode(r["name"], season, episode):
                results.append(r)
        return results

    async def get_streams(
        self, type: str, id: str, user: UserData, auto_dl: bool = False
    ) -> StremioStreamsResponse:
        """Build a ``StremioStreamsResponse`` for *type*/*id* on behalf of *user*.

        Args:
            type: ``"movie"`` or ``"series"``.
            id: IMDb id for movies; ``"{imdbid}:{season}:{episode}"`` for series.
            user: Authenticated user (embedded in created stream links).

        Returns:
            A ``StremioStreamsResponse`` with fast (⚡️) streams first.
        """
        bauxite_service = BauxiteService(self.librebox_url, self.librebox_token)
        hashes = await bauxite_service.get_torrent_hashes()

        if type == "series":
            parts = id.split(":")
            imdb_id = parts[0]
            season = int(parts[1])
            episode = int(parts[2])
            results = await self.search_serie(imdb_id, season, episode)
        else:
            results = await self.search_movie(id)
            season = None
            episode = None

        if not results:
            return StremioStreamsResponse(streams=[])

        results = sort_dicts_by_seeders_desc(results)

        fast_streams: list[StremioStreamData] = []
        slow_streams: list[StremioStreamData] = []

        for result in results:
            details = parse_torrent_name(result["name"])

            if result["info_hash"] in hashes:
                torrent = hashes[result["info_hash"]]

                if torrent["percent_done"] < 1:
                    speed_emoji = "🐢 "
                else:
                    speed_emoji = "⚡️ "

                if len(torrent) == 1:
                    file_path = torrent["files"][0]
                else:
                    for filename in torrent["files"]:
                        if check_season_episode(filename, season, episode):
                            file_path = filename
                            break
                    if not file_path:
                        file_path = torrent["files"][0]
                stream_url = f"{self.librebox_url}/streams/{self.librebox_token}?file_path={file_path}"
            else:
                speed_emoji = ""
                stream_url = f"{self.librebox_url}/streams/download/{self.librebox_token}/{result['info_hash']}?torrent_url={result['link']}"
                if season and episode:
                    stream_url += f"&season={season}&episode={episode}"
                file_path = result["name"]

            stream = StremioStreamData(
                title=(
                    f"{speed_emoji}{result['name']}\n"
                    f"{details}\n"
                    f"📤 {result['seeders']}  📥 {result['leechers']} | {result['tracker_name']}\n"
                    f"💾 {result['size'] / 1024 / 1024 / 1024:.2f} GB"
                ),
                url=stream_url,
                filename=file_path,
                videoSize=int(result["size"]),
            )
            if speed_emoji == "⚡️ " or speed_emoji == "🐢 ":
                fast_streams.append(stream)
            else:
                slow_streams.append(stream)

        if auto_dl is True and len(fast_streams) == 0 and len(slow_streams) > 0:
            stream = StremioStreamData(
                title="⬇️ Téléchargement en cours...\nVous pouvez suivre la progression sur l'application ou vous pouvez rafraîchir la page dans quelques instants.",
                externalUrl=self.librebox_url,
                filename=file_path,
                videoSize=int(result["size"]),
            )
            download_request = extract_download_params(slow_streams[0].url)
            await bauxite_service.download_torrent(download_request)
            fast_streams.append(stream)
            slow_streams.clear()

        streams = fast_streams + slow_streams

        response = StremioStreamsResponse(streams=streams)

        return response
