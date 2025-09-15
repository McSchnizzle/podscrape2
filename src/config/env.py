import os
from typing import Iterable, List
from dotenv import load_dotenv


def load_env() -> None:
    """Load environment variables from .env if present."""
    load_dotenv()


class MissingEnvError(RuntimeError):
    pass


def require_env(keys: Iterable[str]) -> None:
    """Ensure all keys are present and non-empty, else raise MissingEnvError."""
    missing: List[str] = []
    for k in keys:
        v = os.getenv(k)
        if not v:
            missing.append(k)
    if missing:
        raise MissingEnvError(f"Missing required environment variables: {missing}")


def require_database_url() -> str:
    """Return DATABASE_URL, or raise if unset (no local SQLite fallback)."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise MissingEnvError(
            "DATABASE_URL is required but unset. Configure Supabase Postgres in .env."
        )
    return url

