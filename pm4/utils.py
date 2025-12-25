"""
Utility functions for PM4 market maker.
"""
import math
import time
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
