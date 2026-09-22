import os
from pathlib import Path

from dotenv import load_dotenv

# Load cwd .env first, then api/.env so `python -m pipeline.*` from the repo
# root still picks up the API package environment file.
load_dotenv()
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL_ENV = "DATABASE_URL"
FOOTBALL_DATA_API_KEY_ENV = "FOOTBALL_DATA_API_KEY"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
PSYCOPG3_SCHEME = "postgresql+psycopg://"


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Export it or copy .env.example to .env."
        )
    return value


def normalize_database_url(url: str) -> str:
    """Force SQLAlchemy to use psycopg v3 instead of the psycopg2 default.

    Cloud hosts (Railway, Heroku, etc.) often provide postgresql:// or the
    legacy postgres:// scheme with no driver. SQLAlchemy then loads psycopg2,
    which we do not install.
    """
    url = url.strip()
    if url.startswith(PSYCOPG3_SCHEME):
        return url
    if url.startswith("postgresql://"):
        return PSYCOPG3_SCHEME + url.removeprefix("postgresql://")
    if url.startswith("postgres://"):
        return PSYCOPG3_SCHEME + url.removeprefix("postgres://")
    return url


def get_database_url() -> str:
    """Return the database URL from the environment, with a psycopg v3 driver."""
    return normalize_database_url(_require_env(DATABASE_URL_ENV))


def get_football_data_api_key() -> str:
    """Return the football-data.org API token from the environment."""
    return _require_env(FOOTBALL_DATA_API_KEY_ENV)


def get_openai_api_key() -> str:
    """Return the OpenAI API key from the environment."""
    return _require_env(OPENAI_API_KEY_ENV)
