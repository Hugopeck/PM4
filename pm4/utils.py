"""
Utility functions for PM4 market maker.
"""
import math
import time
from datetime import datetime
from typing import Union


def now_ms() -> int:
    """Get current timestamp in milliseconds."""
    return int(time.time() * 1000)


def clip(x: float, lo: float, hi: float) -> float:
    """Clip value to [lo, hi] range."""
    return max(lo, min(hi, x))


def logit(p: float, eps: float = 1e-6) -> float:
    """Logit transformation with clipping."""
    p = clip(p, eps, 1.0 - eps)
    return math.log(p / (1.0 - p))


def sigmoid(x: float) -> float:
    """Sigmoid function."""
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def floor_to_tick(p: float, tick: float) -> float:
    """Floor price to nearest tick."""
    return math.floor(p / tick) * tick


def ceil_to_tick(p: float, tick: float) -> float:
    """Ceil price to nearest tick."""
    return math.ceil(p / tick) * tick


def fmt(x: Union[int, float], nd: int = 4) -> str:
    """Format number with specified decimal places."""
    return f"{x:.{nd}f}"


def date_to_timestamp(date_str: str) -> int:
    """Convert date string to Unix timestamp in milliseconds.

    Supports multiple date formats:
    - YYYY-MM-DD (2025-01-01)
    - YYYY-MM-DD HH:MM:SS (2025-01-01 12:00:00)
    - Month DD, YYYY (January 1, 2025)
    - Mon DD, YYYY (Jan 1, 2025)

    Args:
        date_str: Date string in supported format

    Returns:
        Unix timestamp in milliseconds

    Raises:
        ValueError: If date format is not recognized
    """
    formats = [
        "%Y-%m-%d",           # 2025-01-01
        "%Y-%m-%d %H:%M:%S",  # 2025-01-01 12:00:00
        "%B %d, %Y",          # January 1, 2025
        "%b %d, %Y",          # Jan 1, 2025
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue

    raise ValueError(f"Could not parse date: {date_str}. Supported formats: {formats}")


def timestamp_to_date(ts_ms: int) -> str:
    """Convert Unix timestamp in milliseconds to readable date string.

    Args:
        ts_ms: Unix timestamp in milliseconds

    Returns:
        Date string in YYYY-MM-DD HH:MM:SS format
    """
    dt = datetime.fromtimestamp(ts_ms / 1000)
    return dt.strftime("%Y-%m-%d %H:%M:%S")
