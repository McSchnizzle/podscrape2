#!/usr/bin/env python3
"""
Mine historical GitHub Actions workflow logs for errors.

This script fetches workflow runs from GitHub Actions, downloads their logs,
extracts and classifies errors, and stores them in the workflow_errors table.

Usage:
    python3 scripts/mine_github_errors.py --days-back 30
    python3 scripts/mine_github_errors.py --limit 10 --dry-run
    python3 scripts/mine_github_errors.py --workflow "Full Digest Pipeline"
"""

import argparse
import json
import logging
import re
import subprocess
import sys
from datetime import datetime, date, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple

# Add project root to path
sys.path.insert(0, '.')

from src.error_tracking import ErrorClassifier
from src.database.models import (
    get_database_manager,
    get_workflow_error_repo,
    get_feed_repo,
    WorkflowError,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_workflow_runs(days_back: int = 30, limit: int = 100,
                      workflow: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch workflow runs from GitHub Actions.

    Args:
        days_back: Number of days to look back
        limit: Maximum number of runs to fetch
        workflow: Optional workflow name filter

    Returns:
        List of workflow run dictionaries
    """
    cmd = ['gh', 'run', 'list', '--json',
           'databaseId,workflowName,status,conclusion,createdAt,updatedAt',
           '--limit', str(limit)]

    if workflow:
        cmd.extend(['--workflow', workflow])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        runs = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to fetch workflow runs: {e.stderr}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse workflow runs JSON: {e}")
        return []

    # Filter by date
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
    filtered_runs = []

    for run in runs:
        created_at = run.get('createdAt')
        if created_at:
            try:
                run_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                if run_date >= cutoff_date:
                    filtered_runs.append(run)
            except ValueError:
                continue

    logger.info(f"Found {len(filtered_runs)} workflow runs in the last {days_back} days")
    return filtered_runs


def download_run_logs(run_id: int) -> Optional[str]:
    """
    Download logs for a specific workflow run.

    Args:
        run_id: GitHub Actions workflow run ID

    Returns:
        Log content as string, or None if failed
    """
    cmd = ['gh', 'run', 'view', str(run_id), '--log']

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.warning(f"Failed to download logs for run {run_id}: {result.stderr}")
            return None
        return result.stdout
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout downloading logs for run {run_id}")
        return None
    except subprocess.CalledProcessError as e:
        logger.warning(f"Error downloading logs for run {run_id}: {e}")
        return None


def parse_github_logs(log_content: str) -> List[Dict[str, Any]]:
    """
    Parse GitHub Actions log content into structured entries.

    Args:
        log_content: Raw log content from `gh run view --log`

    Returns:
        List of log entries with timestamp, level, phase, and message
    """
    entries = []

    # Pattern for GitHub Actions log lines
    # Format: YYYY-MM-DDTHH:MM:SS.sssZ [LEVEL] message
    # Or: job_name\tYYYY-MM-DDTHH:MM:SS.sssZ message
    timestamp_pattern = re.compile(
        r'^(?:(\S+)\t)?(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)\s+(.*)$'
    )

    # Error indicators in log messages
    error_indicators = [
        r'\[ERROR\]',
        r'\[CRITICAL\]',
        r'\[FATAL\]',
        r'ERROR:',
        r'CRITICAL:',
        r'FATAL:',
        r'Error:',
        r'error:',
        r'Failed',
        r'failed',
        r'Exception',
        r'Traceback',
        r'\b4\d{2}\b.*?(Forbidden|Not Found|Error)',
        r'\b5\d{2}\b.*?(Error|Internal)',
    ]
    error_pattern = re.compile('|'.join(error_indicators), re.IGNORECASE)

    # Phase indicators
    phase_map = {
        'discovery': ['discover', 'rss', 'feed'],
        'audio': ['audio', 'download', 'transcri', 'whisper'],
        'digest': ['digest', 'script', 'gpt', 'openai', 'scor'],
        'tts': ['tts', 'elevenlabs', 'voice'],
        'publishing': ['publish', 'github', 'release', 'upload'],
        'retention': ['retention', 'cleanup', 'delete'],
    }

    current_phase = 'unknown'

    for line in log_content.split('\n'):
        # Try to parse timestamp
        match = timestamp_pattern.match(line)
        if match:
            job_name = match.group(1) or ''
            timestamp_str = match.group(2)
            message = match.group(3)

            # Detect phase from job name or message
            combined = (job_name + ' ' + message).lower()
            for phase, indicators in phase_map.items():
                if any(ind in combined for ind in indicators):
                    current_phase = phase
                    break

            # Check if this is an error
            if error_pattern.search(message):
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                except ValueError:
                    timestamp = datetime.now(timezone.utc)

                # Determine level
                level = 'ERROR'
                if 'CRITICAL' in message or 'FATAL' in message:
                    level = 'CRITICAL'
                elif 'WARNING' in message or 'warn' in message.lower():
                    level = 'WARNING'

                entries.append({
                    'timestamp': timestamp,
                    'level': level,
                    'phase': current_phase,
                    'message': message,
                    'job_name': job_name,
                })

    return entries


def extract_errors_from_gh_logs(log_content: str,
                                 run_id: int,
                                 created_at: datetime,
                                 classifier: ErrorClassifier,
                                 feed_url_to_id: Dict[str, int]) -> List[WorkflowError]:
    """
    Extract WorkflowError records from GitHub Actions log content.

    Args:
        log_content: Raw log content
        run_id: GitHub Actions workflow run ID
        created_at: When the workflow started
        classifier: ErrorClassifier instance
        feed_url_to_id: Mapping of feed URLs to feed IDs

    Returns:
        List of WorkflowError records
    """
    entries = parse_github_logs(log_content)

    if not entries:
        return []

    errors = []
    for entry in entries:
        classified = classifier.classify(
            message=entry['message'],
            level=entry['level'],
            phase_hint=entry['phase']
        )

        # Look up feed ID
        feed_id = None
        if classified.feed_url:
            if classified.feed_url in feed_url_to_id:
                feed_id = feed_url_to_id[classified.feed_url]
            else:
                for url, fid in feed_url_to_id.items():
                    if url in classified.feed_url or classified.feed_url in url:
                        feed_id = fid
                        break

        error = WorkflowError(
            error_date=entry['timestamp'].date(),
            occurred_at=entry['timestamp'],
            run_id=f"gh-{run_id}",  # Prefix to distinguish from pipeline run IDs
            workflow_run_id=run_id,
            error_category=classified.category,
            phase=classified.phase or entry['phase'],
            severity=classified.severity,
            feed_id=feed_id,
            feed_url=classified.feed_url,
            error_code=classified.error_code,
            error_message=entry['message'],
            error_summary=classified.error_summary,
            extra=classified.extra,
        )
        errors.append(error)

    return errors


def mine_errors(days_back: int = 30,
                limit: int = 100,
                workflow: Optional[str] = None,
                dry_run: bool = False) -> Tuple[int, int]:
    """
    Mine GitHub Actions logs for errors and store them.

    Args:
        days_back: Number of days to look back
        limit: Maximum number of workflow runs to process
        workflow: Optional workflow name filter
        dry_run: If True, don't save to database

    Returns:
        Tuple of (runs_processed, errors_saved)
    """
    classifier = ErrorClassifier()
    db_manager = get_database_manager()
    feed_repo = get_feed_repo(db_manager)
    error_repo = get_workflow_error_repo(db_manager)

    # Build feed URL to ID mapping
    feeds = feed_repo.get_all()
    feed_url_to_id = {f.feed_url: f.id for f in feeds}

    # Fetch workflow runs
    runs = get_workflow_runs(days_back=days_back, limit=limit, workflow=workflow)

    if not runs:
        logger.info("No workflow runs to process")
        return 0, 0

    runs_processed = 0
    total_errors = 0
    all_errors: List[WorkflowError] = []

    for run in runs:
        run_id = run.get('databaseId')
        if not run_id:
            continue

        logger.info(f"Processing run {run_id} ({run.get('workflowName')})...")

        # Download logs
        log_content = download_run_logs(run_id)
        if not log_content:
            logger.warning(f"No logs available for run {run_id}")
            continue

        # Parse created_at
        created_at_str = run.get('createdAt')
        try:
            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            created_at = datetime.now(timezone.utc)

        # Extract errors
        errors = extract_errors_from_gh_logs(
            log_content=log_content,
            run_id=run_id,
            created_at=created_at,
            classifier=classifier,
            feed_url_to_id=feed_url_to_id
        )

        if errors:
            logger.info(f"  Found {len(errors)} errors in run {run_id}")
            all_errors.extend(errors)
            total_errors += len(errors)

        runs_processed += 1

    # Save errors (if not dry run)
    if all_errors and not dry_run:
        saved_count = error_repo.bulk_insert(all_errors)
        logger.info(f"Saved {saved_count} errors to database")
    elif all_errors and dry_run:
        logger.info(f"DRY RUN: Would save {len(all_errors)} errors")

        # Print summary
        by_category: Dict[str, int] = {}
        by_phase: Dict[str, int] = {}
        for err in all_errors:
            by_category[err.error_category] = by_category.get(err.error_category, 0) + 1
            by_phase[err.phase] = by_phase.get(err.phase, 0) + 1

        print("\nError Summary:")
        print(f"  By Category: {by_category}")
        print(f"  By Phase: {by_phase}")

    return runs_processed, total_errors


def main():
    parser = argparse.ArgumentParser(
        description='Mine GitHub Actions workflow logs for errors'
    )
    parser.add_argument(
        '--days-back', type=int, default=30,
        help='Number of days to look back (default: 30)'
    )
    parser.add_argument(
        '--limit', type=int, default=100,
        help='Maximum number of workflow runs to process (default: 100)'
    )
    parser.add_argument(
        '--workflow', type=str,
        help='Filter by workflow name (e.g., "Full Digest Pipeline")'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Parse and classify but do not save to database'
    )

    args = parser.parse_args()

    logger.info(f"Mining GitHub Actions logs (days_back={args.days_back}, "
                f"limit={args.limit}, workflow={args.workflow}, dry_run={args.dry_run})")

    runs_processed, errors_found = mine_errors(
        days_back=args.days_back,
        limit=args.limit,
        workflow=args.workflow,
        dry_run=args.dry_run
    )

    print(f"\nCompleted: Processed {runs_processed} runs, found {errors_found} errors")


if __name__ == '__main__':
    main()
