import functools
import logging
import random
import time
from typing import Any, Callable, Optional, Tuple, Type, Union

logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        jitter_ratio: float = 0.1,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.jitter_ratio = jitter_ratio


def smart_retry(
    config: Optional[RetryConfig] = None,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    non_retryable_exceptions: Tuple[Type[Exception], ...] = (),
) -> Callable:
    """
    Smart retry decorator with exponential backoff and jitter.
    
    Args:
        config: Retry configuration
        retryable_exceptions: Exceptions that should trigger retry
        non_retryable_exceptions: Exceptions that should not trigger retry
    
    Returns:
        Decorated function with retry logic
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(f"Function {func.__name__} succeeded on attempt {attempt + 1}")
                    return result
                    
                except Exception as e:
                    last_exception = e
                    
                    # Check if exception is non-retryable
                    if any(isinstance(e, exc_type) for exc_type in non_retryable_exceptions):
                        logger.error(f"Non-retryable exception in {func.__name__}: {e}")
                        raise e
                    
                    # Check if exception is retryable
                    if not any(isinstance(e, exc_type) for exc_type in retryable_exceptions):
                        logger.error(f"Non-retryable exception type in {func.__name__}: {e}")
                        raise e
                    
                    # If this is the last attempt, raise the exception
                    if attempt == config.max_retries:
                        logger.error(f"Function {func.__name__} failed after {config.max_retries + 1} attempts: {e}")
                        raise e
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    
                    # Add jitter to avoid thundering herd
                    if config.jitter:
                        jitter_amount = delay * config.jitter_ratio
                        delay += random.uniform(-jitter_amount, jitter_amount)
                        delay = max(0, delay)  # Ensure delay is not negative
                    
                    logger.warning(
                        f"Function {func.__name__} failed on attempt {attempt + 1}/{config.max_retries + 1}: {e}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )
                    
                    time.sleep(delay)
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            
        return wrapper
    return decorator


# Predefined configurations for different use cases
OPENAI_RETRY_CONFIG = RetryConfig(
    max_retries=5,
    base_delay=2.0,
    max_delay=120.0,
    exponential_base=2.0,
    jitter=True,
    jitter_ratio=0.2,
)

# Common exception types for OpenAI API
OPENAI_RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,  # Network-related errors
)

OPENAI_NON_RETRYABLE_EXCEPTIONS = (
    ValueError,  # Invalid API key or parameters
    KeyError,    # Missing required parameters
)


def openai_retry(func: Callable) -> Callable:
    """
    Convenient decorator specifically for OpenAI API calls.
    """
    return smart_retry(
        config=OPENAI_RETRY_CONFIG,
        retryable_exceptions=OPENAI_RETRYABLE_EXCEPTIONS,
        non_retryable_exceptions=OPENAI_NON_RETRYABLE_EXCEPTIONS,
    )(func) 