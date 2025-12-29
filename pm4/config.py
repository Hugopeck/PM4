"""
Configuration loading utilities for PM4.
"""
import json

from .types import BotConfig, LoggingConfig, MarketConfig, QuoteConfig, RiskConfig, WarmupConfig


def load_config(path: str) -> BotConfig:
    """Load configuration from JSON file."""
    with open(path, "r") as fp:
        d = json.load(fp)
    market = MarketConfig(**d["market"])
    warmup = WarmupConfig(**d.get("warmup", {}))
    risk = RiskConfig(**d.get("risk", {}))
    quote = QuoteConfig(**d.get("quote", {}))
    logging = LoggingConfig(**d.get("logging", {}))
    return BotConfig(
        market=market,
        warmup=warmup,
        risk=risk,
        quote=quote,
        logging=logging,
        log_path=d.get("log_path", "./data/mm_events.jsonl"),
        calib_path=d.get("calib_path", "./data/warm_calibration.json"),
    )
