import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL_ENV = "DATABASE_URL"


def get_database_url() -> str:
    """Return the database URL from the environment."""
    url = os.getenv(DATABASE_URL_ENV)
    if not url:
        raise RuntimeError(
            f"{DATABASE_URL_ENV} is not set. "
            "Export it or copy .env.example to .env."
        )
    return url
