"""
Standalone warmup/calibration script for PM4 market maker.

This script collects market data, calculates risk parameters, and generates
a human-readable calibration report. It does NOT place any orders - it's
purely for data collection and analysis.

Usage:
    python -m pm4.warmup config.json
"""
import asyncio
import json
import os
import signal
import sys
import time

from .adapters import PolymarketAdapter
from .config import load_config
from .market_data import MarketData
from .trading import Indicators
from .utils import now_ms


def print_calibration_report(snap: dict, cfg, collection_time_s: float, price_range: tuple, avg_spread: float, trade_rate: float):
    """Print human-readable calibration report."""
    print("\n" + "=" * 40)
    print("CALIBRATION REPORT")
    print("=" * 40)
    
    # Basic stats
    n_samples = snap.get("n_returns", 0)
    req_samples = cfg.warmup.min_return_samples
    print(f"Samples Collected: {n_samples} / {req_samples}")
    print(f"Collection Time: {int(collection_time_s // 60)}m {int(collection_time_s % 60)}s")
    
    # Volatility metrics
    sigma_base = snap.get("sigma_base_logit_per_dt", 0.0)
    ema_fast = snap.get("ema_fast_abs", 0.0)
    ema_slow = snap.get("ema_slow_abs", 0.0)
    sigma_smoothed = snap.get("_sigma_smoothed", 1.0)
    
    print(f"\nBase Volatility (MAD): {sigma_base:.4f}")
    print(f"Shock Factor (EMA Fast/Slow): {ema_fast:.4f} / {ema_slow:.4f}")
    
    # Volatility interpretation
    print("\nVolatility Interpretation:")
    print(f"  Current Sigma: {sigma_smoothed:.2f}x baseline")
    
    if sigma_base < 0.05:
        verdict = "LOW VOLATILITY (Safe to tighten spreads)"
    elif sigma_base > 0.20:
        verdict = "HIGH VOLATILITY (Expect wide spreads)"
    else:
        verdict = "MODERATE VOLATILITY"
    print(f"  Verdict: {verdict}")
    
    # Market conditions
    print("\nMarket Conditions:")
    print(f"  - Price Range: {price_range[0]:.2f} - {price_range[1]:.2f}")
    print(f"  - Average Spread: {avg_spread:.4f}")
    print(f"  - Trade Rate: {trade_rate:.2f} trades/sec")
    
    # Sanity checks
    print("\nSanity Checks:")
    if 1.0 <= sigma_smoothed <= 2.0:
        print("  ✓ Sigma in reasonable range (1.0 - 2.0)")
    else:
        print(f"  ⚠ Sigma outside typical range: {sigma_smoothed:.2f}")
    
    if n_samples >= req_samples:
        print("  ✓ Sufficient samples collected")
    else:
        print(f"  ⚠ Only {n_samples}/{req_samples} samples collected")
    
    if ema_fast > ema_slow:
        print("  ⚠ EMA fast > EMA slow (increasing volatility detected)")
    else:
        print("  ✓ EMA fast <= EMA slow (stable or decreasing volatility)")
    
    # File location
    print(f"\nSaved to: {cfg.calib_path}")
    
    # Next steps
    print("\nNext Steps:")
    print("  1. Review the calibration metrics above")
    print("  2. Run: python -m pm4.run_bot config.json --dry-run")
    print("  3. Verify quotes look reasonable")
    print("  4. Run: python -m pm4.run_bot config.json")


async def run_warmup(cfg_path: str):
    """Run warmup data collection and calibration."""
    cfg = load_config(cfg_path)
    
    # Initialize adapter (read-only, no orders will be placed)
    ex = PolymarketAdapter(
        asset_yes=cfg.market.asset_id_yes,
        asset_no=cfg.market.asset_id_no
    )
    
    # Initialize logger (minimal logging for warmup)
    from .logging import JsonlLogger
    logger = JsonlLogger(cfg.log_path)
    
    md = MarketData(logger)
    ind = Indicators(cfg, logger)
    
    print(f"--- Starting Warmup for {cfg.warmup.max_warmup_s}s ---")
    print(f"Goal: Collect {cfg.warmup.min_return_samples} return samples.")
    print(f"Sample interval: {cfg.warmup.dt_sample_s}s")
    print("\nPress Ctrl+C to stop early and save current calibration.\n")
    
    shutdown_event = asyncio.Event()
    
    def signal_handler():
        print("\n\nShutdown signal received. Saving calibration...")
        shutdown_event.set()
    
    # Setup signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass
    
    # WebSocket connection for market data
    async def ws_loop():
        import websockets
        mc = cfg.market
        try:
            async with websockets.connect(mc.wss_url, ping_interval=20, ping_timeout=20) as ws:
                sub = {"type": "subscribe", "channel": "market", "market": mc.market}
                await ws.send(json.dumps(sub))
                logger.write("ws_subscribe", {"payload": sub})
                
                async for raw in ws:
                    if shutdown_event.is_set():
                        break
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        logger.write("ws_parse_error", {"raw": raw[:2000]})
                        continue
                    
                    et = msg.get("event_type") or msg.get("type")
                    if et == "book":
                        md.on_book(msg)
                    elif et == "price_change":
                        md.on_price_change(msg)
                    elif et == "tick_size_change":
                        md.on_tick_size_change(msg)
                    elif et == "last_trade_price":
                        md.on_last_trade_price(msg)
        except Exception as e:
            logger.write("ws_error", {"err": str(e)})
            print(f"\nWebSocket error: {e}")
            shutdown_event.set()
    
    # Start WebSocket task
    ws_task = asyncio.create_task(ws_loop())
    
    # Data collection loop
    t0 = time.time()
    last_progress_print = 0.0
    price_history = []
    spread_history = []
    
    try:
        while not shutdown_event.is_set():
            p = md.state.mid
            if not (0.0 < p < 1.0):
                await asyncio.sleep(0.2)
                continue
            
            # Track price and spread for report
            price_history.append(p)
            if md.state.best_bid > 0 and md.state.best_ask < 1:
                spread_history.append(md.state.best_ask - md.state.best_bid)
            
            # Update indicators
            tr = md.trade_rate_per_s(window_s=60.0)
            ind.on_time_sample(now_ms(), p, tr)
            ind.update_markouts(now_ms(), p)
            
            # Progress reporting
            n = len(ind._returns)
            req = cfg.warmup.min_return_samples
            elapsed = time.time() - t0
            
            # Print progress every 5 seconds
            if time.time() - last_progress_print >= 5.0:
                progress_pct = min(100, (n / req) * 100) if req > 0 else 0
                print(f"\rProgress: {n}/{req} samples ({progress_pct:.1f}%) | "
                      f"Current Sigma: {ind.sigma():.2f} | "
                      f"Elapsed: {int(elapsed // 60)}m {int(elapsed % 60)}s", end="", flush=True)
                last_progress_print = time.time()
            
            # Check completion conditions
            if ind.warm_ready():
                print("\n✓ Warmup complete: Sufficient samples collected")
                break
            
            if elapsed >= cfg.warmup.max_warmup_s:
                print(f"\n⚠ Warmup timeout: Max time ({cfg.warmup.max_warmup_s}s) reached")
                break
            
            await asyncio.sleep(0.2)
    
    finally:
        # Cancel WebSocket task
        ws_task.cancel()
        try:
            await ws_task
        except asyncio.CancelledError:
            pass
        
        # Generate and save calibration
        snap = ind.save_calibration()
        collection_time = time.time() - t0
        
        # Calculate market statistics for report
        price_range = (min(price_history), max(price_history)) if price_history else (0.0, 1.0)
        avg_spread = sum(spread_history) / len(spread_history) if spread_history else 0.0
        trade_rate = md.trade_rate_per_s(window_s=60.0)
        
        # Save calibration file
        os.makedirs(os.path.dirname(cfg.calib_path), exist_ok=True)
        with open(cfg.calib_path, "w") as fp:
            json.dump(snap, fp, indent=2)
        
        # Print report
        print_calibration_report(snap, cfg, collection_time, price_range, avg_spread, trade_rate)
        
        logger.write("warmup_done", snap)
        logger.close()


def main():
    """Main entry point for warmup script."""
    if len(sys.argv) < 2:
        print("Usage: python -m pm4.warmup config.json")
        sys.exit(1)
    
    asyncio.run(run_warmup(sys.argv[1]))


if __name__ == "__main__":
    main()

