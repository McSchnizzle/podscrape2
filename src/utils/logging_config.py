"""
Comprehensive logging infrastructure for RSS Podcast Transcript Digest System.
Provides structured logging with file rotation, error handling, and performance tracking.
"""

import logging
import logging.handlers
import sys
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
import traceback
import time
import threading
import atexit

try:
    from src.database.models import PipelineLog, get_pipeline_log_repo
except Exception:  # pragma: no cover - fallback when database layer unavailable
    PipelineLog = None  # type: ignore
    get_pipeline_log_repo = None  # type: ignore

class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs"""
    
    def format(self, record):
        """Format log record as structured JSON"""
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_entry, default=str)

class HumanReadableFormatter(logging.Formatter):
    """Human-readable formatter for console output"""
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

class PerformanceLogger:
    """Context manager for tracking operation performance"""
    
    def __init__(self, operation_name: str, logger: logging.Logger):
        self.operation_name = operation_name
        self.logger = logger
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.info(f"Starting {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        
        if exc_type is None:
            self.logger.info(
                f"Completed {self.operation_name}",
                extra={'extra_fields': {'duration_seconds': round(duration, 3)}}
            )
        else:
            self.logger.error(
                f"Failed {self.operation_name}: {exc_val}",
                extra={'extra_fields': {'duration_seconds': round(duration, 3)}},
                exc_info=(exc_type, exc_val, exc_tb)
            )


class BatchDatabaseLogHandler(logging.Handler):
    """
    Batch database log handler - stores logs in memory and writes at phase completion.

    This avoids threading/deadlock issues by deferring all database writes until
    flush_to_database() is called explicitly at the end of the phase.
    """

    def __init__(self, run_id: str, phase: str):
        super().__init__()
        self.run_id = run_id
        self.phase = phase
        self.buffer: List[PipelineLog] = []
        self.enabled = True
        self._error_reported = False

        if PipelineLog is None or get_pipeline_log_repo is None:
            self.enabled = False
            return

        # Set minimum level to INFO (skip DEBUG logs)
        self.setLevel(logging.INFO)

    def emit(self, record: logging.LogRecord):
        """Accumulate log records in memory buffer - no database access during logging"""
        if not self.enabled:
            return

        # Skip logs from database module to prevent circular logging
        if record.name.startswith('src.database'):
            return

        try:
            # Only persist informative records; skip verbose DEBUG chatter
            if record.levelno < logging.INFO:
                return

            timestamp = datetime.fromtimestamp(record.created)
            extra_payload: Dict[str, Any] = {}

            if hasattr(record, 'extra_fields') and isinstance(record.extra_fields, dict):
                extra_payload.update(record.extra_fields)

            if record.exc_info:
                exc_type, exc_value, exc_tb = record.exc_info
                extra_payload.setdefault('exception', {
                    'type': exc_type.__name__ if exc_type else None,
                    'message': str(exc_value) if exc_value else None,
                    'traceback': traceback.format_exception(*record.exc_info)
                })

            if record.stack_info:
                extra_payload['stack'] = record.stack_info

            # Create log entry object but DON'T write to database yet
            log_entry = PipelineLog(
                run_id=self.run_id,
                phase=self.phase,
                timestamp=timestamp,
                level=record.levelname,
                logger_name=record.name,
                module=getattr(record, 'module', None),
                function=getattr(record, 'funcName', None),
                line=getattr(record, 'lineno', None),
                message=record.getMessage(),
                extra=extra_payload or None,
            )

            # Just append to buffer - no locks, no database access
            self.buffer.append(log_entry)

        except Exception as exc:  # pragma: no cover - defensive
            self._disable(exc)

    def flush_to_database(self):
        """
        Flush all buffered logs to database in a single batch operation.
        Called explicitly at phase completion - not during logging.
        """
        if not self.enabled or not self.buffer:
            return

        try:
            # Get repository and perform single bulk insert
            repo = get_pipeline_log_repo()
            repo.bulk_insert(self.buffer)

            # Clear buffer after successful write
            log_count = len(self.buffer)
            self.buffer.clear()

            # Log success to file/console (not to database to avoid recursion)
            sys.stderr.write(f"[BatchDatabaseLogHandler] Wrote {log_count} logs to database\n")

        except Exception as exc:  # pragma: no cover - defensive
            self._disable(exc)
            # Clear buffer even on failure to prevent memory issues
            self.buffer.clear()

    def close(self):
        """Handler cleanup - flush any remaining logs"""
        try:
            self.flush_to_database()
        finally:
            super().close()

    def _disable(self, exc: Exception):
        """Disable handler on error and report once"""
        if not self.enabled:
            return
        self.enabled = False
        if not self._error_reported:
            sys.stderr.write(f"[BatchDatabaseLogHandler] disabled: {exc}\n")
            self._error_reported = True

class LoggingManager:
    """
    Manages logging configuration for the entire application.
    Provides file logging with rotation, console logging, and structured output.
    """
    
    def __init__(self, log_dir: str = None, log_level: str = 'INFO'):
        if log_dir is None:
            # Default to data/logs/ directory relative to project root
            project_root = Path(__file__).parent.parent.parent
            log_dir = project_root / 'data' / 'logs'
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_level = getattr(logging, log_level.upper())
        self._configure_logging()
    
    def _configure_logging(self):
        """Configure logging handlers and formatters"""
        
        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler (human-readable, INFO and above)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(HumanReadableFormatter())
        root_logger.addHandler(console_handler)
        
        # Main log file (human-readable, all levels)
        main_log_file = self.log_dir / 'digest.log'
        main_handler = logging.handlers.RotatingFileHandler(
            main_log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=10
        )
        main_handler.setLevel(self.log_level)
        main_handler.setFormatter(HumanReadableFormatter())
        root_logger.addHandler(main_handler)
        
        # Structured log file (JSON format, all levels)
        structured_log_file = self.log_dir / 'digest_structured.log'
        structured_handler = logging.handlers.RotatingFileHandler(
            structured_log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        structured_handler.setLevel(self.log_level)
        structured_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(structured_handler)
        
        # Error log file (errors and critical only)
        error_log_file = self.log_dir / 'errors.log'
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=10
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(HumanReadableFormatter())
        root_logger.addHandler(error_handler)
        
        # Daily log file (timestamped)
        daily_log_file = self.log_dir / f'digest_{datetime.now().strftime("%Y%m%d")}.log'
        daily_handler = logging.FileHandler(daily_log_file)
        daily_handler.setLevel(self.log_level)
        daily_handler.setFormatter(HumanReadableFormatter())
        root_logger.addHandler(daily_handler)
        
        logging.info(f"Logging configured with level {logging.getLevelName(self.log_level)}")
        logging.info(f"Logs directory: {self.log_dir}")
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger instance with the given name"""
        return logging.getLogger(name)
    
    def log_performance(self, operation_name: str, logger: logging.Logger = None) -> PerformanceLogger:
        """Get a performance logging context manager"""
        if logger is None:
            logger = logging.getLogger('performance')
        return PerformanceLogger(operation_name, logger)

def setup_logging(log_dir: str = None, log_level: str = 'INFO') -> LoggingManager:
    """
    Set up application logging.
    
    Args:
        log_dir: Directory for log files (default: data/logs/)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        LoggingManager instance
    """
    return LoggingManager(log_dir, log_level)

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance (convenience function)"""
    return logging.getLogger(name)

# Exception handling utilities
def log_exception(logger: logging.Logger, exception: Exception, 
                 context: str = None, extra_data: Dict[str, Any] = None):
    """Log an exception with context and additional data"""
    message = f"Exception in {context}: {exception}" if context else f"Exception: {exception}"
    
    extra_fields = {
        'exception_type': type(exception).__name__,
        'exception_message': str(exception)
    }
    
    if extra_data:
        extra_fields.update(extra_data)
    
    logger.error(
        message,
        extra={'extra_fields': extra_fields},
        exc_info=True
    )

def log_api_call(logger: logging.Logger, api_name: str, endpoint: str = None, 
                response_code: int = None, duration: float = None):
    """Log API call information"""
    extra_fields = {
        'api_name': api_name,
        'endpoint': endpoint,
        'response_code': response_code,
        'duration_seconds': duration
    }
    
    message = f"API call to {api_name}"
    if endpoint:
        message += f" ({endpoint})"
    if response_code:
        message += f" - {response_code}"
    
    level = logging.INFO if response_code and 200 <= response_code < 300 else logging.WARNING
    logger.log(level, message, extra={'extra_fields': extra_fields})

@contextmanager
def error_handling(logger: logging.Logger, operation: str, 
                  reraise: bool = True, return_value: Any = None):
    """
    Context manager for consistent error handling and logging.
    
    Args:
        logger: Logger instance
        operation: Description of the operation being performed
        reraise: Whether to reraise the exception after logging
        return_value: Value to return if exception occurs and reraise=False
    """
    try:
        yield
    except Exception as e:
        log_exception(logger, e, operation)
        if reraise:
            raise
        return return_value

# Log level utilities
def set_log_level(level: str):
    """Set the log level for all loggers"""
    numeric_level = getattr(logging, level.upper())
    logging.getLogger().setLevel(numeric_level)
    logging.info(f"Log level set to {level.upper()}")

def enable_debug_logging():
    """Enable debug logging for troubleshooting"""
    set_log_level('DEBUG')
    
    # Add debug-specific handlers if needed
    debug_logger = logging.getLogger('debug')
    debug_logger.info("Debug logging enabled")

def cleanup_old_logs(log_dir: str = None, days_to_keep: int = 3):
    """Clean up log files older than specified days (default: 3 days)"""
    if log_dir is None:
        project_root = Path(__file__).parent.parent.parent
        log_dir = project_root / 'logs'  # Changed to top-level logs directory

    log_dir = Path(log_dir)
    if not log_dir.exists():
        return

    logger = get_logger(__name__)
    current_time = time.time()
    cutoff_time = current_time - (days_to_keep * 24 * 60 * 60)

    cleaned_count = 0
    for log_file in log_dir.glob('*.log*'):
        if log_file.stat().st_mtime < cutoff_time:
            try:
                log_file.unlink()
                cleaned_count += 1
                print(f"🗑️  Cleaned up old log: {log_file.name}")
            except Exception as e:
                logger.warning(f"Failed to delete old log file {log_file}: {e}")

    if cleaned_count > 0:
        logger.info(f"Cleaned up {cleaned_count} old log files")


class PipelineLogger:
    """Phase-specific logging for pipeline operations"""

    def __init__(self, phase_name: str, verbose: bool = False, console_output: bool = True, run_cleanup: bool = True):
        """
        Initialize logging for a specific pipeline phase.

        Args:
            phase_name: Name of the phase (e.g., 'orchestrator', 'discovery', 'audio', etc.)
            verbose: Enable debug logging
            console_output: Enable console output in addition to file logging
            run_cleanup: Whether to run log cleanup (default True, set False for sub-phases)
        """
        self.phase_name = phase_name
        self.verbose = verbose
        self.console_output = console_output

        # Create logs directory at project root level
        project_root = Path(__file__).parent.parent.parent
        self.logs_dir = project_root / "logs"
        self.logs_dir.mkdir(exist_ok=True)

        # Clean up old logs (older than 3 days) at start - only if requested and not running under orchestrator
        if run_cleanup and not os.getenv('ORCHESTRATED_EXECUTION'):
            cleanup_old_logs(str(self.logs_dir), days_to_keep=3)

        # Create phase-specific log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.logs_dir / f"{phase_name}_{timestamp}.log"

        # Configure logging
        self._setup_logging()

        # Attach optional database handler for workflow runs
        self.db_handler = self._attach_db_handler()

        # Create logger instance
        self.logger = logging.getLogger(f"pipeline.{phase_name}")

    def _setup_logging(self):
        """Setup logging configuration for this phase"""
        # Clear any existing handlers to avoid conflicts
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Configure logging level
        level = logging.DEBUG if self.verbose else logging.INFO

        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )

        # Create file handler for this phase
        file_handler = logging.FileHandler(self.log_file, mode='w')
        file_handler.setLevel(level)
        file_handler.setFormatter(detailed_formatter)

        # Create handlers list
        handlers = [file_handler]

        # Add console handler if requested
        if self.console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            console_handler.setFormatter(simple_formatter)
            handlers.append(console_handler)

        # Configure root logger
        logging.basicConfig(
            level=level,
            handlers=handlers,
            force=True
        )

    def _attach_db_handler(self):
        run_id = os.getenv('PIPELINE_RUN_ID')
        if not run_id or PipelineLog is None or get_pipeline_log_repo is None:
            return None
        db_logging_enabled = os.getenv('PIPELINE_DB_LOGS', '').lower() in {'1', 'true', 'yes'}
        if not db_logging_enabled:
            return None

        try:
            handler = BatchDatabaseLogHandler(run_id, self.phase_name)
            logging.getLogger().addHandler(handler)
            return handler
        except Exception as exc:  # pragma: no cover - defensive
            logging.getLogger(__name__).warning(f"Database log handler disabled: {exc}")
            return None

    def get_logger(self) -> logging.Logger:
        """Get the configured logger instance"""
        return self.logger

    def get_log_file(self) -> Path:
        """Get the log file path"""
        return self.log_file

    def log_phase_start(self, description: str = ""):
        """Log the start of a phase with formatting"""
        self.logger.info("=" * 80)
        self.logger.info(f"📋 PHASE: {self.phase_name.upper()}")
        if description:
            self.logger.info(f"📝 {description}")
        self.logger.info("=" * 80)
        self.logger.info(f"📁 Log file: {self.log_file}")

    def log_phase_complete(self, success: bool = True, summary: str = ""):
        """Log the completion of a phase and flush database logs"""
        status = "✅ COMPLETED" if success else "❌ FAILED"
        self.logger.info("=" * 80)
        self.logger.info(f"🏁 {self.phase_name.upper()} {status}")
        if summary:
            self.logger.info(f"📊 {summary}")
        self.logger.info("=" * 80)

        # Flush buffered logs to database at phase completion
        if self.db_handler:
            self.db_handler.flush_to_database()


def setup_phase_logging(phase_name: str, verbose: bool = False, console_output: bool = True, run_cleanup: bool = True) -> PipelineLogger:
    """
    Convenience function to set up logging for a phase.

    Args:
        phase_name: Name of the phase
        verbose: Enable debug logging
        console_output: Enable console output
        run_cleanup: Whether to run log cleanup (default True, set False for sub-phases)

    Returns:
        PipelineLogger instance
    """
    return PipelineLogger(phase_name, verbose, console_output, run_cleanup)


def move_legacy_logs_to_logs_dir():
    """Move existing log files to the logs directory"""
    project_root = Path(__file__).parent.parent.parent
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)

    # Find all .log files in the current directory
    current_dir = project_root
    moved_count = 0

    for log_file in current_dir.glob("*.log"):
        try:
            target_path = logs_dir / log_file.name

            # Avoid overwriting existing files
            if target_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                stem = target_path.stem
                suffix = target_path.suffix
                target_path = logs_dir / f"{stem}_moved_{timestamp}{suffix}"

            log_file.rename(target_path)
            moved_count += 1
            print(f"📁 Moved log: {log_file.name} → logs/{target_path.name}")

        except Exception as e:
            print(f"⚠️  Failed to move {log_file}: {e}")

    if moved_count > 0:
        print(f"✅ Moved {moved_count} log files to logs/ directory")
    else:
        print("ℹ️  No legacy log files found to move")

# Application-specific loggers
def get_database_logger() -> logging.Logger:
    """Get logger for database operations"""
    return logging.getLogger('database')

def get_api_logger() -> logging.Logger:
    """Get logger for API calls"""
    return logging.getLogger('api')

def get_transcript_logger() -> logging.Logger:
    """Get logger for transcript processing"""
    return logging.getLogger('transcript')

def get_audio_logger() -> logging.Logger:
    """Get logger for audio processing"""
    return logging.getLogger('audio')

def get_publishing_logger() -> logging.Logger:
    """Get logger for publishing operations"""
    return logging.getLogger('publishing')
