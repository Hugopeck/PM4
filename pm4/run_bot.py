"""
Trading execution script for PM4 market maker.

This script loads calibration data and runs the trading bot. It supports
a dry-run mode for testing quote behavior without placing real orders.

Usage:
    python -m pm4.run_bot config.json              # Live trading
    python -m pm4.run_bot config.json --dry-run     # Dry-run mode
"""
import argparse
import asyncio
import os
import signal
import sys

from .adapters import PolymarketAdapter
from .config import load_config
from .trading import MarketMakerBot


class DryRunAdapter(PolymarketAdapter):
    """Exchange adapter that mocks order placement for dry-run testing.

    This adapter extends PolymarketAdapter but overrides order placement
    methods to print theoretical orders instead of placing them. All other
    methods (get_balances, list_open_orders, get_fills) work normally to
    provide realistic testing conditions.
    """

    async def place_limit_order(self, asset_id: str, side: str, price: float, size: float) -> str:
        """Mock order placement - prints order details without placing.

        Args:
            asset_id: Token identifier
            side: "BUY" or "SELL"
            price: Order price
            size: Order size

        Returns:
            Fake order ID for tracking purposes
        """
        order_id = f"dry_run_{side}_{asset_id[:8]}_{int(price * 1000)}"
        print(f"[DRY] WOULD PLACE {side}: {size:.2f} @ {price:.3f} (order_id: {order_id})")
        return order_id

    async def cancel_order(self, order_id: str) -> None:
        """Mock order cancellation - prints cancellation without canceling.

        Args:
            order_id: Order identifier to cancel
        """
        print(f"[DRY] WOULD CANCEL {order_id}")


async def main():
    """Main entry point for trading bot execution."""
    parser = argparse.ArgumentParser(
        description="Run PM4 market maker bot with optional dry-run mode"
    )
    parser.add_argument(
        "config",
        help="Path to configuration JSON file"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry-run mode: calculate quotes but do not place orders"
    )
    args = parser.parse_args()

    # Load configuration
    cfg = load_config(args.config)

    # Check if calibration file exists
    if not os.path.exists(cfg.calib_path):
        print(f"❌ Error: Calibration file not found: {cfg.calib_path}")
        print("   Please run warmup first: python -m pm4.warmup config.json")
        sys.exit(1)

    # Initialize adapter (dry-run or real)
    if args.dry_run:
        print("⚠️  DRY RUN MODE ACTIVE ⚠️")
        print("No orders will be placed. Watching market and printing theoretical quotes...")
        print("=" * 60)
        ex = DryRunAdapter(
            asset_yes=cfg.market.asset_id_yes,
            asset_no=cfg.market.asset_id_no
        )
    else:
        print("🚀 Starting live trading bot...")
        print("=" * 60)
        ex = PolymarketAdapter(
            asset_yes=cfg.market.asset_id_yes,
            asset_no=cfg.market.asset_id_no
        )

    # Initialize bot
    bot = MarketMakerBot(cfg, ex)

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(bot.shutdown()))
        except NotImplementedError:
            pass

    # Run bot
    try:
        await bot.run()
    except KeyboardInterrupt:
        print("\n\nShutdown requested by user.")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        raise
    finally:
        print("\nBot stopped.")


if __name__ == "__main__":
    asyncio.run(main())

