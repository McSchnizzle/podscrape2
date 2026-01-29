#!/usr/bin/env python3
"""
Environment and data layout validation script for podscrape2.
Validates DATABASE_URL connectivity, data directory structure, and required environment variables.
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple

# Add project root to path for imports (src.config.env etc.)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.environ['PYTHONPATH'] = str(project_root)


def check_environment_variables() -> List[Tuple[str, bool, str]]:
    """Check required environment variables are present.

    FAIL FAST PRINCIPLE: No fallbacks, no silent failures.
    Missing environment variables are critical errors that must be fixed immediately.
    """
    from src.config.env import load_env
    load_env()  # Load .env file

    checks = []

    # Required API keys - NO FALLBACKS, NO SILENT FAILURES
    required_vars = [
        ('OPENAI_API_KEY', 'OpenAI API key for content scoring and script generation'),
        ('ELEVENLABS_API_KEY', 'ElevenLabs API key for TTS audio generation'),
        ('GITHUB_TOKEN', 'GitHub token for publishing releases'),
        ('GITHUB_REPOSITORY', 'GitHub repository in format OWNER/REPO'),
    ]

    for var_name, description in required_vars:
        value = os.getenv(var_name)
        if value and not value.startswith('test-') and value != 'your-key-here' and len(value.strip()) > 0:
            checks.append((f"✅ {var_name}", True, description))
        else:
            checks.append((f"❌ {var_name} [CRITICAL]", False, f"MISSING REQUIRED ENV VAR: {description}"))

    return checks



def check_ci_workflow_secrets() -> List[Tuple[str, bool, str]]:
    """Report presence of secrets required by CI bootstrap and Phase 4 workflows."""
    from src.config.env import load_env

    load_env()

    checks: List[Tuple[str, bool, str]] = []

    database_url = os.getenv("DATABASE_URL")
    supabase_db_url = os.getenv("SUPABASE_DB_URL")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_pw = os.getenv("SUPABASE_PASSWORD")

    if database_url:
        checks.append(("✅ DATABASE_URL (CI)", True, "Postgres connection provided via DATABASE_URL"))
    elif supabase_db_url:
        checks.append(("✅ SUPABASE_DB_URL (CI)", True, "Supabase direct Postgres URL supplied via SUPABASE_DB_URL"))
    elif supabase_url and supabase_pw:
        checks.append(("✅ SUPABASE_URL + SUPABASE_PASSWORD (CI)", True, "Supabase URL/password pair present for CI bootstrap"))
    else:
        detail = (
            "Provide DATABASE_URL, SUPABASE_DB_URL, or SUPABASE_URL + SUPABASE_PASSWORD so CI bootstrap "
            "can reach the database"
        )
        checks.append(("⚠️  DATABASE_URL/SUPABASE_* (CI)", False, detail))

    github_token_var = next((name for name in ("GH_TOKEN", "GITHUB_TOKEN") if os.getenv(name)), None)
    if github_token_var:
        checks.append((f"✅ {github_token_var} (CI)", True, "GitHub token with workflow scope available"))
    else:
        checks.append((
            "⚠️  GH_TOKEN/GITHUB_TOKEN (CI)",
            False,
            "Provide a GitHub token with workflow scope for CI bootstrap checks",
        ))

    repo_value = os.getenv("GH_REPOSITORY") or os.getenv("GITHUB_REPOSITORY")
    if repo_value:
        checks.append(("✅ GH_REPOSITORY/GITHUB_REPOSITORY (CI)", True, "Repository target configured for API calls"))
    else:
        checks.append((
            "⚠️  GH_REPOSITORY/GITHUB_REPOSITORY (CI)",
            False,
            "Set GH_REPOSITORY or rely on default GITHUB_REPOSITORY in CI",
        ))

    for var, description in (
        ("WEBUI_DISPATCH_PAT", "Fine-grained PAT for triggering workflows from the Web UI"),
        ("VERCEL_TOKEN", "Vercel access token for deployments"),
        ("VERCEL_ORG_ID", "Vercel organisation ID"),
        ("VERCEL_PROJECT_ID", "Vercel project ID"),
    ):
        value = os.getenv(var)
        if value:
            checks.append((f"✅ {var} (CI)", True, description))
        else:
            checks.append((
                f"⚠️  {var} (CI)",
                False,
                f"{description} - configure in GitHub secrets when enabling CI dispatch",
            ))

    return checks

def check_database_connectivity() -> Tuple[str, bool, str]:
    """Test DATABASE_URL connectivity to Supabase."""
    try:
        from src.config.env import load_env, require_database_url
        load_env()

        database_url = require_database_url()

        # Test SQLAlchemy connection
        from sqlalchemy import create_engine, text
        engine = create_engine(database_url)

        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            test_val = result.scalar()

        if test_val == 1:
            return ("✅ DATABASE_URL connectivity", True, f"Successfully connected to Supabase Postgres")
        else:
            return ("❌ DATABASE_URL connectivity", False, "Connection test query failed")

    except ImportError as e:
        return ("❌ DATABASE_URL connectivity", False, f"Missing dependency: {e}")
    except Exception as e:
        return ("❌ DATABASE_URL connectivity", False, f"Connection failed: {e}")


def check_data_directory_structure() -> List[Tuple[str, bool, str]]:
    """Validate data directory structure exists and is writable."""
    checks = []

    # Expected data directory structure
    data_paths = [
        ('data/', 'Main data directory'),
        ('data/database/', 'Database files'),
        ('data/transcripts/', 'Transcript files'),
        ('data/scripts/', 'Generated script files'),
        ('data/completed-tts/', 'Generated MP3 files'),
        ('data/logs/', 'Pipeline execution logs'),
        ('data/rss/', 'Generated RSS feeds'),
        ('public/', 'Public RSS feed for Vercel deployment'),
    ]

    for path_str, description in data_paths:
        path = Path(path_str)

        # Check if directory exists
        if path.exists():
            if path.is_dir():
                # Check if writable
                try:
                    test_file = path / '.write_test'
                    test_file.write_text('test')
                    test_file.unlink()
                    checks.append((f"✅ {path_str}", True, f"{description} - exists and writable"))
                except PermissionError:
                    checks.append((f"⚠️  {path_str}", False, f"{description} - exists but not writable"))
                except Exception as e:
                    checks.append((f"⚠️  {path_str}", False, f"{description} - write test failed: {e}"))
            else:
                checks.append((f"❌ {path_str}", False, f"{description} - exists but is not a directory"))
        else:
            # Try to create directory
            try:
                path.mkdir(parents=True, exist_ok=True)
                checks.append((f"✅ {path_str}", True, f"{description} - created successfully"))
            except PermissionError:
                checks.append((f"❌ {path_str}", False, f"{description} - cannot create (permission denied)"))
            except Exception as e:
                checks.append((f"❌ {path_str}", False, f"{description} - cannot create: {e}"))

    return checks


def check_pg_dump_with_paths() -> Tuple[str, bool, str]:
    """
    Check pg_dump availability with fallback to common installation paths.
    Provides platform-specific installation guidance if not found.
    """
    import subprocess
    import platform
    import os
    from pathlib import Path

    # Common pg_dump installation paths by platform
    common_paths = {
        'Darwin': [  # macOS
            '/opt/homebrew/opt/libpq/bin/pg_dump',  # Homebrew libpq (M1 Mac)
            '/usr/local/opt/libpq/bin/pg_dump',     # Homebrew libpq (Intel Mac)
            '/opt/homebrew/bin/pg_dump',            # Homebrew postgresql
            '/usr/local/bin/pg_dump',               # Homebrew postgresql (Intel)
            '/Applications/Postgres.app/Contents/Versions/latest/bin/pg_dump',  # Postgres.app
        ],
        'Linux': [
            '/usr/bin/pg_dump',                     # Standard package manager
            '/usr/local/bin/pg_dump',               # Manual installation
            '/usr/local/pgsql/bin/pg_dump',         # PostgreSQL source install
        ],
        'Windows': [
            'C:\\Program Files\\PostgreSQL\\*\\bin\\pg_dump.exe',
            'C:\\PostgreSQL\\*\\bin\\pg_dump.exe',
        ]
    }

    # First try standard PATH
    try:
        result = subprocess.run(['pg_dump', '--version'],
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            return (f"✅ pg_dump", True, f"PostgreSQL client for database backups - {version_line[:50]}")
    except FileNotFoundError:
        pass
    except Exception:
        pass

    # Try platform-specific paths
    current_platform = platform.system()
    if current_platform in common_paths:
        for pg_dump_path in common_paths[current_platform]:
            try:
                if Path(pg_dump_path).exists():
                    result = subprocess.run([pg_dump_path, '--version'],
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        version_line = result.stdout.split('\n')[0]
                        path_info = f"Found at {pg_dump_path}"
                        return (f"⚠️  pg_dump", True, f"PostgreSQL client - {version_line[:30]} - {path_info}")
            except Exception:
                continue

    # Generate platform-specific installation instructions
    install_instructions = {
        'Darwin': "Install: brew install libpq && export PATH=\"/opt/homebrew/opt/libpq/bin:$PATH\"",
        'Linux': "Install: sudo apt-get install postgresql-client (Debian/Ubuntu) or sudo yum install postgresql (RHEL/CentOS)",
        'Windows': "Install: Download PostgreSQL from https://www.postgresql.org/download/windows/"
    }

    instruction = install_instructions.get(current_platform, "Install PostgreSQL client tools for your platform")
    return (f"❌ pg_dump", False, f"PostgreSQL client for database backups - not found. {instruction}")


def check_github_repo_visibility() -> Tuple[str, bool, str]:
    """Check that the GitHub repository is public.

    CRITICAL: The repository MUST be public for podcast RSS feeds to work.
    Podcatcher apps download MP3 files from GitHub releases without authentication.
    If the repo is private, downloads will return 404 errors.
    """
    import subprocess
    from src.config.env import load_env
    load_env()

    repo = os.getenv('GITHUB_REPOSITORY')
    if not repo:
        return ("⚠️  GitHub repo visibility", False, "GITHUB_REPOSITORY not set - cannot check visibility")

    try:
        result = subprocess.run(
            ['gh', 'repo', 'view', repo, '--json', 'visibility,isPrivate'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return ("⚠️  GitHub repo visibility", False, f"Could not check repo: {result.stderr[:100]}")

        import json
        data = json.loads(result.stdout)
        is_private = data.get('isPrivate', True)
        visibility = data.get('visibility', 'unknown')

        if is_private:
            return (
                "❌ GitHub repo visibility [CRITICAL]",
                False,
                f"Repository {repo} is PRIVATE - MP3 downloads will fail with 404. "
                f"Run: gh repo edit {repo} --visibility public --accept-visibility-change-consequences"
            )
        else:
            return ("✅ GitHub repo visibility", True, f"Repository {repo} is {visibility} - downloads will work")

    except FileNotFoundError:
        return ("⚠️  GitHub repo visibility", False, "gh CLI not found - cannot check repo visibility")
    except json.JSONDecodeError:
        return ("⚠️  GitHub repo visibility", False, "Could not parse gh output")
    except Exception as e:
        return ("⚠️  GitHub repo visibility", False, f"Error checking repo: {e}")


def check_external_tools() -> List[Tuple[str, bool, str]]:
    """Check availability of external tools."""
    checks = []

    # Handle pg_dump specially with path detection
    checks.append(check_pg_dump_with_paths())

    # Handle other tools normally
    tools = [
        ('ffmpeg', 'Required for audio chunking and format conversion', '-version'),  # ffmpeg uses single dash
        ('gh', 'GitHub CLI for publishing (optional if GITHUB_TOKEN is available)', '--version'),
    ]

    for tool_info in tools:
        tool = tool_info[0]
        description = tool_info[1]
        version_flag = tool_info[2] if len(tool_info) > 2 else '--version'

        try:
            import subprocess
            result = subprocess.run([tool, version_flag],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0] if result.stdout else result.stderr.split('\n')[0]
                checks.append((f"✅ {tool}", True, f"{description} - {version_line[:50]}"))
            else:
                # Show actual exit code and stderr to help diagnose the issue
                stderr_snippet = result.stderr[:100] if result.stderr else "no error output"
                checks.append((f"❌ {tool}", False, f"{description} - exit code {result.returncode}: {stderr_snippet}"))
        except FileNotFoundError:
            checks.append((f"❌ {tool}", False, f"{description} - not found in PATH"))
        except subprocess.TimeoutExpired:
            checks.append((f"⚠️  {tool}", False, f"{description} - command timeout"))
        except Exception as e:
            checks.append((f"⚠️  {tool}", False, f"{description} - error: {e}"))

    return checks


def check_python_dependencies() -> List[Tuple[str, bool, str]]:
    """Check availability of key Python dependencies."""
    checks = []

    dependencies = [
        ('sqlalchemy', 'Database ORM'),
        ('psycopg', 'PostgreSQL driver'),
        ('openai', 'OpenAI API client'),
        ('elevenlabs', 'ElevenLabs TTS client'),
        ('feedparser', 'RSS feed parsing'),
        ('flask', 'Web UI framework'),
        ('parakeet_mlx', 'Apple Silicon transcription (optional)'),
    ]

    for module, description in dependencies:
        try:
            __import__(module)
            checks.append((f"✅ {module}", True, f"{description} - available"))
        except ImportError:
            if module == 'parakeet_mlx':
                checks.append((f"⚠️  {module}", True, f"{description} - optional, not installed"))
            else:
                checks.append((f"❌ {module}", False, f"{description} - missing"))

    return checks


def main():
    """Run all validation checks and display results.

    FAIL FAST PRINCIPLE: Exit immediately if critical environment issues are found.
    """
    print("🏥 Podscrape2 Environment Doctor")
    print("=" * 50)
    print("FAIL FAST MODE: Critical environment issues will cause immediate failure")

    all_checks = []
    critical_failures = []
    running_in_ci = (os.getenv("CI", "").lower() == "true") or (os.getenv("GITHUB_ACTIONS") == "true")

    # Run all checks
    print("\n📋 Environment Variables")
    env_checks = check_environment_variables()
    all_checks.extend(env_checks)
    for check_name, passed, description in env_checks:
        print(f"  {check_name}")
        if not passed:
            print(f"    → {description}")
            if "[CRITICAL]" in check_name:
                critical_failures.append((check_name, description))

    print("\n🚀 CI/CD Secrets for GitHub Actions")
    ci_checks = check_ci_workflow_secrets()
    all_checks.extend(ci_checks)
    for check_name, passed, description in ci_checks:
        print(f"  {check_name}")
        if not passed:
            print(f"    → {description}")
            if running_in_ci:
                critical_failures.append((check_name, description))

    print("\n🔗 Database Connectivity")
    db_check = check_database_connectivity()
    all_checks.append(db_check)
    check_name, passed, description = db_check
    print(f"  {check_name}")
    if not passed:
        print(f"    → {description}")
        critical_failures.append((check_name, description))

    print("\n📁 Data Directory Structure")
    dir_checks = check_data_directory_structure()
    all_checks.extend(dir_checks)
    for check_name, passed, description in dir_checks:
        print(f"  {check_name}")
        if not passed:
            print(f"    → {description}")

    print("\n🔧 External Tools")
    tool_checks = check_external_tools()
    all_checks.extend(tool_checks)
    for check_name, passed, description in tool_checks:
        print(f"  {check_name}")
        if not passed:
            print(f"    → {description}")
            if "ffmpeg" in check_name and "❌" in check_name:
                critical_failures.append((check_name, description))

    print("\n🌐 GitHub Repository")
    repo_check = check_github_repo_visibility()
    all_checks.append(repo_check)
    check_name, passed, description = repo_check
    print(f"  {check_name}")
    if not passed:
        print(f"    → {description}")
        if "[CRITICAL]" in check_name:
            critical_failures.append((check_name, description))

    print("\n🐍 Python Dependencies")
    dep_checks = check_python_dependencies()
    all_checks.extend(dep_checks)
    for check_name, passed, description in dep_checks:
        print(f"  {check_name}")
        if not passed:
            print(f"    → {description}")
            if "❌" in check_name and "optional" not in description:
                critical_failures.append((check_name, description))

    # Summary
    passed_checks = sum(1 for _, passed, _ in all_checks if passed)
    total_checks = len(all_checks)

    print("\n" + "=" * 50)
    print(f"📊 Summary: {passed_checks}/{total_checks} checks passed")

    # Handle critical failures with FAIL FAST principle
    if critical_failures:
        print("\n🚨 CRITICAL FAILURES DETECTED - SYSTEM CANNOT OPERATE")
        print("=" * 60)
        print("The following CRITICAL issues must be fixed before proceeding:")
        print()
        for i, (check_name, description) in enumerate(critical_failures, 1):
            print(f"{i}. {check_name}")
            print(f"   {description}")
            print()
        print("❌ ABORTING: Fix critical issues and run doctor.py again")
        print("❌ NO FALLBACKS: System will not attempt to run with missing configuration")
        sys.exit(2)  # Exit code 2 for critical failures

    if passed_checks == total_checks:
        print("🎉 All checks passed! Environment is ready.")
        sys.exit(0)
    else:
        failed_checks = total_checks - passed_checks
        print(f"⚠️  {failed_checks} non-critical checks failed. Review issues above.")
        print("💡 System may still operate but with reduced functionality.")
        sys.exit(1)  # Exit code 1 for non-critical failures


if __name__ == "__main__":
    main()