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
from typing import Optional, Dict, Any
from contextlib import contextmanager
import traceback
import time

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

def cleanup_old_logs(log_dir: str = None, days_to_keep: int = 30):
    """Clean up log files older than specified days"""
    if log_dir is None:
        project_root = Path(__file__).parent.parent.parent
        log_dir = project_root / 'data' / 'logs'
    
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
            except Exception as e:
                logger.warning(f"Failed to delete old log file {log_file}: {e}")
    
    if cleaned_count > 0:
        logger.info(f"Cleaned up {cleaned_count} old log files")

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