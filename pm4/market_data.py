"""
Market data processing and order book state management.

This module handles real-time market data streams from Polymarket's WebSocket API,
maintaining synchronized order book state for algorithmic trading. It processes
multiple message types to provide a complete market view:

Real-time Data Flow:
    Polymarket WebSocket → Message Parsing → State Updates → Trading Signals

Message Processing:
- High-frequency price updates (price_change events)
- Periodic full book snapshots (book events)
- Trade execution notifications (last_trade_price events)
- Market configuration changes (tick_size_change events)

Key Design Principles:
- Thread-safe single-writer state updates
- Timestamp synchronization across data sources
- Graceful handling of malformed/missing data
- Comprehensive logging for debugging and analysis

The BookState maintains the current market snapshot while trade_ts provides
activity analysis for liquidity assessment and risk management.
"""
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Optional

from .logging import JsonlLogger
from .utils import now_ms


@dataclass
class BookState:
    """Real-time order book state for a prediction market.

    Maintains the current state of the limit order book and recent trading activity.
    All prices are in decimal format (0.0 to 1.0) for prediction market probabilities.

    Attributes:
        best_bid: Highest bid price (best price to sell at)
        best_ask: Lowest ask price (best price to buy at)
        mid: Midpoint price ((best_bid + best_ask) / 2)
        tick_size: Minimum price increment for orders
        last_trade_price: Price of most recent trade execution
        last_book_ts_ms: Timestamp of last order book update (milliseconds)
        last_trade_ts_ms: Timestamp of last trade execution (milliseconds)

    Note:
        Prices represent probabilities in prediction markets:
        - 0.0 = impossible event
        - 0.5 = neutral/fair odds
        - 1.0 = certain event

        The spread (best_ask - best_bid) indicates market liquidity and uncertainty.
    """
    best_bid: float = 0.0
    best_ask: float = 1.0
    mid: float = 0.5
    tick_size: float = 0.01
    last_trade_price: Optional[float] = None
    last_book_ts_ms: int = 0
    last_trade_ts_ms: int = 0


class MarketData:
    """Real-time market data processor for Polymarket WebSocket feeds.

    Handles incoming WebSocket messages from Polymarket's real-time data streams,
    maintaining synchronized order book state and trade history. Processes multiple
    message types to keep trading algorithms informed of market conditions.

    Key Responsibilities:
    - Order book state management (bids, asks, spreads)
    - Trade execution tracking and rate calculation
    - Real-time price feed processing
    - Market microstructure monitoring
    - Timestamp synchronization across data sources

    WebSocket Message Types Handled:
    - book: Full order book snapshots
    - price_change: Incremental best bid/ask updates
    - tick_size_change: Market precision updates
    - last_trade_price: Individual trade executions

    Thread Safety:
    - Designed for single-threaded async operation
    - All state updates are atomic
    - Trade rate calculations use snapshot semantics
    """

    def __init__(self, logger: JsonlLogger):
        """Initialize market data processor with logging.

        Sets up the core data structures for tracking market state and
        establishes the logging interface for market data events.

        Args:
            logger: JsonlLogger instance for recording market data events
                   Used to persist order book updates, trades, and state changes
                   for analysis and debugging

        Data Structures:
            state: BookState dataclass maintaining current order book snapshot
            trade_ts: Rolling buffer of recent trade timestamps (last 5000 trades)
                     Used for calculating trading activity rates and market liquidity
        """
        self.state = BookState()
        self.logger = logger
        # Maintain rolling history of trade timestamps for rate calculations
        # maxlen=5000 provides ~5 minutes of history at high frequency
        self.trade_ts: Deque[int] = deque(maxlen=5000)

    def _update_mid(self):
        """Update midpoint price from current best bid/ask prices.

        Calculates the market midpoint as the average of best bid and ask prices.
        Only updates when prices are in valid prediction market range and properly ordered.

        Validation Conditions:
        - Best bid > 0 (not at impossible event boundary)
        - Best ask < 1 (not at certain event boundary)
        - Best bid < best ask (proper order book structure)

        The midpoint represents the market's fair value estimate and is used by
        trading algorithms for positioning and volatility calculations.
        """
        b, a = self.state.best_bid, self.state.best_ask
        # Validate price ranges and order book integrity before updating
        if b > 0 and a < 1 and b < a:
            # Standard midpoint calculation: average of best bid and ask
            self.state.mid = 0.5 * (b + a)

    def on_book(self, msg: Dict[str, Any]) -> None:
        """Process full order book snapshot from Polymarket WebSocket.

        Handles complete order book updates containing all active bids and asks.
        Extracts the best (highest) bid and best (lowest) ask prices to maintain
        the current market view. This is typically sent periodically or after
        significant order book changes.

        Message Format:
            Polymarket sends order book data in various formats:
            - "bids"/"asks": Standard format
            - "buys"/"sells": Alternative format
            Orders are typically sorted by price (bids descending, asks ascending)

        Args:
            msg: WebSocket message containing order book data with structure:
                {
                    "bids": [{"price": float, "size": float}, ...] or
                    "buys": [{"price": float, "size": float}, ...],
                    "asks": [{"price": float, "size": float}, ...] or
                    "sells": [{"price": float, "size": float}, ...],
                    "timestamp": int  # milliseconds
                }

        Processing:
        - Extracts best bid (highest price in bids array)
        - Extracts best ask (lowest price in asks array)
        - Updates timestamps and recalculates midpoint
        - Logs state change for market analysis

        Note:
            Full book updates are less frequent than price_change updates
            but provide complete market depth information when needed.
        """
        # Handle Polymarket's flexible message format (bids/asks or buys/sells)
        bids = msg.get("bids") or msg.get("buys") or []
        asks = msg.get("asks") or msg.get("sells") or []

        # Extract best prices from order book arrays
        # bids[0] is highest bid price, asks[0] is lowest ask price
        if bids:
            self.state.best_bid = float(bids[0]["price"])
        if asks:
            self.state.best_ask = float(asks[0]["price"])

        # Update timestamp and recalculate derived metrics
        self.state.last_book_ts_ms = int(msg.get("timestamp", now_ms()))
        self._update_mid()

        # Log significant order book state change
        self.logger.write("ws_book", {
            "best_bid": self.state.best_bid,
            "best_ask": self.state.best_ask,
            "mid": self.state.mid,
            "tick": self.state.tick_size
        })

    def on_price_change(self, msg: Dict[str, Any]) -> None:
        """Process incremental best bid/ask price changes.

        Handles real-time price updates from Polymarket's high-frequency feed.
        These are lightweight updates containing only the current best prices,
        sent whenever the top of book changes without a full book refresh.

        This is the most frequent message type and critical for:
        - Real-time trading signal generation
        - Spread monitoring and market making decisions
        - Latency-sensitive price tracking

        Message Format:
            {
                "price_changes": [
                    {
                        "best_bid": float,    # optional, highest bid price
                        "best_ask": float     # optional, lowest ask price
                    }
                ],
                "timestamp": int  # milliseconds
            }

        Processing Logic:
        - Iterates through all price changes in the message
        - Updates best_bid/best_ask only when values are provided
        - Handles malformed data gracefully (skips invalid entries)
        - Maintains data integrity even with network issues

        Args:
            msg: WebSocket message with incremental price updates

        Note:
            These updates are optimized for low latency and high frequency.
            Missing bid/ask values in a change indicate no update to that side.
        """
        pcs = msg.get("price_changes", [])

        # Process incremental updates, allowing partial updates
        best_bid = None
        best_ask = None

        for pc in pcs:
            # Extract best bid if provided in this change
            if pc.get("best_bid") is not None:
                try:
                    best_bid = float(pc["best_bid"])
                except (ValueError, TypeError):
                    # Skip malformed price data, continue with other updates
                    pass

            # Extract best ask if provided in this change
            if pc.get("best_ask") is not None:
                try:
                    best_ask = float(pc["best_ask"])
                except (ValueError, TypeError):
                    # Skip malformed price data, continue with other updates
                    pass

        # Apply validated updates to book state
        if best_bid is not None:
            self.state.best_bid = best_bid
        if best_ask is not None:
            self.state.best_ask = best_ask

        # Update metadata and derived calculations
        self.state.last_book_ts_ms = int(msg.get("timestamp", now_ms()))
        self._update_mid()

        # Log incremental price changes for market analysis
        self.logger.write("ws_price_change", {
            "best_bid": self.state.best_bid,
            "best_ask": self.state.best_ask,
            "mid": self.state.mid,
            "n_changes": len(pcs)  # Track batch size for performance monitoring
        })

    def on_tick_size_change(self, msg: Dict[str, Any]) -> None:
        """Process market tick size (price precision) changes.

        Updates the minimum price increment for the market. Tick size determines:
        - Valid price levels for order placement
        - Price rounding for order generation algorithms
        - Market granularity and liquidity distribution

        This rarely changes but is critical for:
        - Generating valid order prices
        - Calculating proper price levels in ladder construction
        - Understanding market microstructure

        Args:
            msg: Message containing new tick size specification:
                {"new_tick_size": float}

        Note:
            Typical values: 0.01 (1%) for most prediction markets.
            Smaller tick sizes allow finer price discrimination.
        """
        self.state.tick_size = float(msg["new_tick_size"])
        self.logger.write("ws_tick_size_change", {"tick": self.state.tick_size})

    def on_last_trade_price(self, msg: Dict[str, Any]) -> None:
        """Process individual trade execution notifications.

        Records completed trade executions for market activity analysis.
        Tracks trade timestamps to calculate trading rates and market liquidity.

        Each trade represents an actual execution where:
        - A bid and ask order crossed
        - Price discovery occurred
        - Market participants exchanged tokens

        Args:
            msg: Trade execution message:
                {
                    "price": float,      # execution price
                    "side": str,         # "BUY" or "SELL" (taker side)
                    "timestamp": int     # milliseconds
                }

        Tracking:
        - Updates last trade price and timestamp in book state
        - Maintains rolling buffer of trade timestamps for rate calculations
        - Logs trade events for execution analysis and performance monitoring

        Note:
            Trade rate calculations use this timestamp history to measure
            market activity levels and adjust trading aggressiveness accordingly.
        """
        p = float(msg["price"])
        ts = int(msg.get("timestamp", now_ms()))

        # Update book state with latest execution
        self.state.last_trade_price = p
        self.state.last_trade_ts_ms = ts

        # Maintain rolling trade history for rate calculations
        self.trade_ts.append(ts)

        # Log trade execution for market analysis
        self.logger.write("ws_last_trade", {
            "price": p,
            "side": msg.get("side", "UNKNOWN")
        })

    def trade_rate_per_s(self, window_s: float = 60.0) -> float:
        """Calculate recent trading activity rate in trades per second.

        Measures market liquidity and activity by counting trade executions
        within a rolling time window. Used by risk management to adjust:
        - Position sizing (higher activity = more aggressive sizing)
        - Spread width (higher activity = tighter spreads)
        - Trading frequency (higher activity = more frequent quotes)

        Algorithm:
        - Counts trades in the specified time window
        - Calculates rate as trades per second
        - Uses rolling buffer of recent trade timestamps
        - Handles edge cases (empty buffer, very short windows)

        Args:
            window_s: Analysis window in seconds (default: 60.0)
                      Longer windows = smoother but less responsive
                      Shorter windows = more responsive but noisier

        Returns:
            Trading rate in trades per second:
            - 0.0 = no recent activity (illiquid market)
            - 0.1 = low activity (~6 trades/minute)
            - 1.0 = moderate activity (~60 trades/minute)
            - 10.0+ = high activity (very liquid market)

        Performance:
            - O(k) complexity where k is trades in window
            - Typically fast due to limited buffer size (5000 trades)
            - Optimized with early termination on timestamp sorting

        Note:
            Trade rate is a key input to volatility estimation and
            market regime detection algorithms.
        """
        if not self.trade_ts:
            return 0.0

        t_now = now_ms()
        # Convert window to milliseconds for timestamp comparison
        cutoff = t_now - int(window_s * 1000)

        # Count trades within the analysis window
        # Iterate backwards for efficiency (recent trades first)
        n = 0
        for ts in reversed(self.trade_ts):
            if ts < cutoff:
                break  # All remaining trades are older, exit early
            n += 1

        # Calculate rate, avoid division by zero
        return n / max(window_s, 1e-9)
