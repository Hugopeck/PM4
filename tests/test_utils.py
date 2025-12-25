"""
Tests for utility functions in pm4/utils.py.

Tests cover:
- Mathematical functions (logit, sigmoid, clip)
- Time utilities (now_ms)
- Price rounding functions (floor_to_tick, ceil_to_tick)
- Formatting utilities (fmt)
"""
import math
import time
from unittest.mock import patch

import pytest

from pm4.utils import ceil_to_tick, clip, floor_to_tick, fmt, logit, now_ms, sigmoid


class TestTimeUtils:
    """Test time-related utility functions."""

    @pytest.mark.unit
    def test_now_ms_returns_integer(self):
        """Test that now_ms returns an integer timestamp in milliseconds."""
        result = now_ms()
        assert isinstance(result, int)
        assert result > 0

    @pytest.mark.unit
    def test_now_ms_reasonable_range(self):
        """Test that now_ms returns a timestamp in a reasonable range."""
        result = now_ms()
        # Should be roughly current time in milliseconds
        current_time_ms = int(time.time() * 1000)
        # Allow for some test execution time difference
        assert abs(result - current_time_ms) < 10000  # Within 10 seconds


class TestClipping:
    """Test value clipping functionality."""

    @pytest.mark.unit
    @pytest.mark.parametrize("value,lo,hi,expected", [
        (5.0, 0.0, 10.0, 5.0),  # Value within range
        (-1.0, 0.0, 10.0, 0.0),  # Value below range
        (15.0, 0.0, 10.0, 10.0),  # Value above range
        (0.0, 0.0, 10.0, 0.0),  # Value at lower bound
        (10.0, 0.0, 10.0, 10.0),  # Value at upper bound
    ])
    def test_clip_basic_cases(self, value, lo, hi, expected):
        """Test clipping with various input values."""
        assert clip(value, lo, hi) == expected

    @pytest.mark.unit
    def test_clip_edge_cases(self):
        """Test clipping with edge cases."""
        # Very small ranges
        assert clip(1.0, 1.0, 1.0) == 1.0
        # Negative ranges
        assert clip(5.0, -10.0, -5.0) == -5.0
        # Large numbers
        assert clip(1e10, 0.0, 1e9) == 1e9


class TestLogitSigmoid:
    """Test logit and sigmoid transformation functions."""

    @pytest.mark.unit
    @pytest.mark.parametrize("p,expected_logit", [
        (0.5, 0.0),  # Neutral probability
        (0.6, pytest.approx(0.405465, abs=1e-6)),  # Slightly above neutral
        (0.4, pytest.approx(-0.405465, abs=1e-6)),  # Slightly below neutral
        (0.9, pytest.approx(2.197224, abs=1e-6)),  # High probability
        (0.1, pytest.approx(-2.197224, abs=1e-6)),  # Low probability
    ])
    def test_logit_standard_values(self, p, expected_logit):
        """Test logit function with standard probability values."""
        assert logit(p) == expected_logit

    @pytest.mark.unit
    def test_logit_edge_cases(self):
        """Test logit function with edge cases."""
        # Test boundary values with epsilon clipping
        eps = 1e-6
        # eps is much smaller than 0.001, so logit(eps) should be much more negative
        assert logit(eps) < logit(0.001)
        assert logit(eps) < -10.0  # Should be very negative
        # 1.0 - eps is much closer to 1.0 than 0.999 is, so logit should be much more positive
        assert logit(1.0 - eps) > logit(0.999)
        assert logit(1.0 - eps) > 10.0  # Should be very positive

        # Test extreme values
        assert logit(0.001) < -5.0  # Should be very negative
        assert logit(0.999) > 5.0   # Should be very positive

    @pytest.mark.unit
    def test_logit_sigmoid_inverse(self):
        """Test that logit and sigmoid are approximate inverses."""
        test_values = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

        for p in test_values:
            # sigmoid(logit(p)) should be approximately p
            reconstructed = sigmoid(logit(p))
            assert reconstructed == pytest.approx(p, abs=1e-6)

    @pytest.mark.unit
    @pytest.mark.parametrize("x,expected_sigmoid", [
        (0.0, 0.5),  # Neutral logit
        (1.0, pytest.approx(0.731058, abs=1e-6)),  # Positive logit
        (-1.0, pytest.approx(0.268941, abs=1e-6)),  # Negative logit
        (2.0, pytest.approx(0.880797, abs=1e-6)),  # Large positive
        (-2.0, pytest.approx(0.119202, abs=1e-6)),  # Large negative
    ])
    def test_sigmoid_standard_values(self, x, expected_sigmoid):
        """Test sigmoid function with standard logit values."""
        assert sigmoid(x) == expected_sigmoid

    @pytest.mark.unit
    def test_sigmoid_bounds(self):
        """Test that sigmoid always returns values in (0, 1)."""
        test_values = [-10.0, -5.0, -1.0, 0.0, 1.0, 5.0, 10.0]

        for x in test_values:
            result = sigmoid(x)
            assert 0.0 < result < 1.0

    @pytest.mark.unit
    def test_sigmoid_extremes(self):
        """Test sigmoid behavior at extremes."""
        # Very negative values should approach 0
        assert sigmoid(-10.0) < 0.01
        # Very positive values should approach 1
        assert sigmoid(10.0) > 0.99


class TestTickRounding:
    """Test price rounding to tick size functions."""

    @pytest.mark.unit
    @pytest.mark.parametrize("price,tick,expected", [
        (0.654, 0.01, 0.65),  # Standard rounding down
        (0.659, 0.01, 0.65),  # Rounds down to nearest tick
        (0.651, 0.01, 0.65),  # Already at tick boundary
        (0.655, 0.005, 0.655),  # Smaller tick size
        (1.23456, 0.001, 1.234),  # Higher precision
    ])
    def test_floor_to_tick(self, price, tick, expected):
        """Test floor_to_tick function with various prices and tick sizes."""
        assert floor_to_tick(price, tick) == expected

    @pytest.mark.unit
    @pytest.mark.parametrize("price,tick,expected", [
        (0.654, 0.01, 0.66),  # Standard rounding up
        (0.659, 0.01, 0.66),  # Rounds up to nearest tick
        (0.651, 0.01, 0.66),  # Rounds up from tick boundary
        (0.655, 0.005, 0.655),  # Smaller tick size
        (1.23456, 0.001, 1.235),  # Higher precision
    ])
    def test_ceil_to_tick(self, price, tick, expected):
        """Test ceil_to_tick function with various prices and tick sizes."""
        assert ceil_to_tick(price, tick) == expected

    @pytest.mark.unit
    def test_tick_rounding_edge_cases(self):
        """Test tick rounding with edge cases."""
        # Zero price
        assert floor_to_tick(0.0, 0.01) == 0.0
        assert ceil_to_tick(0.0, 0.01) == 0.0

        # Very small tick sizes
        assert floor_to_tick(0.123456, 0.0001) == pytest.approx(0.1234, abs=1e-10)

        # Large tick sizes
        assert floor_to_tick(0.5, 0.1) == 0.5
        assert ceil_to_tick(0.5, 0.1) == 0.5

    @pytest.mark.unit
    def test_tick_rounding_consistency(self):
        """Test that floor and ceil are consistent."""
        test_cases = [(0.654, 0.01), (0.123456, 0.001), (0.987654, 0.005)]

        for price, tick in test_cases:
            floor_result = floor_to_tick(price, tick)
            ceil_result = ceil_to_tick(price, tick)

            # Floor should be <= ceil
            assert floor_result <= ceil_result

            # Difference should be exactly one tick or zero (with floating point tolerance)
            diff = ceil_result - floor_result
            assert diff == pytest.approx(0.0, abs=1e-10) or diff == pytest.approx(tick, abs=1e-10)


class TestFormatting:
    """Test number formatting utilities."""

    @pytest.mark.unit
    @pytest.mark.parametrize("value,nd,expected", [
        (3.14159, 2, "3.14"),
        (3.14159, 4, "3.1416"),  # Rounds correctly
        (100.0, 0, "100"),
        (0.001234, 6, "0.001234"),
        (1.234567, 3, "1.235"),  # Rounds up
    ])
    def test_fmt_basic_formatting(self, value, nd, expected):
        """Test fmt function with various decimal places."""
        assert fmt(value, nd) == expected

    @pytest.mark.unit
    def test_fmt_integer_values(self):
        """Test fmt with integer inputs."""
        assert fmt(42, 2) == "42.00"
        assert fmt(100, 0) == "100"

    @pytest.mark.unit
    def test_fmt_negative_values(self):
        """Test fmt with negative values."""
        assert fmt(-3.14159, 2) == "-3.14"
        assert fmt(-0.001, 3) == "-0.001"

    @pytest.mark.unit
    def test_fmt_edge_cases(self):
        """Test fmt with edge cases."""
        # Very small numbers
        assert fmt(1e-10, 10) == "0.0000000001"

        # Very large numbers
        assert fmt(1e6, 2) == "1000000.00"

        # Zero
        assert fmt(0.0, 2) == "0.00"

        # Default decimal places
        assert fmt(3.14159) == "3.1416"  # Default nd=4
