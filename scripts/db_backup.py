#!/usr/bin/env python3
"""
Create a Postgres backup (pg_dump) using DATABASE_URL and optionally upload to GitHub Actions Artifacts.

Enhanced for Phase 2 of move-online plan:
- Creates pg_dump of Supabase Postgres database
- Supports GitHub Actions artifact uploading via actions/upload-artifact
- Configurable retention and compression
- Local backup storage for development/testing
"""

import os
import sys
import json
import gzip
import subprocess
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from src.config.env import require_database_url


def find_pg_dump_executable():
    """
    Find pg_dump executable in PATH or common installation locations.

    Returns:
        str: Path to pg_dump executable, or None if not found
    """
    import platform
    import shutil

    # First try standard PATH
    pg_dump = shutil.which('pg_dump')
    if pg_dump:
        return pg_dump

    # Platform-specific fallback paths
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
            'C:\\Program Files\\PostgreSQL\\15\\bin\\pg_dump.exe',
            'C:\\Program Files\\PostgreSQL\\14\\bin\\pg_dump.exe',
            'C:\\Program Files\\PostgreSQL\\13\\bin\\pg_dump.exe',
            'C:\\PostgreSQL\\bin\\pg_dump.exe',
        ]
    }

    current_platform = platform.system()
    if current_platform in common_paths:
        for pg_dump_path in common_paths[current_platform]:
            if Path(pg_dump_path).exists():
                return pg_dump_path

    return None


def compress_file(file_path: Path) -> Path:
    """
    Compress a file using gzip

    Args:
        file_path: Path to file to compress

    Returns:
        Path to compressed file
    """
    compressed_path = file_path.with_suffix(file_path.suffix + '.gz')

    print(f"Compressing {file_path.name}...")
    with open(file_path, 'rb') as f_in:
        with gzip.open(compressed_path, 'wb') as f_out:
            f_out.write(f_in.read())

    # Remove original uncompressed file
    file_path.unlink()
    print(f"Compressed: {compressed_path.name} ({get_file_size(compressed_path)})")

    return compressed_path


def get_file_size(file_path: Path) -> str:
    """Get human-readable file size"""
    size_bytes = file_path.stat().st_size
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def create_github_actions_output(backup_path: Path, metadata: dict):
    """
    Create GitHub Actions outputs for the backup file

    Args:
        backup_path: Path to backup file
        metadata: Backup metadata
    """
    if not os.getenv('GITHUB_ACTIONS'):
        return

    github_output = os.getenv('GITHUB_OUTPUT')
    if not github_output:
        return

    try:
        with open(github_output, 'a') as f:
            f.write(f"backup-file={backup_path}\n")
            f.write(f"backup-size={backup_path.stat().st_size}\n")
            f.write(f"backup-timestamp={metadata['timestamp']}\n")
            f.write(f"backup-compressed={'true' if backup_path.suffix == '.gz' else 'false'}\n")

        print(f"GitHub Actions outputs set:")
        print(f"  backup-file: {backup_path}")
        print(f"  backup-size: {backup_path.stat().st_size}")
        print(f"  backup-timestamp: {metadata['timestamp']}")

    except Exception as e:
        print(f"Warning: Failed to set GitHub Actions outputs: {e}")


def create_backup_metadata(backup_path: Path, pg_url: str) -> dict:
    """
    Create metadata file for the backup

    Args:
        backup_path: Path to backup file
        pg_url: Database URL (sanitized)

    Returns:
        Metadata dictionary
    """
    # Sanitize URL for metadata (remove password)
    sanitized_url = pg_url
    if '@' in pg_url:
        # Remove password from URL for security
        parts = pg_url.split('@')
        if len(parts) >= 2:
            user_pass = parts[0].split('://')[-1]
            if ':' in user_pass:
                user = user_pass.split(':')[0]
                sanitized_url = pg_url.replace(user_pass, user)

    metadata = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'backup_file': backup_path.name,
        'file_size': backup_path.stat().st_size,
        'file_size_formatted': get_file_size(backup_path),
        'database_host': sanitized_url.split('@')[-1].split('/')[0] if '@' in sanitized_url else 'unknown',
        'backup_type': 'pg_dump_plain',
        'compressed': backup_path.suffix == '.gz',
        'retention_days': 7
    }

    # Write metadata file
    metadata_path = backup_path.with_suffix('.json')
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"Metadata saved: {metadata_path.name}")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Create Supabase Postgres backup and optionally upload to GitHub Actions Artifacts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create local backup
  python3 scripts/db_backup.py

  # Create compressed backup
  python3 scripts/db_backup.py --compress

  # In GitHub Actions (with actions/upload-artifact step after this)
  python3 scripts/db_backup.py --compress --github-actions

  # Specify custom output directory
  python3 scripts/db_backup.py --output-dir /tmp/backups
        """
    )

    parser.add_argument('--compress', action='store_true',
                       help='Compress backup with gzip')
    parser.add_argument('--output-dir', default='data/backups',
                       help='Output directory for backup files (default: data/backups)')
    parser.add_argument('--github-actions', action='store_true',
                       help='Optimize for GitHub Actions environment (sets outputs)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')

    args = parser.parse_args()

    try:
        # Load environment and get database URL
        load_dotenv()
        db_url = require_database_url()

        # Ensure we're using Supabase
        if 'supabase.co' not in db_url:
            print("Warning: DATABASE_URL doesn't appear to be Supabase")

        # pg_dump expects a libpq-style URL without the SQLAlchemy driver suffix
        pg_url = db_url.replace("postgresql+psycopg://", "postgresql://")

        # Create output directory
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Generate backup filename
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"pg_dump_{ts}.sql"

        # Find pg_dump executable (with fallback paths)
        pg_dump_exe = find_pg_dump_executable()
        if not pg_dump_exe:
            print("❌ pg_dump not found in PATH or common installation locations")
            print("Install PostgreSQL client tools:")
            print("  macOS: brew install libpq")
            print("  Ubuntu/Debian: sudo apt-get install postgresql-client")
            print("  RHEL/CentOS: sudo yum install postgresql")
            sys.exit(1)

        # Build pg_dump command
        cmd = [
            pg_dump_exe,
            "--no-owner",
            "--no-privileges",
            "--format=plain",
            "--verbose" if args.verbose else "--no-comments",
            pg_url,
        ]

        if not args.verbose:
            # Remove --verbose if not requested
            cmd = [c for c in cmd if c != "--verbose"]

        print(f"Creating Supabase backup...")
        print(f"Output: {out_path}")

        # Run pg_dump
        with open(out_path, "w", encoding="utf-8") as f:
            try:
                result = subprocess.run(cmd, check=True, stdout=f, stderr=subprocess.PIPE, text=True)
                if args.verbose and result.stderr:
                    print("pg_dump stderr:", result.stderr)
            except subprocess.CalledProcessError as e:
                print(f"pg_dump failed: {e}")
                if e.stderr:
                    print(f"Error output: {e.stderr}")
                sys.exit(1)

        print(f"Backup created: {out_path.name} ({get_file_size(out_path)})")

        # Compress if requested
        if args.compress:
            out_path = compress_file(out_path)

        # Create metadata
        metadata = create_backup_metadata(out_path, pg_url)

        # Set GitHub Actions outputs if in CI
        if args.github_actions or os.getenv('GITHUB_ACTIONS'):
            create_github_actions_output(out_path, metadata)
            print(f"\n✅ Backup ready for GitHub Actions artifact upload:")
            print(f"   File: {out_path}")
            print(f"   Size: {get_file_size(out_path)}")
            print(f"   Use: actions/upload-artifact@v4 with path: {out_path}")

        print(f"\n✅ Backup complete: {out_path}")

    except KeyboardInterrupt:
        print("\n⏹️  Backup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
