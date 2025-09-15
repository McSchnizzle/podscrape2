import os
from typing import Iterable, List, Optional
from urllib.parse import urlparse
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


def _strip_quotes(val: str) -> str:
    v = val.strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    # handle stray trailing quote
    if v.endswith('"') or v.endswith("'"):
        return v[:-1]
    return v


def _build_from_supabase_env() -> Optional[str]:
    """Attempt to construct a SQLAlchemy Postgres URL from SUPABASE_URL and SUPABASE_PASSWORD.

    SUPABASE_URL is typically https://<ref>.supabase.co, and the Postgres host is db.<ref>.supabase.co.
    Username defaults to 'postgres'.
    """
    supa_url = os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_DB_URL")
    supa_pw = os.getenv("SUPABASE_PASSWORD")
    if not supa_url or not supa_pw:
        return None
    try:
        supa_url = _strip_quotes(supa_url)
        # If user provided a full Postgres URL in SUPABASE_* directly, honor it
        if supa_url.startswith("postgres://") or supa_url.startswith("postgresql://") or supa_url.startswith("postgresql+psycopg://"):
            url = supa_url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            # Ensure sslmode=require
            if "sslmode=" not in url:
                sep = "&" if "?" in url else "?"
                url = f"{url}{sep}sslmode=require"
            return url

        parsed = urlparse(supa_url)
        host = parsed.hostname or supa_url.replace("https://", "").replace("http://", "")
        if not host.endswith(".supabase.co"):
            # Unrecognized; bail
            return None
        # Compose DB host if needed
        db_host = host if host.startswith("db.") else f"db.{host}"
        return f"postgresql+psycopg://postgres:{supa_pw}@{db_host}:5432/postgres?sslmode=require"
    except Exception:
        return None


def require_database_url() -> str:
    """Resolve DATABASE_URL, allowing Supabase env fallbacks, else raise.

    Priority:
      1) DATABASE_URL
      2) SUPABASE_DB_URL (if provided)
      3) Construct from SUPABASE_URL + SUPABASE_PASSWORD
    """
    load_dotenv()  # Ensure .env is loaded
    url = os.getenv("DATABASE_URL")
    if not url:
        url = os.getenv("SUPABASE_DB_URL")
    if not url:
        url = _build_from_supabase_env()
        if url:
            os.environ["DATABASE_URL"] = url  # normalize for the rest of the app
    if not url:
        raise MissingEnvError(
            "DATABASE_URL is required. Set DATABASE_URL directly or provide SUPABASE_URL and SUPABASE_PASSWORD in .env."
        )
    return url
