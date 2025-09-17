Summary

Added an isolated pytest module that exercises require_env and require_database_url so we can validate environment-variable fallbacks without needing optional infrastructure dependencies.

Testing

⚠️ pytest (fails: missing SQLAlchemy dependency; installing blocked by network proxy).

✅ pytest env_tests

⚠️ python scripts/doctor.py (environment doctor reports missing secrets, dependencies, and CLI tools).

Findings

Package installation is currently blocked by the proxy, so key dependencies such as SQLAlchemy and openai-whisper cannot be fetched, leaving the runtime without required modules.

The environment doctor confirms that required secrets (OpenAI, ElevenLabs, GitHub token/repository, database URL) are unset, causing the database connectivity check to fail immediately.

Several external tools (ffmpeg, gh, pg_dump) and Python libraries (sqlalchemy, psycopg, feedparser) are missing from the PATH/Python environment, which will block audio processing, publishing, and database workflows.

Top 3 focus areas to fix

Supply real environment variables for API keys and DATABASE_URL (or a Supabase fallback) so configuration checks and DB connections can succeed.

Restore access to Python dependencies—particularly SQLAlchemy, psycopg, and feedparser—either by enabling pip downloads through the proxy or by pre-installing the wheels, so the core test suite can import project modules.

Install required external CLI tools (ffmpeg, GitHub CLI, pg_dump) so the media pipeline and publishing scripts can operate end-to-end during testing.