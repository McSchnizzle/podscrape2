import os
from typing import Iterable, List, Optional
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
    _DOTENV_AVAILABLE = True
except ImportError:
    _DOTENV_AVAILABLE = False

    def load_dotenv() -> None:
        """No-op when dotenv is not available (e.g., in CI environments)."""
        pass


def load_env() -> None:
    """Load environment variables from .env if present."""
    if _DOTENV_AVAILABLE:
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

    Raises MissingEnvError with detailed diagnostics if configuration is invalid.
    """
    supa_url = os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_DB_URL")
    supa_pw = os.getenv("SUPABASE_PASSWORD")

    # FAIL FAST: If attempting Supabase connection, all variables must be present
    if supa_url and not supa_pw:
        raise MissingEnvError(
            "SUPABASE_PASSWORD is required when SUPABASE_URL is provided. "
            "Check your .env file for missing SUPABASE_PASSWORD variable."
        )
    if supa_pw and not supa_url:
        raise MissingEnvError(
            "SUPABASE_URL is required when SUPABASE_PASSWORD is provided. "
            "Check your .env file for missing SUPABASE_URL variable."
        )

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

        # Validate SUPABASE_URL format
        if not supa_url.startswith(("https://", "http://")):
            raise MissingEnvError(
                f"SUPABASE_URL must start with 'https://' or 'http://', got: '{supa_url}'. "
                "Expected format: https://your-project.supabase.co"
            )

        parsed = urlparse(supa_url)
        host = parsed.hostname or supa_url.replace("https://", "").replace("http://", "")

        if not host.endswith(".supabase.co"):
            raise MissingEnvError(
                f"SUPABASE_URL must be a valid Supabase URL ending with '.supabase.co', got: '{supa_url}'. "
                "Expected format: https://your-project.supabase.co"
            )

        # Compose DB host if needed
        db_host = host if host.startswith("db.") else f"db.{host}"
        return f"postgresql+psycopg://postgres:{supa_pw}@{db_host}:5432/postgres?sslmode=require"

    except MissingEnvError:
        # Re-raise our own validation errors
        raise
    except Exception as e:
        raise MissingEnvError(
            f"Failed to parse SUPABASE_URL '{supa_url}': {str(e)}. "
            "Ensure SUPABASE_URL is a valid URL in format: https://your-project.supabase.co"
        )


def require_database_url() -> str:
    """Resolve DATABASE_URL, allowing Supabase env fallbacks, else raise.

    Priority:
      1) DATABASE_URL (direct PostgreSQL connection string)
      2) SUPABASE_DB_URL (direct Supabase connection string)
      3) Construct from SUPABASE_URL + SUPABASE_PASSWORD

    FAIL FAST: Provides detailed error messages about which configuration option to use.
    """
    load_env()  # Ensure .env is loaded (if dotenv available)

    # Try direct DATABASE_URL first
    url = os.getenv("DATABASE_URL")
    if url:
        # Validate DATABASE_URL format (allow SQLite for testing)
        if not url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://", "sqlite://")):
            raise MissingEnvError(
                f"DATABASE_URL must be a valid PostgreSQL or SQLite connection string starting with "
                f"'postgres://', 'postgresql://', 'postgresql+psycopg://', or 'sqlite://'. Got: {url[:50]}..."
            )
        return url

    # Try SUPABASE_DB_URL as fallback
    url = os.getenv("SUPABASE_DB_URL")
    if url:
        # Validate SUPABASE_DB_URL format (should be PostgreSQL for Supabase)
        if not url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
            raise MissingEnvError(
                f"SUPABASE_DB_URL must be a valid PostgreSQL connection string starting with "
                f"'postgres://', 'postgresql://', or 'postgresql+psycopg://'. Got: {url[:50]}..."
            )
        return url

    # Try building from Supabase components
    try:
        url = _build_from_supabase_env()
        if url:
            os.environ["DATABASE_URL"] = url  # normalize for the rest of the app
            return url
    except MissingEnvError:
        # Re-raise validation errors from _build_from_supabase_env
        raise

    # No valid database configuration found
    supa_url = os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_DB_URL")
    supa_pw = os.getenv("SUPABASE_PASSWORD")

    error_msg = (
        "No valid database configuration found. Choose ONE of these options:\n\n"
        "Option 1 - Direct PostgreSQL URL:\n"
        "  Set DATABASE_URL=postgresql+psycopg://user:password@host:5432/database\n\n"
        "Option 2 - Supabase connection string:\n"
        "  Set SUPABASE_DB_URL=postgresql+psycopg://postgres:password@db.xxx.supabase.co:5432/postgres\n\n"
        "Option 3 - Supabase components:\n"
        "  Set SUPABASE_URL=https://your-project.supabase.co\n"
        "  Set SUPABASE_PASSWORD=your_database_password\n\n"
        "Option 4 - SQLite (for testing only):\n"
        "  Set DATABASE_URL=sqlite:///path/to/database.db\n\n"
    )

    if supa_url and not supa_pw:
        error_msg += "Found SUPABASE_URL but missing SUPABASE_PASSWORD."
    elif supa_pw and not supa_url:
        error_msg += "Found SUPABASE_PASSWORD but missing SUPABASE_URL."
    else:
        error_msg += "No database environment variables found in .env file."

    raise MissingEnvError(error_msg)


def validate_critical_environment() -> None:
    """Validate critical environment variables and fail fast if any are missing.

    FAIL FAST PRINCIPLE: This function will raise MissingEnvError immediately
    if any critical environment variables are missing. NO FALLBACKS.

    Use this function at the start of any script that requires environment configuration.
    """
    load_env()  # Ensure .env is loaded (if dotenv available)

    # Critical environment variables - NO FALLBACKS, NO SILENT FAILURES
    critical_vars = [
        'OPENAI_API_KEY',
        'ELEVENLABS_API_KEY',
        'GITHUB_TOKEN',
        'GITHUB_REPOSITORY'
    ]

    # Check all critical variables
    require_env(critical_vars)

    # Check database connectivity
    require_database_url()

    # Validate GitHub repository format
    github_repo = os.getenv('GITHUB_REPOSITORY', '')
    if '/' not in github_repo or github_repo.count('/') != 1:
        raise MissingEnvError(
            f"GITHUB_REPOSITORY must be in format 'owner/repo', got: '{github_repo}'"
        )
