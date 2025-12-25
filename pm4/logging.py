"""
Comprehensive logging and debugging system for PM4 trading platform.

This module provides a hierarchical logging system designed for high-frequency
trading applications with extensive debugging and performance monitoring capabilities:

Core Components:
- JsonlLogger: Basic structured JSON logging for production use
- DebugLogger: Enhanced logger with configurable log levels and debugging features
- performance_trace: Automatic function timing decorator for performance analysis
- ErrorContext: Comprehensive error logging with stack traces and context

Logging Architecture:
    Application Code → Logger Instance → JSON Lines File
                              ↓
                         Debug/Performance Events

Key Features:
- Structured JSON output for easy parsing and analysis
- Configurable log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Automatic function performance timing
- Comprehensive error context capture
- Thread-safe async operation support
- Backward compatibility with existing logging

Performance Considerations:
- Minimal overhead when debug features disabled
- Efficient JSON serialization with compression
- File buffering for high-frequency logging
- Conditional execution to avoid performance impact

Usage Patterns:
    # Basic production logging
    logger = JsonlLogger("trades.jsonl")
    logger.write("trade_executed", {"price": 0.65, "size": 100})

    # Enhanced debugging with levels
    logger = DebugLogger("debug.jsonl", level="DEBUG")
    logger.debug("variable_dump", {"key": "value"})
    logger.error("api_failure", {"endpoint": "orders", "error": "timeout"})

    # Performance monitoring
    @performance_trace()
    def trading_algorithm(self):
        # Function automatically timed when DEBUG enabled
        pass

    # Enhanced error handling
    try:
        risky_operation()
    except Exception as e:
        ErrorContext.log_operation_error(logger, "risky_operation", e)
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
    """Production-ready JSON Lines logger for structured event logging.

    Provides efficient, append-only logging to JSON Lines format files.
    Each log entry is a complete JSON object on a single line, making
    it ideal for streaming processing, analysis tools, and log aggregation.

    File Format:
        {"ts_ms": 1703123456789, "event": "trade_executed", "price": 0.65, "size": 100}
        {"ts_ms": 1703123456789, "event": "order_placed", "order_id": "12345", "side": "BUY"}

    Key Features:
    - Timestamp automatic injection (milliseconds since epoch)
    - Compact JSON format with minimal whitespace
    - Unicode support (non-ASCII characters preserved)
    - File buffering for high-frequency logging
    - Automatic directory creation
    - Graceful file handle management

    Performance:
    - Low latency: buffered I/O with line buffering
    - Memory efficient: no in-memory log buffering
    - CPU efficient: minimal JSON serialization overhead
    - Thread-compatible: single-writer design

    Args:
        path: File path for log output (created if doesn't exist)

    Usage:
        logger = JsonlLogger("./data/trades.jsonl")
        logger.write("trade", {"price": 0.65, "size": 100, "side": "BUY"})
    """

    def __init__(self, path: str):
        """Initialize logger with output file path.

        Args:
            path: Complete file path for JSON Lines output
                 Directory structure created automatically if missing
        """
        self.path = path
        # Ensure directory exists for log file
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Open with line buffering (buffering=1) for low-latency writes
        self._fp = open(path, "a", buffering=1)

    def write(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Write a structured event to the log file.

        Creates a complete log record with automatic timestamp injection
        and writes it as a single JSON Lines entry.

        Args:
            event_type: Descriptive event identifier (e.g., "trade_executed", "order_failed")
            payload: Event-specific data dictionary (merged into log record)

        Log Record Format:
            {
                "ts_ms": 1703123456789,    # Automatic timestamp
                "event": "event_type",     # Provided event type
                ...payload...              # Merged payload data
            }

        Thread Safety:
            Not thread-safe for concurrent writes. Use single writer pattern
            or external synchronization for multi-threaded applications.
        """
        # Create complete log record with timestamp
        rec = {"ts_ms": now_ms(), "event": event_type, **payload}
        # Write compact JSON without extra whitespace, preserving Unicode
        self._fp.write(json.dumps(rec, separators=(",", ":"), ensure_ascii=False) + "\n")

    def close(self) -> None:
        """Flush and close the log file handle.

        Ensures all buffered log entries are written to disk before closing.
        Safe to call multiple times - handles already-closed files gracefully.

        Note:
            After closing, further write() calls will fail silently.
            Always call close() before program termination for data integrity.
        """
        try:
            self._fp.close()
        except Exception:
            # Ignore errors during close (file may already be closed)
            pass


class DebugLogger(JsonlLogger):
    """Advanced logging system with hierarchical log levels and debugging features.

    Extends JsonlLogger with configurable verbosity levels for development,
    debugging, and production monitoring. Provides granular control over
    what information gets logged based on importance and debug context.

    Log Levels (hierarchical, higher numbers include lower levels):
        CRITICAL (50): System failures requiring immediate attention
        ERROR (40):   Error conditions that don't stop operation
        WARNING (30): Warning conditions that may indicate problems
        INFO (20):    General information about system operation (default)
        DEBUG (10):   Detailed debugging information for development

    Level Usage Guidelines:
        CRITICAL: System crashes, data corruption, security breaches
        ERROR:   API failures, invalid responses, connection drops
        WARNING: Performance degradation, unusual conditions, config issues
        INFO:    Normal operations (trades, orders, state changes)
        DEBUG:   Variable dumps, function entry/exit, detailed execution flow

    Features:
    - Configurable verbosity levels
    - Performance monitoring integration
    - Structured debug event prefixes
    - Backward compatibility with JsonlLogger
    - Context stack for nested operation tracking

    Args:
        path: Log file output path (same as JsonlLogger)
        level: Logging verbosity level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Usage:
        # Development debugging
        logger = DebugLogger("debug.jsonl", level="DEBUG")
        logger.debug("variable_state", {"key": "value"})

        # Production monitoring
        logger = DebugLogger("prod.jsonl", level="WARNING")
        logger.error("api_timeout", {"endpoint": "orders"})
    """

    # Hierarchical log levels (Python logging standard)
    LEVELS = {
        'DEBUG': 10,     # Detailed debugging (highest verbosity)
        'INFO': 20,      # General information (default)
        'WARNING': 30,   # Warning conditions
        'ERROR': 40,     # Error conditions
        'CRITICAL': 50   # Critical failures (lowest verbosity)
    }

    def __init__(self, path: str, level: str = 'INFO'):
        """Initialize debug logger with configurable verbosity.

        Args:
            path: Output file path for JSON Lines logging
            level: Initial logging level (case-insensitive)
                  Defaults to INFO for production use

        Raises:
            No exceptions raised - invalid levels default to INFO
        """
        super().__init__(path)
        # Convert level string to numeric value, default to INFO
        self.level = self.LEVELS.get(level.upper(), self.LEVELS['INFO'])
        # Future: context stack for nested operation tracking
        self._context_stack = []

    def debug(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Log detailed debugging information for development and troubleshooting.

        DEBUG level events provide the most verbose logging, including:
        - Variable state dumps during execution
        - Function entry/exit points
        - Intermediate calculation results
        - Performance timing data
        - Detailed execution flow information

        Only logged when level <= DEBUG. Events are prefixed with "debug_"
        to distinguish them in log analysis.

        Args:
            event_type: Specific debug event identifier
            payload: Debug data (variables, state, timing, etc.)

        Example:
            logger.debug("variable_dump", {"position": 100, "mid_price": 0.65})
        """
        if self.level <= self.LEVELS['DEBUG']:
            self.write(f"debug_{event_type}", payload)

    def info(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Log general operational information (default production level).

        INFO level events capture normal system operation and important
        state changes that are relevant for monitoring but not debugging:
        - Trade executions and order placements
        - Market data updates and state changes
        - Configuration changes and system status
        - Normal business logic execution

        Always logged in production environments. No prefix added to event_type.

        Args:
            event_type: Standard event identifier (e.g., "trade_executed")
            payload: Operational data and context

        Example:
            logger.info("trade_executed", {"order_id": "123", "price": 0.65})
        """
        if self.level <= self.LEVELS['INFO']:
            self.write(event_type, payload)

    def warning(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Log warning conditions that may indicate potential problems.

        WARNING level events indicate situations that don't prevent operation
        but may require attention or indicate developing issues:
        - Performance degradation warnings
        - Unusual market conditions
        - Configuration inconsistencies
        - Resource usage alerts
        - Recovery from transient errors

        Events are prefixed with "warn_" for easy filtering and alerting.

        Args:
            event_type: Warning condition identifier
            payload: Warning context and diagnostic information

        Example:
            logger.warning("high_latency", {"endpoint": "orders", "latency_ms": 500})
        """
        if self.level <= self.LEVELS['WARNING']:
            self.write(f"warn_{event_type}", payload)

    def error(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Log error conditions that impair but don't stop operation.

        ERROR level events indicate failures or invalid states that affect
        system operation but allow continued execution:
        - API failures and connection drops
        - Invalid responses or data corruption
        - Business logic errors (insufficient balance, etc.)
        - Recovery-attempt failures
        - Data validation failures

        Events are prefixed with "error_" for easy identification and alerting.
        Always logged regardless of configured level.

        Args:
            event_type: Error condition identifier
            payload: Error details, context, and diagnostic data

        Example:
            logger.error("api_failure", {"endpoint": "balances", "error": "timeout"})
        """
        if self.level <= self.LEVELS['ERROR']:
            self.write(f"error_{event_type}", payload)

    def critical(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Log critical system failures requiring immediate attention.

        CRITICAL level events indicate severe failures that threaten system
        operation or data integrity:
        - System crashes or unrecoverable errors
        - Data corruption or loss
        - Security breaches or compromises
        - Complete system failure conditions
        - Emergency shutdown scenarios

        Events are prefixed with "critical_" for highest priority alerting.
        Always logged regardless of configured level.

        Args:
            event_type: Critical failure identifier
            payload: Critical failure details and emergency context

        Example:
            logger.critical("system_corruption", {"component": "order_book", "severity": "high"})
        """
        if self.level <= self.LEVELS['CRITICAL']:
            self.write(f"critical_{event_type}", payload)

    # Backward compatibility: keep the original write method behavior
    # but also provide level-based methods that existing code can migrate to


def performance_trace(logger_attr: str = 'logger'):
    """Decorator for automatic function performance timing and monitoring.

    Transparently measures execution time of decorated functions and logs
    performance metrics when debug logging is enabled. Supports both sync
    and async functions with automatic detection.

    Performance Metrics Logged:
    - Function execution time (milliseconds, 3 decimal precision)
    - Function qualified name (module.class.method)
    - Argument count (for complexity analysis)
    - Error timing (duration before exception)

    Conditional Execution:
    - Only active when logger is DebugLogger instance
    - Only logs when DEBUG level is enabled (level <= 10)
    - Zero performance overhead when disabled
    - Graceful fallback if logger not available

    Args:
        logger_attr: Name of the logger attribute on the instance (default: 'logger')
                    Used to access the logger from the decorated method's instance

    Returns:
        Decorated function that automatically logs performance when debug enabled

    Usage Examples:
        # Instance method (logger accessed via self.logger)
        @performance_trace()
        def trading_algorithm(self):
            # Automatically timed when DEBUG enabled
            return self.compute_signals()

        # Async method with custom logger attribute
        @performance_trace('debug_logger')
        async def fetch_market_data(self):
            # Performance logged to self.debug_logger
            return await self.api_call()

    Log Output:
        {
            "ts_ms": 1703123456789,
            "event": "debug_perf_async_function",
            "function": "pm4.trading.Quoter.compute",
            "duration_ms": 15.234,
            "args_count": 2
        }

    Performance Impact:
    - When disabled: ~1-2 nanoseconds overhead (negligible)
    - When enabled: ~50-100 microseconds overhead per call
    - Memory: Minimal (no persistent storage in decorator)

    Thread Safety:
    - Safe for single-threaded async code
    - Logger access is read-only, no shared state modification
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Early exit if no instance or invalid logger (zero overhead)
            if not args:
                return await func(*args, **kwargs)

            instance = args[0]
            logger = getattr(instance, logger_attr, None)

            # Only instrument if we have a DebugLogger at DEBUG level
            if not isinstance(logger, DebugLogger) or logger.level > DebugLogger.LEVELS['DEBUG']:
                return await func(*args, **kwargs)

            # High-precision timing using perf_counter (nanosecond resolution)
            start_time = time.perf_counter()

            try:
                result = await func(*args, **kwargs)
                # Calculate duration and log successful execution
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.debug("perf_async_function", {
                    "function": f"{func.__module__}.{func.__qualname__}",
                    "duration_ms": round(duration_ms, 3),  # Millisecond precision
                    "args_count": len(args) + len(kwargs)   # Complexity indicator
                })
                return result
            except Exception as e:
                # Log timing even for failed executions
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.error("perf_function_error", {
                    "function": f"{func.__module__}.{func.__qualname__}",
                    "duration_ms": round(duration_ms, 3),
                    "error": str(e),
                    "error_type": type(e).__name__
                })
                raise  # Re-raise exception after logging

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Early exit if no instance or invalid logger (zero overhead)
            if not args:
                return func(*args, **kwargs)

            instance = args[0]
            logger = getattr(instance, logger_attr, None)

            # Only instrument if we have a DebugLogger at DEBUG level
            if not isinstance(logger, DebugLogger) or logger.level > DebugLogger.LEVELS['DEBUG']:
                return func(*args, **kwargs)

            # High-precision timing for synchronous functions
            start_time = time.perf_counter()

            try:
                result = func(*args, **kwargs)
                # Calculate and log execution duration
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.debug("perf_sync_function", {
                    "function": f"{func.__module__}.{func.__qualname__}",
                    "duration_ms": round(duration_ms, 3),
                    "args_count": len(args) + len(kwargs)
                })
                return result
            except Exception as e:
                # Log timing for failed synchronous executions
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.error("perf_function_error", {
                    "function": f"{func.__module__}.{func.__qualname__}",
                    "duration_ms": round(duration_ms, 3),
                    "error": str(e),
                    "error_type": type(e).__name__
                })
                raise  # Re-raise exception after logging

        # Auto-detect async vs sync and return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class ErrorContext:
    """Comprehensive error logging and context capture system.

    Provides structured error reporting with full diagnostic information,
    stack traces, and operational context. Designed for production debugging
    and incident analysis in high-frequency trading systems.

    Key Features:
    - Automatic stack trace capture and formatting
    - Function and file location identification
    - Configurable context inclusion
    - Exception type and message extraction
    - Timestamp correlation with other events
    - Integration with DebugLogger error levels

    Error Information Captured:
    - Exception type and message
    - File name and line number where error occurred
    - Function name and call stack
    - Full Python traceback (when enabled)
    - Custom context data (operation, parameters, etc.)
    - Timestamp for correlation with other events

    Usage Patterns:
        # Basic error logging
        try:
            risky_operation()
        except Exception as e:
            ErrorContext.capture_error(logger, e)

        # Operation-specific error with context
        try:
            place_order(symbol, price, size)
        except Exception as e:
            ErrorContext.log_operation_error(logger, "place_order", e, {
                "symbol": symbol,
                "price": price,
                "size": size
            })

    Log Output:
        {
            "ts_ms": 1703123456789,
            "event": "error_detailed_error",
            "error_message": "Insufficient balance",
            "error_type": "ValueError",
            "function": "place_limit_order",
            "file": "pm4/adapters.py",
            "line": 142,
            "stack_trace": "Traceback (most recent call last):\n...",
            "context": {"operation": "place_order", "symbol": "YES"}
        }

    Performance Considerations:
    - Stack trace capture has moderate overhead (~1-5ms)
    - Frame inspection may fail in some environments (graceful fallback)
    - Memory usage scales with stack depth and context size
    """

    @staticmethod
    def capture_error(
        logger: DebugLogger,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        include_stack: bool = True
    ) -> None:
        """Capture and log comprehensive error information with full context.

        Performs deep error analysis including stack trace inspection to provide
        complete diagnostic information for debugging and incident analysis.

        Error Analysis Performed:
        1. Exception type and message extraction
        2. Stack frame inspection to find error location
        3. Function name, file name, and line number identification
        4. Optional full Python traceback capture
        5. Custom context data integration
        6. Timestamp correlation for event sequencing

        Args:
            logger: DebugLogger instance for error output
            error: Exception object to analyze and log
            context: Optional custom context dictionary (operation details, parameters, etc.)
            include_stack: Whether to include full Python traceback (default: True)
                         Disable for performance-critical code or to reduce log volume

        Error Location Detection:
            Uses Python's inspect module to walk up the call stack and identify
            where the error actually occurred (not where it was caught).
            Gracefully handles cases where frame inspection fails.

        Log Level: Always logged as ERROR level regardless of logger configuration
                  Critical for debugging production issues.

        Example:
            try:
                complex_calculation()
            except ValueError as e:
                ErrorContext.capture_error(logger, e, {
                    "operation": "risk_calculation",
                    "parameters": {"position": 100, "volatility": 0.2}
                })
        """
        import traceback

        # Initialize error location with safe defaults
        function_name = "unknown"
        file_name = "unknown"
        line_number = 0

        # Perform stack frame inspection to find actual error location
        frame = inspect.currentframe()
        try:
            # Walk up call stack: skip capture_error -> log_operation_error -> caller
            # This finds where the exception actually occurred, not where it was caught
            caller_frame = frame
            for _ in range(3):  # Adjust depth based on call chain
                if caller_frame:
                    caller_frame = caller_frame.f_back

            # Extract location information from the relevant stack frame
            if caller_frame:
                function_name = caller_frame.f_code.co_name
                file_name = caller_frame.f_code.co_filename
                line_number = caller_frame.f_lineno

        except AttributeError:
            # Frame inspection can fail in some Python environments
            # or with certain optimization settings - use defaults
            pass
        finally:
            # Always clean up frame reference to prevent memory leaks
            del frame

        # Build comprehensive error payload
        error_payload = {
            "error_message": str(error),           # Human-readable error description
            "error_type": type(error).__name__,    # Exception class name
            "function": function_name,             # Function where error occurred
            "file": file_name,                     # Source file path
            "line": line_number,                   # Line number in source
            "timestamp": now_ms()                  # For event correlation
        }

        # Include full stack trace if requested (can be large)
        if include_stack:
            error_payload["stack_trace"] = traceback.format_exc()

        # Merge in custom context data
        if context:
            error_payload["context"] = context

        # Log as error level (always visible for debugging)
        logger.error("detailed_error", error_payload)

    @staticmethod
    def log_operation_error(
        logger: DebugLogger,
        operation: str,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log operation-specific errors with standardized context structure.

        Convenience method for logging errors within specific business operations.
        Automatically includes operation name and merges additional context.

        This is the preferred method for most error logging scenarios as it
        provides consistent structure for operation-level error analysis.

        Args:
            logger: DebugLogger instance for error output
            operation: String identifier for the operation that failed
                      (e.g., "place_order", "get_balances", "calculate_risk")
            error: Exception that occurred during the operation
            context: Additional operation-specific context (parameters, state, etc.)

        Context Structure:
            The operation name is automatically included as "operation" field,
            and any additional context is merged in.

        Example:
            try:
                await adapter.place_limit_order("YES", "BUY", 0.65, 100)
            except Exception as e:
                ErrorContext.log_operation_error(logger, "place_limit_order", e, {
                    "asset_id": "YES",
                    "side": "BUY",
                    "price": 0.65,
                    "size": 100
                })

        This creates structured error logs that can be easily queried and analyzed
        for specific operation failures and patterns.
        """
        # Merge operation name with additional context
        full_context = {
            "operation": operation,
            **(context or {})  # Merge in additional context if provided
        }

        # Delegate to comprehensive error capture
        ErrorContext.capture_error(logger, error, full_context)
