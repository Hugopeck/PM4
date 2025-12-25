"""
Tests for logging functionality in pm4/logging.py.

Tests cover:
- JsonlLogger basic functionality
- DebugLogger enhanced features
- performance_trace decorator
- ErrorContext logging
- File I/O and JSON formatting
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pm4.logging import DebugLogger, ErrorContext, JsonlLogger, performance_trace
from pm4.utils import now_ms


class TestJsonlLogger:
    """Test JsonlLogger basic functionality."""

    @pytest.mark.unit
    def test_jsonl_logger_creation(self, temp_dir):
        """Test creating a JsonlLogger instance."""
        log_path = temp_dir / "test_log.jsonl"
        logger = JsonlLogger(str(log_path))

        assert logger.path == str(log_path)
        assert log_path.exists()  # File should be created

    @pytest.mark.unit
    def test_jsonl_logger_write_basic(self, temp_dir):
        """Test basic write functionality."""
        log_path = temp_dir / "test_log.jsonl"
        logger = JsonlLogger(str(log_path))

        # Write a simple event
        logger.write("test_event", {"key": "value", "number": 42})

        # Check file contents
        with open(log_path, 'r') as f:
            lines = f.readlines()

        assert len(lines) == 1
        entry = json.loads(lines[0])

        assert "ts_ms" in entry
        assert entry["event"] == "test_event"
        assert entry["key"] == "value"
        assert entry["number"] == 42

    @pytest.mark.unit
    def test_jsonl_logger_write_multiple_events(self, temp_dir):
        """Test writing multiple events."""
        log_path = temp_dir / "test_log.jsonl"
        logger = JsonlLogger(str(log_path))

        # Write multiple events
        logger.write("event1", {"data": "first"})
        logger.write("event2", {"data": "second"})
        logger.write("event3", {"data": "third"})

        # Check file contents
        with open(log_path, 'r') as f:
            lines = f.readlines()

        assert len(lines) == 3

        for i, line in enumerate(lines):
            entry = json.loads(line)
            assert entry["event"] == f"event{i+1}"
            assert entry["data"] == ["first", "second", "third"][i]

    @pytest.mark.unit
    def test_jsonl_logger_timestamp_injection(self, temp_dir):
        """Test that timestamps are automatically injected."""
        log_path = temp_dir / "test_log.jsonl"
        logger = JsonlLogger(str(log_path))

        before_write = now_ms()
        logger.write("test", {"data": "value"})
        after_write = now_ms()

        with open(log_path, 'r') as f:
            entry = json.loads(f.readline())

        assert "ts_ms" in entry
        assert before_write <= entry["ts_ms"] <= after_write

    @pytest.mark.unit
    def test_jsonl_logger_unicode_support(self, temp_dir):
        """Test Unicode character support in logging."""
        log_path = temp_dir / "test_log.jsonl"
        logger = JsonlLogger(str(log_path))

        # Test various Unicode characters
        logger.write("unicode_test", {
            "emoji": "🚀",
            "accented": "café",
            "chinese": "你好",
            "math": "∑∆∏"
        })

        with open(log_path, 'r', encoding='utf-8') as f:
            entry = json.loads(f.readline())

        assert entry["emoji"] == "🚀"
        assert entry["accented"] == "café"
        assert entry["chinese"] == "你好"
        assert entry["math"] == "∑∆∏"

    @pytest.mark.unit
    def test_jsonl_logger_complex_data_types(self, temp_dir):
        """Test logging complex data types."""
        log_path = temp_dir / "test_log.jsonl"
        logger = JsonlLogger(str(log_path))

        complex_data = {
            "list": [1, 2, 3, "string"],
            "dict": {"nested": {"key": "value"}},
            "float": 3.14159,
            "bool": True,
            "none": None,
        }

        logger.write("complex", complex_data)

        with open(log_path, 'r') as f:
            entry = json.loads(f.readline())

        assert entry["list"] == [1, 2, 3, "string"]
        assert entry["dict"]["nested"]["key"] == "value"
        assert entry["float"] == 3.14159
        assert entry["bool"] is True
        assert entry["none"] is None


class TestDebugLogger:
    """Test DebugLogger enhanced functionality."""

    @pytest.mark.unit
    def test_debug_logger_creation(self, temp_dir):
        """Test creating a DebugLogger instance."""
        log_path = temp_dir / "debug_log.jsonl"
        logger = DebugLogger(str(log_path), level="DEBUG")

        assert logger.path == str(log_path)
        assert logger.level == "DEBUG"
        assert logger.enable_performance is False
        assert logger.enable_context is False

    @pytest.mark.unit
    def test_debug_logger_log_levels(self, temp_dir):
        """Test different log levels."""
        log_path = temp_dir / "debug_log.jsonl"
        logger = DebugLogger(str(log_path), level="INFO")

        # These should all write since they're at or above INFO
        logger.info("info_event", {"data": "info"})
        logger.warning("warn_event", {"data": "warn"})
        logger.error("error_event", {"data": "error"})
        logger.critical("critical_event", {"data": "critical"})

        # This should not write since DEBUG is below INFO
        logger.debug("debug_event", {"data": "debug"})

        with open(log_path, 'r') as f:
            lines = f.readlines()

        # Should have 4 entries (all except debug)
        assert len(lines) == 4

        events = [json.loads(line)["event"] for line in lines]
        assert "info_event" in events
        assert "warn_event" in events
        assert "error_event" in events
        assert "critical_event" in events
        assert "debug_event" not in events

    @pytest.mark.unit
    def test_debug_logger_debug_level(self, temp_dir):
        """Test DEBUG level logging."""
        log_path = temp_dir / "debug_log.jsonl"
        logger = DebugLogger(str(log_path), level="DEBUG")

        logger.debug("debug_event", {"data": "debug"})
        logger.info("info_event", {"data": "info"})

        with open(log_path, 'r') as f:
            lines = f.readlines()

        assert len(lines) == 2

        events = [json.loads(line)["event"] for line in lines]
        assert "debug_event" in events
        assert "info_event" in events

    @pytest.mark.unit
    def test_debug_logger_performance_enabled(self, temp_dir):
        """Test performance logging when enabled."""
        log_path = temp_dir / "perf_log.jsonl"
        logger = DebugLogger(str(log_path), level="INFO", enable_performance=True)

        # Performance events should be logged
        logger.write("test", {"data": "value"})

        with open(log_path, 'r') as f:
            lines = f.readlines()

        assert len(lines) >= 1  # At least the main event

        # Check for performance-related entries
        events = [json.loads(line)["event"] for line in lines]
        assert "test" in events

    @pytest.mark.unit
    def test_debug_logger_context_enabled(self, temp_dir):
        """Test context tracking when enabled."""
        log_path = temp_dir / "context_log.jsonl"
        logger = DebugLogger(str(log_path), level="INFO", enable_context_tracking=True)

        logger.write("test", {"data": "value"})

        with open(log_path, 'r') as f:
            lines = f.readlines()

        assert len(lines) >= 1

        # Context tracking might add additional metadata to events
        entry = json.loads(lines[0])
        assert "event" in entry
        assert "ts_ms" in entry


class TestPerformanceTrace:
    """Test performance_trace decorator."""

    @pytest.mark.unit
    def test_performance_trace_decorator(self, temp_dir):
        """Test that performance_trace decorator works."""
        log_path = temp_dir / "perf_trace_log.jsonl"
        logger = DebugLogger(str(log_path), level="DEBUG", enable_performance=True)

        @performance_trace(logger)
        def dummy_function():
            return 42

        result = dummy_function()
        assert result == 42

        # Check that performance data was logged
        with open(log_path, 'r') as f:
            lines = f.readlines()

        # Should have performance logging entries
        assert len(lines) > 0

        # Look for performance-related events
        events = [json.loads(line)["event"] for line in lines]
        assert any("performance" in event.lower() or "trace" in event.lower() for event in events)

    @pytest.mark.unit
    def test_performance_trace_execution_time(self, temp_dir):
        """Test that performance trace captures execution time."""
        log_path = temp_dir / "perf_time_log.jsonl"
        logger = DebugLogger(str(log_path), level="DEBUG", enable_performance=True)

        @performance_trace(logger)
        def slow_function():
            import time
            time.sleep(0.01)  # Sleep for 10ms
            return "done"

        result = slow_function()
        assert result == "done"

        with open(log_path, 'r') as f:
            lines = f.readlines()

        # Look for execution time data
        found_performance = False
        for line in lines:
            entry = json.loads(line)
            if "duration_ms" in entry or "execution_time" in str(entry).lower():
                found_performance = True
                # Should have reasonable execution time (> 10ms due to sleep)
                duration = entry.get("duration_ms", entry.get("execution_time_ms", 0))
                assert duration >= 10  # At least 10ms from sleep

        assert found_performance, "Performance trace should have logged execution time"


class TestErrorContext:
    """Test ErrorContext error logging."""

    @pytest.mark.unit
    def test_error_context_log_operation_error(self, temp_dir):
        """Test logging operation errors with context."""
        log_path = temp_dir / "error_log.jsonl"
        logger = DebugLogger(str(log_path), level="ERROR")

        try:
            raise ValueError("Test error")
        except Exception as e:
            ErrorContext.log_operation_error(logger, "test_operation", e)

        with open(log_path, 'r') as f:
            lines = f.readlines()

        assert len(lines) > 0

        # Check for error logging
        found_error = False
        for line in lines:
            entry = json.loads(line)
            if "error" in entry or "exception" in str(entry).lower():
                found_error = True
                assert "test_operation" in str(entry)
                assert "Test error" in str(entry)

        assert found_error, "Error context should have logged the exception"

    @pytest.mark.unit
    def test_error_context_with_stack_trace(self, temp_dir):
        """Test that error context captures stack traces."""
        log_path = temp_dir / "stack_trace_log.jsonl"
        logger = DebugLogger(str(log_path), level="ERROR")

        def nested_function():
            raise RuntimeError("Nested error")

        try:
            nested_function()
        except Exception as e:
            ErrorContext.log_operation_error(logger, "nested_call", e)

        with open(log_path, 'r') as f:
            lines = f.readlines()

        assert len(lines) > 0

        # Check for stack trace information
        found_stack = False
        for line in lines:
            entry = json.loads(line)
            error_info = str(entry)
            if "traceback" in error_info.lower() or "stack" in error_info.lower() or "nested_function" in error_info:
                found_stack = True

        assert found_stack, "Error context should include stack trace information"


class TestLoggerFileOperations:
    """Test file operations and edge cases."""

    @pytest.mark.unit
    def test_logger_directory_creation(self, temp_dir):
        """Test that logger creates necessary directories."""
        nested_path = temp_dir / "nested" / "deep" / "log.jsonl"
        logger = JsonlLogger(str(nested_path))

        assert nested_path.exists()
        assert nested_path.parent.exists()

    @pytest.mark.unit
    def test_logger_buffering(self, temp_dir):
        """Test that logger properly buffers writes."""
        log_path = temp_dir / "buffer_test.jsonl"
        logger = JsonlLogger(str(log_path))

        # Write many events quickly
        for i in range(100):
            logger.write(f"event_{i}", {"index": i})

        # Force buffer flush by checking file
        import os
        os.fsync(logger.fp.fileno())  # Force write to disk

        with open(log_path, 'r') as f:
            lines = f.readlines()

        assert len(lines) == 100

        # Verify all events are present
        for i, line in enumerate(lines):
            entry = json.loads(line)
            assert entry["event"] == f"event_{i}"
            assert entry["index"] == i

    @pytest.mark.unit
    def test_logger_file_reopening(self, temp_dir):
        """Test logger behavior when file is reopened."""
        log_path = temp_dir / "reopen_test.jsonl"

        logger1 = JsonlLogger(str(log_path))
        logger1.write("event1", {"data": "first"})
        # Logger1 goes out of scope, file should be closed

        logger2 = JsonlLogger(str(log_path))
        logger2.write("event2", {"data": "second"})

        with open(log_path, 'r') as f:
            lines = f.readlines()

        assert len(lines) == 2

        events = [json.loads(line)["event"] for line in lines]
        assert "event1" in events
        assert "event2" in events
