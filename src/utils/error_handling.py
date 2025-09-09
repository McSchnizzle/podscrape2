"""
Error handling utilities for YouTube Transcript Digest System.
Provides custom exceptions, retry logic, and error recovery mechanisms.
"""

import time
import random
import logging
from typing import Callable, Any, Optional, Type, List
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Custom Exceptions
class DigestSystemError(Exception):
    """Base exception for digest system errors"""
    pass

class ConfigurationError(DigestSystemError):
    """Raised when configuration is invalid or missing"""
    pass

class DatabaseError(DigestSystemError):
    """Raised when database operations fail"""
    pass

class TranscriptError(DigestSystemError):
    """Raised when transcript fetching or processing fails"""
    pass

class ScoringError(DigestSystemError):
    """Raised when AI scoring operations fail"""
    pass

class GenerationError(DigestSystemError):
    """Raised when script generation fails"""
    pass

class AudioError(DigestSystemError):
    """Raised when audio processing or TTS fails"""
    pass

class PublishingError(DigestSystemError):
    """Raised when publishing operations fail"""
    pass

class PodcastError(DigestSystemError):
    """Raised when podcast processing operations fail"""
    pass

class APIError(DigestSystemError):
    """Raised when external API calls fail"""
    
    def __init__(self, message: str, api_name: str, status_code: int = None, response: str = None):
        super().__init__(message)
        self.api_name = api_name
        self.status_code = status_code
        self.response = response

class RateLimitError(APIError):
    """Raised when API rate limits are exceeded"""
    
    def __init__(self, message: str, api_name: str, retry_after: int = None):
        super().__init__(message, api_name)
        self.retry_after = retry_after

# Retry decorators and utilities
def retry_with_backoff(
    func: Callable = None,
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    exceptions: tuple = (Exception,)
):
    """
    Function/decorator for retrying functions with configurable backoff strategy.
    Can be used as a decorator or called directly with a function.
    
    Args:
        func: Function to retry (when used as direct call)
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        jitter: Add random jitter to delays
        exceptions: Tuple of exceptions to retry on
    """
    def _retry_func(target_func: Callable) -> Any:
        last_exception = None
        
        for attempt in range(max_retries + 1):  # +1 because we include the initial attempt
            try:
                return target_func()
                
            except exceptions as e:
                last_exception = e
                
                if attempt == max_retries:
                    # Last attempt failed, don't sleep
                    break
                
                # Calculate delay
                delay = base_delay * (backoff_factor ** attempt)
                delay = min(delay, max_delay)
                
                if jitter:
                    delay += random.uniform(0, delay * 0.1)
                
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                    f"Retrying in {delay:.2f} seconds..."
                )
                
                time.sleep(delay)
        
        # All attempts failed
        logger.error(f"All {max_retries + 1} attempts failed")
        raise last_exception
    
    if func is None:
        # Used as decorator
        def decorator(target_func: Callable) -> Callable:
            @wraps(target_func)
            def wrapper(*args, **kwargs):
                return _retry_func(lambda: target_func(*args, **kwargs))
            return wrapper
        return decorator
    else:
        # Used as direct function call
        return _retry_func(func)

def retry_api_call(
    api_name: str,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    respect_rate_limits: bool = True
):
    """
    Decorator specifically for API calls with rate limit handling.
    
    Args:
        api_name: Name of the API for logging
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay between retries
        respect_rate_limits: Whether to respect rate limit headers
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    result = func(*args, **kwargs)
                    
                    if attempt > 0:
                        logger.info(f"API call to {api_name} succeeded on attempt {attempt + 1}")
                    
                    return result
                    
                except RateLimitError as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        break
                    
                    # Use the retry_after value if provided
                    delay = e.retry_after if e.retry_after else base_delay * (2 ** attempt)
                    
                    logger.warning(
                        f"Rate limited by {api_name}. Waiting {delay} seconds before retry "
                        f"(attempt {attempt + 1}/{max_attempts})"
                    )
                    
                    time.sleep(delay)
                
                except APIError as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        break
                    
                    # Don't retry on certain status codes
                    if e.status_code and e.status_code in [400, 401, 403, 404]:
                        logger.error(f"Non-retryable error from {api_name}: {e}")
                        raise
                    
                    delay = base_delay * (2 ** attempt)
                    
                    logger.warning(
                        f"API error from {api_name}: {e}. Retrying in {delay} seconds "
                        f"(attempt {attempt + 1}/{max_attempts})"
                    )
                    
                    time.sleep(delay)
                
                except Exception as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        break
                    
                    delay = base_delay * (2 ** attempt)
                    
                    logger.warning(
                        f"Unexpected error calling {api_name}: {e}. Retrying in {delay} seconds "
                        f"(attempt {attempt + 1}/{max_attempts})"
                    )
                    
                    time.sleep(delay)
            
            # All attempts failed
            logger.error(f"All {max_attempts} attempts failed for {api_name} API call")
            raise last_exception
        
        return wrapper
    return decorator

# Context managers for error handling
@contextmanager
def safe_operation(operation_name: str, logger: logging.Logger = None, 
                  reraise: bool = True, default_return: Any = None):
    """
    Context manager for safe operation execution with logging.
    
    Args:
        operation_name: Name of the operation for logging
        logger: Logger instance (defaults to module logger)
        reraise: Whether to reraise exceptions
        default_return: Default return value if exception occurs and reraise=False
    """
    if logger is None:
        logger = globals()['logger']
    
    try:
        logger.info(f"Starting operation: {operation_name}")
        yield
        logger.info(f"Completed operation: {operation_name}")
        
    except Exception as e:
        logger.error(f"Operation failed: {operation_name} - {e}", exc_info=True)
        
        if reraise:
            raise
        else:
            return default_return

@contextmanager
def database_transaction(db_manager, operation_name: str):
    """
    Context manager for database transactions with proper error handling.
    
    Args:
        db_manager: Database manager instance
        operation_name: Name of the operation for logging
    """
    logger.info(f"Starting database transaction: {operation_name}")
    
    try:
        with db_manager.get_connection() as conn:
            conn.execute("BEGIN TRANSACTION")
            yield conn
            conn.commit()
            logger.info(f"Database transaction committed: {operation_name}")
            
    except Exception as e:
        logger.error(f"Database transaction failed: {operation_name} - {e}", exc_info=True)
        try:
            conn.rollback()
            logger.info(f"Database transaction rolled back: {operation_name}")
        except:
            logger.error(f"Failed to rollback transaction: {operation_name}")
        raise DatabaseError(f"Transaction failed for {operation_name}: {e}") from e

# Error recovery utilities
class ErrorTracker:
    """Tracks errors for patterns and recovery strategies"""
    
    def __init__(self):
        self.error_counts = {}
        self.recent_errors = []
        self.max_recent_errors = 100
    
    def record_error(self, error_type: str, context: str = None):
        """Record an error occurrence"""
        key = f"{error_type}:{context}" if context else error_type
        self.error_counts[key] = self.error_counts.get(key, 0) + 1
        
        self.recent_errors.append({
            'timestamp': time.time(),
            'error_type': error_type,
            'context': context
        })
        
        # Keep only recent errors
        if len(self.recent_errors) > self.max_recent_errors:
            self.recent_errors = self.recent_errors[-self.max_recent_errors:]
    
    def get_error_rate(self, error_type: str, time_window: int = 3600) -> float:
        """Get error rate for a specific error type within time window"""
        cutoff_time = time.time() - time_window
        
        recent_errors = [
            e for e in self.recent_errors 
            if e['timestamp'] > cutoff_time and e['error_type'] == error_type
        ]
        
        return len(recent_errors) / max(time_window / 3600, 1)  # errors per hour
    
    def should_circuit_break(self, error_type: str, threshold: int = 5) -> bool:
        """Determine if circuit breaker should trigger"""
        return self.get_error_rate(error_type, 300) > threshold  # 5 errors in 5 minutes

# Global error tracker instance
error_tracker = ErrorTracker()

def handle_graceful_degradation(operation: str, fallback_func: Callable = None):
    """
    Decorator for graceful degradation when operations fail.
    
    Args:
        operation: Name of the operation for logging
        fallback_func: Optional fallback function to call on failure
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
                
            except Exception as e:
                error_tracker.record_error(type(e).__name__, operation)
                logger.warning(f"Operation {operation} failed, attempting graceful degradation: {e}")
                
                if fallback_func:
                    try:
                        return fallback_func(*args, **kwargs)
                    except Exception as fallback_error:
                        logger.error(f"Fallback also failed for {operation}: {fallback_error}")
                
                # If we reach here, both primary and fallback failed
                logger.error(f"Complete failure for {operation}, no recovery possible")
                raise
        
        return wrapper
    return decorator

# Validation utilities
def validate_required_fields(data: dict, required_fields: List[str], context: str = None):
    """Validate that required fields are present and not None"""
    missing_fields = []
    
    for field in required_fields:
        if field not in data or data[field] is None:
            missing_fields.append(field)
    
    if missing_fields:
        context_str = f" in {context}" if context else ""
        raise ConfigurationError(f"Missing required fields{context_str}: {missing_fields}")

def validate_file_exists(file_path: str, context: str = None):
    """Validate that a file exists"""
    from pathlib import Path
    
    if not Path(file_path).exists():
        context_str = f" for {context}" if context else ""
        raise ConfigurationError(f"Required file not found{context_str}: {file_path}")

def validate_api_key(api_key: str, api_name: str):
    """Validate that API key is present and has correct format"""
    if not api_key:
        raise ConfigurationError(f"Missing API key for {api_name}")
    
    if len(api_key) < 10:  # Basic sanity check
        raise ConfigurationError(f"Invalid API key format for {api_name}")

# Health check utilities
def system_health_check() -> dict:
    """Perform basic system health check"""
    health_status = {
        'timestamp': time.time(),
        'status': 'healthy',
        'checks': {}
    }
    
    try:
        # Check database connectivity
        from database.models import get_database_manager
        db_manager = get_database_manager()
        with db_manager.get_connection():
            health_status['checks']['database'] = 'healthy'
    except Exception as e:
        health_status['checks']['database'] = f'unhealthy: {e}'
        health_status['status'] = 'degraded'
    
    try:
        # Check configuration
        from utils.config import get_config_manager, validate_environment
        config_manager = get_config_manager()
        topics = config_manager.load_topics()
        channels = config_manager.load_channels()
        validate_environment()
        
        health_status['checks']['configuration'] = f'healthy: {len(topics)} topics, {len(channels)} channels'
    except Exception as e:
        health_status['checks']['configuration'] = f'unhealthy: {e}'
        health_status['status'] = 'degraded'
    
    try:
        # Check log directory
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        log_dir = project_root / 'data' / 'logs'
        if log_dir.exists() and log_dir.is_dir():
            health_status['checks']['logging'] = 'healthy'
        else:
            health_status['checks']['logging'] = 'unhealthy: log directory not accessible'
            health_status['status'] = 'degraded'
    except Exception as e:
        health_status['checks']['logging'] = f'unhealthy: {e}'
        health_status['status'] = 'degraded'
    
    return health_status