"""
PM4 Market Maker - Main entry point.
"""
import asyncio
import json
import signal
import sys

from .adapters import PolymarketAdapter
from .trading import MarketMakerBot
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


async def _amain():
    """Main async entry point."""
    if len(sys.argv) < 2:
        print("Usage: python -m pm4 config.json")
        sys.exit(1)

    cfg = load_config(sys.argv[1])

    # Initialize real adapter (Secrets read internally from os.environ)
    ex = PolymarketAdapter(
        asset_yes=cfg.market.asset_id_yes,
        asset_no=cfg.market.asset_id_no
    )

    bot = MarketMakerBot(cfg, ex)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(bot.shutdown()))
        except NotImplementedError:
            pass
    await bot.run()


if __name__ == "__main__":
    asyncio.run(_amain())
