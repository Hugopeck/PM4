"""
Market data processing and order book state management.
"""
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Optional

from .logging import JsonlLogger
from .utils import now_ms


@dataclass
class BookState:
    """Current order book state."""
    best_bid: float = 0.0
    best_ask: float = 1.0
    mid: float = 0.5
    tick_size: float = 0.01
    last_trade_price: Optional[float] = None
    last_book_ts_ms: int = 0
    last_trade_ts_ms: int = 0


class MarketData:
    """Processes real-time market data from WebSocket feeds."""

    def __init__(self, logger: JsonlLogger):
        self.state = BookState()
        self.logger = logger
        self.trade_ts: Deque[int] = deque(maxlen=5000)

    def _update_mid(self):
        """Update midpoint price from best bid/ask."""
        b, a = self.state.best_bid, self.state.best_ask
        if b > 0 and a < 1 and b < a:
            self.state.mid = 0.5 * (b + a)

    def on_book(self, msg: Dict[str, Any]) -> None:
        """Handle full order book update."""
        bids = msg.get("bids") or msg.get("buys") or []
        asks = msg.get("asks") or msg.get("sells") or []
        if bids:
            self.state.best_bid = float(bids[0]["price"])
        if asks:
            self.state.best_ask = float(asks[0]["price"])
        self.state.last_book_ts_ms = int(msg.get("timestamp", now_ms()))
        self._update_mid()
        self.logger.write("ws_book", {
            "best_bid": self.state.best_bid,
            "best_ask": self.state.best_ask,
            "mid": self.state.mid,
            "tick": self.state.tick_size
        })

    def on_price_change(self, msg: Dict[str, Any]) -> None:
        """Handle price change updates."""
        pcs = msg.get("price_changes", [])
        best_bid = None
        best_ask = None
        for pc in pcs:
            if pc.get("best_bid") is not None:
                try:
                    best_bid = float(pc["best_bid"])
                except Exception:
                    pass
            if pc.get("best_ask") is not None:
                try:
                    best_ask = float(pc["best_ask"])
                except Exception:
                    pass
        if best_bid is not None:
            self.state.best_bid = best_bid
        if best_ask is not None:
            self.state.best_ask = best_ask
        self.state.last_book_ts_ms = int(msg.get("timestamp", now_ms()))
        self._update_mid()
        self.logger.write("ws_price_change", {
            "best_bid": self.state.best_bid,
            "best_ask": self.state.best_ask,
            "mid": self.state.mid,
            "n_changes": len(pcs)
        })

    def on_tick_size_change(self, msg: Dict[str, Any]) -> None:
        """Handle tick size changes."""
        self.state.tick_size = float(msg["new_tick_size"])
        self.logger.write("ws_tick_size_change", {"tick": self.state.tick_size})

    def on_last_trade_price(self, msg: Dict[str, Any]) -> None:
        """Handle trade price updates."""
        p = float(msg["price"])
        ts = int(msg.get("timestamp", now_ms()))
        self.state.last_trade_price = p
        self.state.last_trade_ts_ms = ts
        self.trade_ts.append(ts)
        self.logger.write("ws_last_trade", {"price": p, "side": msg.get("side", "UNKNOWN")})

    def trade_rate_per_s(self, window_s: float = 60.0) -> float:
        """Calculate trade rate over a time window."""
        if not self.trade_ts:
            return 0.0
        t_now = now_ms()
        cutoff = t_now - int(window_s * 1000)
        n = 0
        for ts in reversed(self.trade_ts):
            if ts < cutoff:
                break
            n += 1
        return n / max(window_s, 1e-9)
