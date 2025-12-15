"""
Error extraction from pipeline logs.

Extracts and classifies errors from pipeline_logs table for persistent storage.
"""

import logging
from datetime import datetime, date, timezone
from typing import Optional, List, Dict, Any

from src.database.models import (
    get_database_manager,
    get_pipeline_log_repo,
    get_workflow_error_repo,
    get_feed_repo,
    WorkflowError,
    PipelineLog,
)
from .error_classifier import ErrorClassifier

logger = logging.getLogger(__name__)


def extract_errors_from_run(run_id: str,
                            workflow_run_id: Optional[int] = None) -> List[WorkflowError]:
    """
    Extract and classify errors from pipeline logs for a specific run.

    Args:
        run_id: The pipeline run identifier
        workflow_run_id: Optional GitHub Actions workflow run ID

    Returns:
        List of WorkflowError records ready for database insertion
    """
    db_manager = get_database_manager()
    log_repo = get_pipeline_log_repo(db_manager)
    feed_repo = get_feed_repo(db_manager)
    classifier = ErrorClassifier()

    # Get all logs for this run
    logs = log_repo.get_recent_logs(run_id=run_id, limit=5000)

    if not logs:
        logger.info(f"No logs found for run {run_id}")
        return []

    # Filter to error-level logs only
    error_logs = [
        log for log in logs
        if log.level.upper() in ('ERROR', 'CRITICAL', 'FATAL', 'WARNING')
    ]

    if not error_logs:
        logger.info(f"No errors found in run {run_id}")
        return []

    logger.info(f"Processing {len(error_logs)} error logs from run {run_id}")

    # Build feed URL to ID mapping for enrichment
    feeds = feed_repo.get_all()
    url_to_feed: Dict[str, Dict[str, Any]] = {}
    for feed in feeds:
        url_to_feed[feed.feed_url] = {'id': feed.id, 'title': feed.title}

    errors = []
    for log in error_logs:
        # Classify the error
        classified = classifier.classify(
            message=log.message,
            level=log.level,
            phase_hint=log.phase
        )

        # Look up feed ID if we have a feed URL
        feed_id = None
        if classified.feed_url:
            # Try exact match first
            if classified.feed_url in url_to_feed:
                feed_id = url_to_feed[classified.feed_url]['id']
            else:
                # Try partial match (URL might be truncated)
                for url, info in url_to_feed.items():
                    if url in classified.feed_url or classified.feed_url in url:
                        feed_id = info['id']
                        break

        # Create WorkflowError record
        error = WorkflowError(
            error_date=log.timestamp.date() if log.timestamp else date.today(),
            occurred_at=log.timestamp or datetime.now(timezone.utc),
            run_id=run_id,
            workflow_run_id=workflow_run_id,
            error_category=classified.category,
            phase=classified.phase or log.phase or 'unknown',
            severity=classified.severity,
            feed_id=feed_id,
            feed_url=classified.feed_url,
            error_code=classified.error_code,
            error_message=log.message,
            error_summary=classified.error_summary,
            extra=classified.extra,
            source_log_id=log.id,
        )
        errors.append(error)

    logger.info(f"Extracted {len(errors)} errors from run {run_id}")
    return errors


def save_errors_from_run(run_id: str,
                         workflow_run_id: Optional[int] = None) -> int:
    """
    Extract and save errors from a pipeline run to workflow_errors table.

    Args:
        run_id: The pipeline run identifier
        workflow_run_id: Optional GitHub Actions workflow run ID

    Returns:
        Number of errors saved
    """
    errors = extract_errors_from_run(run_id, workflow_run_id)
    if not errors:
        return 0

    db_manager = get_database_manager()
    error_repo = get_workflow_error_repo(db_manager)

    count = error_repo.bulk_insert(errors)
    logger.info(f"Saved {count} errors for run {run_id}")
    return count


def extract_errors_after_workflow(run_id: Optional[str] = None,
                                  workflow_run_id: Optional[int] = None) -> int:
    """
    Called at the end of retention phase to extract and persist errors.

    This function should be called at the end of every workflow to ensure
    error data is captured before logs are potentially cleaned up.

    Args:
        run_id: Pipeline run ID (if known)
        workflow_run_id: GitHub Actions workflow run ID (if known)

    Returns:
        Number of errors saved
    """
    import os

    # Get run_id from environment if not provided
    if not run_id:
        run_id = os.environ.get('PIPELINE_RUN_ID')
        if not run_id:
            logger.warning("No run_id provided and PIPELINE_RUN_ID not set")
            return 0

    # Get workflow_run_id from environment if not provided
    if not workflow_run_id:
        gh_run_id = os.environ.get('GITHUB_RUN_ID')
        if gh_run_id:
            try:
                workflow_run_id = int(gh_run_id)
            except ValueError:
                pass

    return save_errors_from_run(run_id, workflow_run_id)


def get_error_summary(run_id: str) -> Dict[str, Any]:
    """
    Get a summary of errors for a run.

    Args:
        run_id: Pipeline run identifier

    Returns:
        Dict with error counts by category and phase
    """
    db_manager = get_database_manager()
    error_repo = get_workflow_error_repo(db_manager)

    errors = error_repo.get_by_run_id(run_id)

    if not errors:
        return {'total': 0, 'by_category': {}, 'by_phase': {}, 'by_severity': {}}

    # Count by category
    by_category: Dict[str, int] = {}
    by_phase: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}

    for error in errors:
        by_category[error.error_category] = by_category.get(error.error_category, 0) + 1
        by_phase[error.phase] = by_phase.get(error.phase, 0) + 1
        by_severity[error.severity] = by_severity.get(error.severity, 0) + 1

    return {
        'total': len(errors),
        'by_category': by_category,
        'by_phase': by_phase,
        'by_severity': by_severity,
    }
