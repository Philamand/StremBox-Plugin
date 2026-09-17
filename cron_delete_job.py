import asyncio
import os

import asyncpg

from cache import close_cache_client, init_cache_client
from http_client import close_http_session, init_http_session
from services.bauxite import BauxiteService
from services.betaseries import BetaSeriesService
from services.stremio import C411Service, StremioOrchestrationService, Tr4kerService
from services.trakt import TraktService
from services.users import UserService
from settings import get_settings
from utils.stremio import check_season_episode

DATABASE_URL = os.getenv("DATABASE_URL")


async def main():
    settings = get_settings()
    await init_http_session()
    await init_cache_client()

    pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=1,
        max_size=5,
    )

    try:
        async with pool.acquire() as conn:
            user_service = UserService(conn)
            users = await user_service.get_all_users(filter_without_trakt_slug=True)
            trakt_service = TraktService(
                api_key=settings.trakt_api_key,
                access_token=settings.trakt_access_token,
            )
            betaseries_service = BetaSeriesService(api_key=settings.betaseries_api_key)

            for user in users:
                bauxite_service = BauxiteService(user.librebox_url, user.librebox_token)
                hashes = await bauxite_service.get_torrent_hashes()

                if user.trakt_slug:
                    if user.c411_key:
                        c411_service = C411Service(user.c411_key)
                    else:
                        c411_service = None

                    if user.tr4ker_key:
                        tr4ker_service = Tr4kerService(user.tr4ker_key)
                    else:
                        tr4ker_service = None

                    stremio_service = StremioOrchestrationService(
                        user.librebox_url,
                        user.librebox_token,
                        c411_service=c411_service,
                        tr4ker_service=tr4ker_service,
                        betaseries_service=betaseries_service,
                    )

                    movies = await trakt_service.get_movie_watched_history(
                        user.trakt_slug
                    )
                    favorite_movies = await trakt_service.get_favorite_movies(
                        user.trakt_slug
                    )
                    favorite_movies_id = {
                        fav.movie.ids.imdb
                        for fav in favorite_movies
                        if fav.movie.ids.imdb is not None
                    }

                    for movie in movies:
                        if (
                            movie.movie.ids.imdb is None
                            or movie.movie.ids.imdb in favorite_movies_id
                        ):
                            continue

                        results = await stremio_service.search_movie(
                            movie.movie.ids.imdb
                        )

                        for result in results:
                            if result["info_hash"] in hashes:
                                await bauxite_service.remove_torrent(
                                    result["info_hash"]
                                )

                    shows = await trakt_service.get_show_watched_history(
                        user.trakt_slug
                    )
                    favorite_shows = await trakt_service.get_favorite_shows(
                        user.trakt_slug
                    )
                    favorite_shows_ids = [
                        show.show.ids.imdb
                        for show in favorite_shows
                        if show.show.ids.imdb is not None
                    ]

                    for show in shows:
                        if (
                            show.show.ids.imdb is None
                            or show.show.ids.slug is None
                            or show.show.ids.imdb in favorite_shows_ids
                        ):
                            continue

                        next_episode = await trakt_service.get_next_episode(
                            user.trakt_slug, show.show.ids.slug
                        )
                        if next_episode is None:
                            continue

                        results = await stremio_service.search_serie(
                            show.show.ids.imdb, show.episode.season, show.episode.number
                        )

                        for result in results:
                            if result[
                                "info_hash"
                            ] in hashes and not check_season_episode(
                                result["name"], next_episode.season, next_episode.number
                            ):
                                await bauxite_service.remove_torrent(
                                    result["info_hash"]
                                )

    finally:
        await pool.close()
        await close_cache_client()
        await close_http_session()


if __name__ == "__main__":
    asyncio.run(main())
