import os
from pathlib import Path

from dotenv import load_dotenv

# Load cwd .env first, then api/.env so `python -m pipeline.*` from the repo
# root still picks up the API package environment file.
load_dotenv()
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL_ENV = "DATABASE_URL"
FOOTBALL_DATA_API_KEY_ENV = "FOOTBALL_DATA_API_KEY"


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Export it or copy .env.example to .env."
        )
    return value


def get_database_url() -> str:
    """Return the database URL from the environment."""
    return _require_env(DATABASE_URL_ENV)


def get_football_data_api_key() -> str:
    """Return the football-data.org API token from the environment."""
    return _require_env(FOOTBALL_DATA_API_KEY_ENV)
