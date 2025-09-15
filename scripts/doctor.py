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
    """Check required environment variables are present."""
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file

    checks = []

    # Required API keys
    required_vars = [
        ('OPENAI_API_KEY', 'OpenAI API key for content scoring and script generation'),
        ('ELEVENLABS_API_KEY', 'ElevenLabs API key for TTS audio generation'),
        ('GITHUB_TOKEN', 'GitHub token for publishing releases'),
        ('GITHUB_REPOSITORY', 'GitHub repository in format OWNER/REPO'),
    ]

    for var_name, description in required_vars:
        value = os.getenv(var_name)
        if value and not value.startswith('test-') and value != 'your-key-here':
            checks.append((f"✅ {var_name}", True, description))
        else:
            checks.append((f"❌ {var_name}", False, f"Missing or placeholder: {description}"))

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


def check_external_tools() -> List[Tuple[str, bool, str]]:
    """Check availability of external tools."""
    checks = []

    tools = [
        ('ffmpeg', 'Required for audio chunking and format conversion'),
        ('gh', 'GitHub CLI for publishing (optional if GITHUB_TOKEN is available)'),
        ('pg_dump', 'PostgreSQL client for database backups'),
    ]

    for tool, description in tools:
        try:
            import subprocess
            result = subprocess.run([tool, '--version'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0] if result.stdout else result.stderr.split('\n')[0]
                checks.append((f"✅ {tool}", True, f"{description} - {version_line[:50]}"))
            else:
                checks.append((f"❌ {tool}", False, f"{description} - command failed"))
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
    """Run all validation checks and display results."""
    print("🏥 Podscrape2 Environment Doctor")
    print("=" * 50)

    all_checks = []

    # Run all checks
    print("\n📋 Environment Variables")
    env_checks = check_environment_variables()
    all_checks.extend(env_checks)
    for check_name, passed, description in env_checks:
        print(f"  {check_name}")
        if not passed:
            print(f"    → {description}")

    print("\n🔗 Database Connectivity")
    db_check = check_database_connectivity()
    all_checks.append(db_check)
    check_name, passed, description = db_check
    print(f"  {check_name}")
    if not passed:
        print(f"    → {description}")

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

    print("\n🐍 Python Dependencies")
    dep_checks = check_python_dependencies()
    all_checks.extend(dep_checks)
    for check_name, passed, description in dep_checks:
        print(f"  {check_name}")
        if not passed:
            print(f"    → {description}")

    # Summary
    passed_checks = sum(1 for _, passed, _ in all_checks if passed)
    total_checks = len(all_checks)

    print("\n" + "=" * 50)
    print(f"📊 Summary: {passed_checks}/{total_checks} checks passed")

    if passed_checks == total_checks:
        print("🎉 All checks passed! Environment is ready.")
        sys.exit(0)
    else:
        failed_checks = total_checks - passed_checks
        print(f"⚠️  {failed_checks} checks failed. Review issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()