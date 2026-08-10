"""Settings, read from the environment (or a .env file in backend/).

Every variable is prefixed NHS_ so it can't collide with anything else on the
server. See .env.example at the repo root for the full list.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="NHS_", extra="ignore"
    )

    # Path to the SQLite file. In production this points at
    # /var/lib/nhs-web/calendar.db — never at a path inside the repo, or a
    # deploy would overwrite live data.
    db_path: str = "./calendar.db"

    # Both must be set for the admin endpoints to work at all; see auth.py.
    admin_password: str = ""
    secret_key: str = ""

    token_ttl_hours: int = 12

    # Only needed in development, when the static site is served from a
    # different port than the API. In production Caddy puts both on one origin.
    cors_origins: list[str] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
