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


def print_calibration_report(snap: dict, cfg, collection_time_s: float, price_range: tuple, avg_spread: float, trade_rate: float, meta_params=None):
    """Print human-readable calibration report."""
    print("\n" + "=" * 40)
    print("CALIBRATION REPORT")
    print("=" * 40)

    # Basic stats
    n_samples = snap.get("n_returns", 0)
    req_samples = cfg.warmup.min_return_samples
    print(f"Samples Collected: {n_samples} / {req_samples}")
    print(f"Collection Time: {int(collection_time_s // 60)}m {int(collection_time_s % 60)}s")

    # Meta-calibration info
    if meta_params:
        print("\nMeta-Calibration Applied:")
        print(".1f"        print(".1f"        print(".1f"        print(".1f"        print(".1f"        activity = meta_params.market_activity_summary
        if activity:
            print("
Market Activity Observed:"            print(f"  - Price Changes: {activity.get('n_price_changes', 0)}")
            print(".1f"            print(".1f"            print(".1f"            print(".1f"            print(".1f"    else:
        print("\nMeta-Calibration: Not applied (insufficient data)")
    
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
    print(f"Phase 1: Observation (collecting market activity data)")
    print(f"Phase 2: Meta-calibration (optimizing warmup parameters)")
    print(f"Phase 3: Calibration (collecting {cfg.warmup.min_return_samples} return samples)")
    print(f"\nPress Ctrl+C to stop early and save current calibration.\n")
    
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
    
    # Three-phase warmup
    t0 = time.time()
    last_progress_print = 0.0
    price_history = []
    spread_history = []

    # Phase tracking
    PHASE_OBSERVATION = 0
    PHASE_METACALIBRATION = 1
    PHASE_CALIBRATION = 2

    current_phase = PHASE_OBSERVATION
    phase_start_time = t0
    meta_params = None

    # Phase 1: Observation parameters (fast sampling to collect activity data)
    observation_duration_s = min(600.0, cfg.warmup.max_warmup_s * 0.2)  # Up to 10 minutes or 20% of total time
    observation_sample_interval = 1.0  # Fast sampling for activity detection

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

            current_time = time.time()
            elapsed = current_time - t0
            phase_elapsed = current_time - phase_start_time

            # Phase management
            if current_phase == PHASE_OBSERVATION:
                # Phase 1: Collect activity data with fast sampling
                sample_interval = observation_sample_interval

                # Check if we should move to Phase 2
                if phase_elapsed >= observation_duration_s:
                    print("
✓ Phase 1 complete: Collected activity data")
                    print("Phase 2: Meta-calibrating warmup parameters...")

                    # Perform meta-calibration
                    meta_params = ind.meta_calibrate_warmup_params()
                    if meta_params:
                        # Apply meta-calibrated parameters
                        ind.apply_meta_warmup_params(meta_params)

                        # Save meta-calibration
                        meta_path = cfg.calib_path.replace('.json', '_meta_warmup.json')
                        ind.save_meta_warmup_params(meta_path, meta_params)

                        print("✓ Phase 2 complete: Meta-calibration applied")
                        print(".1f"                        print(".1f"                        print(".1f"                        print(".1f"                    else:
                        print("⚠ Phase 2: Insufficient data for meta-calibration, using config defaults")

                    # Move to Phase 3
                    current_phase = PHASE_CALIBRATION
                    phase_start_time = current_time
                    print("Phase 3: Collecting return samples with calibrated parameters...")

            else:
                # Phase 2 & 3: Use meta-calibrated or config parameters
                sample_interval = ind.get_dt_sample_s()

            # Throttle sampling based on current phase requirements
            if (current_time - (ind._last_sample_ts_ms / 1000.0 if ind._last_sample_ts_ms else 0)) < sample_interval:
                await asyncio.sleep(0.1)
                continue

            # Update indicators
            tr = md.trade_rate_per_s(window_s=60.0)
            ind.on_time_sample(now_ms(), p, tr)
            ind.update_markouts(now_ms(), p)

            # Progress reporting
            n = len(ind._returns)
            req = cfg.warmup.min_return_samples

            # Print progress every 5 seconds
            if current_time - last_progress_print >= 5.0:
                if current_phase == PHASE_OBSERVATION:
                    progress_pct = min(100, (phase_elapsed / observation_duration_s) * 100)
                    phase_name = "Observation"
                elif current_phase == PHASE_CALIBRATION:
                    progress_pct = min(100, (n / req) * 100) if req > 0 else 0
                    phase_name = "Calibration"
                else:
                    progress_pct = 100
                    phase_name = "Meta-calibration"

                print(f"\r[{phase_name}] Progress: {progress_pct:.1f}% | "
                      f"Samples: {n}/{req} | "
                      f"Sigma: {ind.sigma():.2f} | "
                      f"Elapsed: {int(elapsed // 60)}m {int(elapsed % 60)}s", end="", flush=True)
                last_progress_print = current_time

            # Check completion conditions (only in calibration phase)
            if current_phase == PHASE_CALIBRATION and ind.warm_ready():
                print("\n✓ Warmup complete: Sufficient samples collected")
                break

            if elapsed >= cfg.warmup.max_warmup_s:
                print(f"\n⚠ Warmup timeout: Max time ({cfg.warmup.max_warmup_s}s) reached")
                break

            await asyncio.sleep(0.1)  # Slightly faster polling for responsiveness
    
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
        print_calibration_report(snap, cfg, collection_time, price_range, avg_spread, trade_rate, meta_params)
        
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

