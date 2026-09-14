from typing import Any

from http_client import get_session
from schemas.bauxite import DownloadRequest


class BauxiteService:
    """Service for interacting with Bauxite-related endpoints."""

    def __init__(self, base_url: str, bearer_token: str):
        self.base_url = base_url
        self.bearer_token = bearer_token

    async def get_torrent_hashes(self) -> dict[str, Any]:
        """Get a list of torrent hashes from the API."""
        session = get_session()
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        async with session.get(
            f"{self.base_url}/api/hashes/", headers=headers
        ) as response:
            return await response.json()

    async def download_torrent(self, request: DownloadRequest) -> None:
        """Start the download of a torrent using the provided request data."""
        session = get_session()
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        async with session.post(
            f"{self.base_url}/api/download/",
            headers=headers,
            json=request.model_dump(),
        ) as response:
            await response.json()

    async def add_torrent_download(self, torrent_url: str) -> None:
        """Add a torrent download to the queue."""
        session = get_session()
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        async with session.post(
            f"{self.base_url}/api/add/",
            headers=headers,
            params={"torrent_url": torrent_url},
        ) as response:
            await response.json()

    async def remove_torrent(self, torrent_hash: str) -> None:
        """Remove a torrent."""
        session = get_session()
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        async with session.post(
            f"{self.base_url}/api/remove/{torrent_hash}/",
            headers=headers,
        ) as response:
            print(await response.json())
