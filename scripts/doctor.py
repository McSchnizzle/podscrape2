#!/usr/bin/env python3
"""
Environment and data layout validation script for podscrape2.
Validates DATABASE_URL connectivity, data directory structure, and required environment variables.
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))
os.environ['PYTHONPATH'] = str(project_root / 'src')


def check_environment_variables() -> List[Tuple[str, bool, str]]:
    """Check required environment variables are present.

    FAIL FAST PRINCIPLE: No fallbacks, no silent failures.
    Missing environment variables are critical errors that must be fixed immediately.
    """
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file

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


def check_database_connectivity() -> Tuple[str, bool, str]:
    """Test DATABASE_URL connectivity to Supabase."""
    try:
        from dotenv import load_dotenv
        load_dotenv()

        # Add src to path again for this function
        sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
        from config.env import require_database_url
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