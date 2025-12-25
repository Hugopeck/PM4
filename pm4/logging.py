"""
JSON Lines logging system for PM4 with enhanced debugging capabilities.
"""
import asyncio
import functools
import inspect
import json
import os
import time
from typing import Any, Callable, Dict, Optional

from .utils import now_ms


class JsonlLogger:
    """Structured JSON Lines logger for trading events."""

    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._fp = open(path, "a", buffering=1)

    def write(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Write a structured event to the log."""
        rec = {"ts_ms": now_ms(), "event": event_type, **payload}
        self._fp.write(json.dumps(rec, separators=(",", ":"), ensure_ascii=False) + "\n")

    def close(self) -> None:
        """Close the log file."""
        try:
            self._fp.close()
        except Exception:
            pass


class DebugLogger(JsonlLogger):
    """Enhanced logger with configurable log levels and debugging features."""

    LEVELS = {
        'DEBUG': 10,
        'INFO': 20,
        'WARNING': 30,
        'ERROR': 40,
        'CRITICAL': 50
    }

    def __init__(self, path: str, level: str = 'INFO'):
        super().__init__(path)
        self.level = self.LEVELS.get(level.upper(), self.LEVELS['INFO'])
        self._context_stack = []  # For future context tracking

    def debug(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Log debug-level events."""
        if self.level <= self.LEVELS['DEBUG']:
            self.write(f"debug_{event_type}", payload)

    def info(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Log info-level events (default behavior)."""
        if self.level <= self.LEVELS['INFO']:
            self.write(event_type, payload)

    def warning(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Log warning-level events."""
        if self.level <= self.LEVELS['WARNING']:
            self.write(f"warn_{event_type}", payload)

    def error(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Log error-level events."""
        if self.level <= self.LEVELS['ERROR']:
            self.write(f"error_{event_type}", payload)

    def critical(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Log critical-level events."""
        if self.level <= self.LEVELS['CRITICAL']:
            self.write(f"critical_{event_type}", payload)

    # Backward compatibility: keep the original write method behavior
    # but also provide level-based methods that existing code can migrate to


def performance_trace(logger_attr: str = 'logger'):
    """Decorator for automatic function timing. Only active when DEBUG level enabled.

    Args:
        logger_attr: Name of the logger attribute on the instance (default: 'logger')
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get logger from instance
            if not args:
                return await func(*args, **kwargs)
            instance = args[0]
            logger = getattr(instance, logger_attr, None)
            if not isinstance(logger, DebugLogger) or logger.level > DebugLogger.LEVELS['DEBUG']:
                return await func(*args, **kwargs)

            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.debug("perf_async_function", {
                    "function": f"{func.__module__}.{func.__qualname__}",
                    "duration_ms": round(duration_ms, 3),
                    "args_count": len(args) + len(kwargs)
                })
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.error("perf_function_error", {
                    "function": f"{func.__module__}.{func.__qualname__}",
                    "duration_ms": round(duration_ms, 3),
                    "error": str(e),
                    "error_type": type(e).__name__
                })
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Get logger from instance
            if not args:
                return func(*args, **kwargs)
            instance = args[0]
            logger = getattr(instance, logger_attr, None)
            if not isinstance(logger, DebugLogger) or logger.level > DebugLogger.LEVELS['DEBUG']:
                return func(*args, **kwargs)

            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.debug("perf_sync_function", {
                    "function": f"{func.__module__}.{func.__qualname__}",
                    "duration_ms": round(duration_ms, 3),
                    "args_count": len(args) + len(kwargs)
                })
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.error("perf_function_error", {
                    "function": f"{func.__module__}.{func.__qualname__}",
                    "duration_ms": round(duration_ms, 3),
                    "error": str(e),
                    "error_type": type(e).__name__
                })
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class ErrorContext:
    """Enhanced error logging with comprehensive context capture."""

    @staticmethod
    def capture_error(
        logger: DebugLogger,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        include_stack: bool = True
    ) -> None:
        """Log comprehensive error information with context."""

        import traceback

        # Get current function context
        frame = inspect.currentframe()
        function_name = "unknown"
        file_name = "unknown"
        line_number = 0

        try:
            # Go up the stack to find the actual error location
            caller_frame = frame
            for _ in range(3):  # Skip this method, caller, and logger call
                if caller_frame:
                    caller_frame = caller_frame.f_back

            if caller_frame:
                function_name = caller_frame.f_code.co_name
                file_name = caller_frame.f_code.co_filename
                line_number = caller_frame.f_lineno
        except AttributeError:
            # Frame inspection failed, use defaults
            pass
        finally:
            del frame

        error_payload = {
            "error_message": str(error),
            "error_type": type(error).__name__,
            "function": function_name,
            "file": file_name,
            "line": line_number,
            "timestamp": now_ms()
        }

        if include_stack:
            error_payload["stack_trace"] = traceback.format_exc()

        if context:
            error_payload["context"] = context

        # Always log errors regardless of level
        logger.error("detailed_error", error_payload)

    @staticmethod
    def log_operation_error(
        logger: DebugLogger,
        operation: str,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log operation-specific errors with enhanced context."""

        ErrorContext.capture_error(logger, error, {
            "operation": operation,
            **(context or {})
        })
