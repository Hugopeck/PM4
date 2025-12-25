"""
Tests for market data processing in pm4/market_data.py.

Tests cover:
- MarketData class initialization
- WebSocket message processing (book, price_change, tick_size_change, last_trade_price)
- Order book state management
- Trade rate calculations
- Midpoint price updates
- Logging integration
"""
from unittest.mock import MagicMock, patch

import pytest

from pm4.market_data import BookState, MarketData


class TestBookState:
    """Test BookState dataclass."""

    @pytest.mark.unit
    def test_book_state_defaults(self):
        """Test BookState default values."""
        state = BookState()

        assert state.best_bid == 0.0
        assert state.best_ask == 1.0
        assert state.mid == 0.5
        assert state.tick_size == 0.01
        assert state.last_trade_price is None
        assert state.last_book_ts_ms == 0
        assert state.last_trade_ts_ms == 0

    @pytest.mark.unit
    def test_book_state_custom_values(self):
        """Test BookState with custom values."""
        state = BookState(
            best_bid=0.45,
            best_ask=0.55,
            tick_size=0.001,
            last_trade_price=0.48,
            last_book_ts_ms=1703123456789,
            last_trade_ts_ms=1703123456789,
        )

        assert state.best_bid == 0.45
        assert state.best_ask == 0.55
        assert state.mid == 0.5  # Should be calculated as (0.45 + 0.55) / 2
        assert state.tick_size == 0.001
        assert state.last_trade_price == 0.48
        assert state.last_book_ts_ms == 1703123456789
        assert state.last_trade_ts_ms == 1703123456789


class TestMarketData:
    """Test MarketData class functionality."""

    @pytest.mark.unit
    def test_market_data_initialization(self, mock_logger):
        """Test MarketData initialization."""
        md = MarketData(mock_logger)

        assert md.logger == mock_logger
        assert len(md.trade_ts) == 0
        assert md.trade_ts.maxlen == 5000

        # Check initial state
        assert md.state.best_bid == 0.0
        assert md.state.best_ask == 1.0
        assert md.state.mid == 0.5

    @pytest.mark.unit
    def test_update_mid_valid_prices(self, mock_logger):
        """Test midpoint calculation with valid prices."""
        md = MarketData(mock_logger)

        # Set valid bid/ask prices
        md.state.best_bid = 0.45
        md.state.best_ask = 0.55
        md._update_mid()

        assert md.state.mid == 0.5

    @pytest.mark.unit
    def test_update_mid_invalid_prices(self, mock_logger):
        """Test midpoint calculation with invalid prices."""
        md = MarketData(mock_logger)

        # Set invalid prices (bid >= ask)
        md.state.best_bid = 0.6
        md.state.best_ask = 0.5
        md._update_mid()

        # Mid should not be updated (remains default)
        assert md.state.mid == 0.5

        # Test boundary conditions - bid = 0.0 (not > 0)
        md.state.best_bid = 0.0  # At boundary, invalid
        md.state.best_ask = 0.1
        md._update_mid()

        # Should NOT update since bid is not > 0
        assert md.state.mid == 0.5

        # Test valid boundary conditions
        md.state.best_bid = 0.001  # Just above boundary
        md.state.best_ask = 0.999  # Just below boundary
        md._update_mid()

        # Should update since both conditions are met
        assert md.state.mid == pytest.approx(0.5, abs=1e-3)

    @pytest.mark.unit
    def test_on_book_standard_format(self, mock_logger):
        """Test processing book messages in standard format."""
        md = MarketData(mock_logger)

        msg = {
            "bids": [{"price": "0.45", "size": "100"}],
            "asks": [{"price": "0.55", "size": "200"}],
            "timestamp": 1703123456789,
        }

        md.on_book(msg)

        assert md.state.best_bid == 0.45
        assert md.state.best_ask == 0.55
        assert md.state.mid == 0.5
        assert md.state.last_book_ts_ms == 1703123456789

        # Check logging was called
        mock_logger.write.assert_called_with("ws_book", {
            "best_bid": 0.45,
            "best_ask": 0.55,
            "mid": 0.5,
            "tick": 0.01,
        })

    @pytest.mark.unit
    def test_on_book_alternative_format(self, mock_logger):
        """Test processing book messages in alternative buys/sells format."""
        md = MarketData(mock_logger)

        msg = {
            "buys": [{"price": "0.40", "size": "150"}],
            "sells": [{"price": "0.60", "size": "250"}],
            "timestamp": 1703123456789,
        }

        md.on_book(msg)

        assert md.state.best_bid == 0.40
        assert md.state.best_ask == 0.60
        assert md.state.mid == 0.5
        assert md.state.last_book_ts_ms == 1703123456789

    @pytest.mark.unit
    def test_on_book_empty_book(self, mock_logger):
        """Test processing book messages with empty order book."""
        md = MarketData(mock_logger)

        msg = {
            "bids": [],
            "asks": [],
            "timestamp": 1703123456789,
        }

        md.on_book(msg)

        # State should remain unchanged
        assert md.state.best_bid == 0.0
        assert md.state.best_ask == 1.0
        assert md.state.mid == 0.5

    @pytest.mark.unit
    def test_on_price_change_single_update(self, mock_logger):
        """Test processing single price change updates."""
        md = MarketData(mock_logger)

        msg = {
            "price_changes": [
                {
                    "best_bid": "0.48",
                    "best_ask": "0.52",
                }
            ],
            "timestamp": 1703123456789,
        }

        md.on_price_change(msg)

        assert md.state.best_bid == 0.48
        assert md.state.best_ask == 0.52
        assert md.state.mid == 0.5
        assert md.state.last_book_ts_ms == 1703123456789

        # Check logging
        mock_logger.write.assert_called_with("ws_price_change", {
            "best_bid": 0.48,
            "best_ask": 0.52,
            "mid": 0.5,
            "n_changes": 1,
        })

    @pytest.mark.unit
    def test_on_price_change_partial_updates(self, mock_logger):
        """Test processing partial price change updates."""
        md = MarketData(mock_logger)

        # Set initial state
        md.state.best_bid = 0.45
        md.state.best_ask = 0.55

        # Only update bid
        msg1 = {
            "price_changes": [{"best_bid": "0.47"}],
            "timestamp": 1703123456789,
        }

        md.on_price_change(msg1)

        assert md.state.best_bid == 0.47
        assert md.state.best_ask == 0.55  # Unchanged

        # Only update ask
        msg2 = {
            "price_changes": [{"best_ask": "0.53"}],
            "timestamp": 1703123456790,
        }

        md.on_price_change(msg2)

        assert md.state.best_bid == 0.47  # Unchanged
        assert md.state.best_ask == 0.53

    @pytest.mark.unit
    def test_on_price_change_malformed_data(self, mock_logger):
        """Test handling of malformed price change data."""
        md = MarketData(mock_logger)

        msg = {
            "price_changes": [
                {
                    "best_bid": "invalid_price",
                    "best_ask": "0.52",
                },
                {
                    "best_bid": "0.48",
                    "best_ask": None,  # None value
                }
            ],
            "timestamp": 1703123456789,
        }

        md.on_price_change(msg)

        # Should skip invalid bid from first change, use valid values from both changes
        assert md.state.best_bid == 0.48  # Valid from second change
        assert md.state.best_ask == 0.52  # Valid from first change

    @pytest.mark.unit
    def test_on_tick_size_change(self, mock_logger):
        """Test processing tick size change messages."""
        md = MarketData(mock_logger)

        msg = {
            "new_tick_size": 0.005,
        }

        md.on_tick_size_change(msg)

        assert md.state.tick_size == 0.005

        # Check logging
        mock_logger.write.assert_called_with("ws_tick_size_change", {"tick": 0.005})

    @pytest.mark.unit
    def test_on_last_trade_price(self, mock_logger):
        """Test processing trade execution messages."""
        md = MarketData(mock_logger)

        msg = {
            "price": "0.475",
            "side": "BUY",
            "timestamp": 1703123456789,
        }

        md.on_last_trade_price(msg)

        assert md.state.last_trade_price == 0.475
        assert md.state.last_trade_ts_ms == 1703123456789
        assert len(md.trade_ts) == 1
        assert md.trade_ts[0] == 1703123456789

        # Check logging
        mock_logger.write.assert_called_with("ws_last_trade", {
            "price": 0.475,
            "side": "BUY",
        })

    @pytest.mark.unit
    def test_trade_rate_per_s_no_trades(self, mock_logger):
        """Test trade rate calculation with no trades."""
        md = MarketData(mock_logger)

        rate = md.trade_rate_per_s()
        assert rate == 0.0

    @pytest.mark.unit
    def test_trade_rate_per_s_with_trades(self, mock_logger):
        """Test trade rate calculation with recent trades."""
        md = MarketData(mock_logger)

        # Add some trades with timestamps (in milliseconds)
        current_time = 1703123456789  # Base timestamp
        md.trade_ts.extend([
            current_time - 60000,  # 1 minute ago
            current_time - 30000,  # 30 seconds ago
            current_time - 15000,  # 15 seconds ago
            current_time - 5000,   # 5 seconds ago
        ])

        # Mock now_ms to return our current_time
        with patch('pm4.market_data.now_ms', return_value=current_time):
            # Calculate rate over 60 second window
            rate = md.trade_rate_per_s(window_s=60.0)

            # 4 trades in 60 seconds = 4/60 ≈ 0.0667 trades per second
            assert rate == pytest.approx(4.0 / 60.0, abs=1e-6)

    @pytest.mark.unit
    def test_trade_rate_per_s_partial_window(self, mock_logger):
        """Test trade rate calculation with trades outside window."""
        md = MarketData(mock_logger)

        current_time = 1703123456789
        # Add trades: some within window, some outside
        md.trade_ts.extend([
            current_time - 120000,  # 2 minutes ago (outside 60s window)
            current_time - 90000,   # 1.5 minutes ago (outside window)
            current_time - 30000,   # 30 seconds ago (inside window)
            current_time - 15000,   # 15 seconds ago (inside window)
        ])

        with patch('pm4.market_data.now_ms', return_value=current_time):
            rate = md.trade_rate_per_s(window_s=60.0)

            # Only 2 trades in 60 second window = 2/60 ≈ 0.0333 trades per second
            assert rate == pytest.approx(2.0 / 60.0, abs=1e-6)

    @pytest.mark.unit
    def test_trade_rate_per_s_different_windows(self, mock_logger):
        """Test trade rate calculation with different window sizes."""
        md = MarketData(mock_logger)

        current_time = 1703123456789
        md.trade_ts.extend([
            current_time - 10000,  # 10 seconds ago
            current_time - 5000,   # 5 seconds ago
        ])

        with patch('pm4.market_data.now_ms', return_value=current_time):
            # 30 second window: 2 trades / 30s = ~0.0667/s
            rate_30s = md.trade_rate_per_s(window_s=30.0)
            assert rate_30s == pytest.approx(2.0 / 30.0, abs=1e-6)

            # 10 second window: 2 trades / 10s = 0.2/s (both trades within window)
            rate_10s = md.trade_rate_per_s(window_s=10.0)
            assert rate_10s == pytest.approx(2.0 / 10.0, abs=1e-6)

    @pytest.mark.unit
    def test_trade_rate_per_s_edge_cases(self, mock_logger):
        """Test trade rate calculation edge cases."""
        md = MarketData(mock_logger)

        current_time = 1703123456789

        # Test with very small window (should avoid division by zero)
        with patch('pm4.market_data.now_ms', return_value=current_time):
            rate = md.trade_rate_per_s(window_s=0.001)
            assert rate == 0.0  # No trades, so rate is 0

        # Test with trades exactly at boundaries
        md.trade_ts.append(current_time)  # Trade at current time
        with patch('pm4.market_data.now_ms', return_value=current_time):
            rate = md.trade_rate_per_s(window_s=1.0)
            # Should include the trade at current time
            assert rate > 0

    @pytest.mark.unit
    def test_trade_ts_buffer_limit(self, mock_logger):
        """Test that trade_ts respects buffer size limit."""
        md = MarketData(mock_logger)

        # Add more trades than buffer capacity (5000)
        base_time = 1703123456789
        for i in range(6000):
            md.trade_ts.append(base_time + i * 1000)

        # Buffer should only keep the most recent 5000 trades
        assert len(md.trade_ts) == 5000

        # Oldest trade should be the 1000th trade added (since 6000-5000=1000 were dropped)
        assert md.trade_ts[0] == base_time + 1000 * 1000  # 1000th trade added
        assert md.trade_ts[-1] == base_time + 5999 * 1000  # Last trade added
