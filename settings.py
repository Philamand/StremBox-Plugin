from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Process-level configuration shared by the app and the cron jobs.

    Field values are read from the environment (case-insensitive), e.g.
    ``TRAKT_API_KEY`` for ``trakt_api_key``. Services themselves receive
    everything via their constructors.
    """

    trakt_api_key: str | None = None
    trakt_access_token: str | None = None
    betaseries_api_key: str | None = None


def get_settings() -> Settings:
    """Build the application settings from the environment."""
    return Settings()
