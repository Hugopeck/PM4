"""
Market configuration helper for PM4.

This script helps extract market information from Polymarket URLs
and generates the correct configuration format for config.json.
"""

import argparse
import json
import re
from datetime import datetime
from typing import Optional, Tuple

from .market_analyzer import MarketAnalyzer
from .utils import date_to_timestamp, timestamp_to_date


def extract_market_slug(url: str) -> str:
    """Extract market slug from Polymarket URL."""
    # Handle various Polymarket URL formats
    patterns = [
        r'polymarket\.com/market/([^/?]+)',
        r'gamma\.polymarket\.com/market/([^/?]+)',
        r'https?://[^/]+/market/([^/?]+)'
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    raise ValueError(f"Could not extract market slug from URL: {url}")


def format_config_for_market(market_slug: str, custom_bankroll: Optional[float] = None) -> dict:
    """Generate config.json format for a specific market."""

    analyzer = MarketAnalyzer()
    analysis = analyzer.analyze_market(market_slug)

    if not analysis.condition_id:
        print(f"Warning: Could not fetch market data for {market_slug}")
        print("Using placeholder values - you'll need to fill in manually")

        # Placeholder config
        config = {
            "market": {
                "market": "0x_CONDITION_ID",  # TODO: Fill from Polymarket
                "asset_id_yes": "0x_YES_TOKEN_ID",  # TODO: Fill from Polymarket
                "asset_id_no": "0x_NO_TOKEN_ID",   # TODO: Fill from Polymarket
                "start_ts_ms": 1700000000000,     # TODO: Set market start date
                "resolve_ts_ms": 1735000000000,   # TODO: Set resolution date
                "wss_url": "wss://ws-subscriptions-clob.polymarket.com/ws/market"
            }
        }
    else:
        # Use actual market data
        config = {
            "market": {
                "market": analysis.condition_id,
                "asset_id_yes": "0x_YES_TOKEN_ID",  # TODO: Get from market page
                "asset_id_no": "0x_NO_TOKEN_ID",   # TODO: Get from market page
                "start_ts_ms": 1700000000000,     # TODO: Set actual market start
                "resolve_ts_ms": 1735000000000,   # TODO: Set actual resolution date
                "wss_url": "wss://ws-subscriptions-clob.polymarket.com/ws/market"
            }
        }

    # Add analysis summary
    config["_market_analysis"] = {
        "slug": analysis.market_slug,
        "volume_24h": analysis.volume_24h,
        "active_traders": analysis.active_traders,
        "current_price": analysis.current_price,
        "recommendation": analysis.recommendation,
        "analyzed_at": timestamp_to_date(int(datetime.now().timestamp() * 1000))
    }

    # Use custom bankroll if provided, otherwise use safe default
    bankroll = custom_bankroll if custom_bankroll is not None else 50.0

    # Add the rest of the config with the bankroll
    base_config = {
        "warmup": {
            "dt_sample_s": 5.0,
            "min_return_samples": 360,
            "max_warmup_s": 7200,
            "tau_fast_s": 30.0,
            "tau_slow_s": 1800.0,
            "markout_h1_s": 10.0,
            "markout_h2_s": 60.0
        },
        "risk": {
            "bankroll_B": bankroll,
            "n_plays": 3,
            "eta_time": 0.5,
            "slippage_buffer": 0.10,
            "gamma_a": 1.0,
            "gamma_max": 50.0,
            "lambda_min": 0.8,
            "lambda_max": 2.0,
            "beta_p": 0.7,
            "alpha_U": 0.5,
            "U_ref": 50.0,
            "w_A": 1.0,
            "w_L": 1.0,
            "s_scale": 1.0,
            "I_max": 3.0,
            "c_tox": 1.0,
            "c_sigma": 1.0,
            "nu_sigma": 1.4,
            "sigma_max": 6.0,
            "sigma_tau_up_s": 10.0,
            "sigma_tau_down_s": 90.0
        },
        "quote": {
            "c_risk": 0.2,
            "kappa0": 1.0,
            "rate_ref_per_s": 0.05,
            "min_half_spread_prob": 0.01,
            "max_half_spread_logit": 1.5,
            "ladder_decay": 0.8,
            "ladder_step_mult": 0.5,
            "ladder_min_step_logit": 0.05,
            "ladder_max_levels": 5,
            "min_order_size": 1.0,
            "max_order_notional_side": 100.0,
            "refresh_s": 2.0,
            "price_move_requote_ticks": 1
        },
        "logging": {
            "level": "DEBUG",
            "enable_performance": True,
            "enable_context_tracking": False
        },
        "log_path": "./data/mm_events.jsonl",
        "calib_path": "./data/warm_calibration.json"
    }

    config.update(base_config)
    return config


def interactive_config_setup():
    """Interactive setup for market configuration."""
    print("PM4 Market Configuration Helper")
    print("=" * 40)

    # Get market URL
    while True:
        url = input("Enter Polymarket market URL: ").strip()
        try:
            market_slug = extract_market_slug(url)
            print(f"✓ Extracted market slug: {market_slug}")
            break
        except ValueError as e:
            print(f"✗ {e}")
            continue

    # Get bankroll
    while True:
        bankroll_input = input("Enter bankroll amount (USD) [50]: ").strip()
        if not bankroll_input:
            bankroll = 50.0
            break
        try:
            bankroll = float(bankroll_input)
            if bankroll > 0:
                break
            else:
                print("✗ Bankroll must be positive")
        except ValueError:
            print("✗ Please enter a valid number")

    # Generate config
    print(f"\nAnalyzing market: {market_slug}")
    config = format_config_for_market(market_slug, bankroll)

    # Show analysis
    analysis = config["_market_analysis"]
    print("\nMarket Analysis:")
    print(f"  Volume (24h): ${analysis['volume_24h']:,.0f}")
    print(f"  Active Traders: {analysis['active_traders']}")
    print(f"  Current Price: {analysis['current_price']:.3f}")
    print(f"  Recommendation: {analysis['recommendation']}")

    # Save config
    output_file = "config_generated.json"
    with open(output_file, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"\n✓ Configuration saved to: {output_file}")
    print("\nNext steps:")
    print("1. Edit the generated config file")
    print("2. Fill in the asset IDs from Polymarket market page")
    print("3. Set correct start_ts_ms and resolve_ts_ms dates")
    print("4. Rename to config.json and run: python -m pm4.warmup config.json")


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="Generate PM4 config for Polymarket markets"
    )

    parser.add_argument(
        "market_url",
        nargs="?",
        help="Polymarket market URL"
    )

    parser.add_argument(
        "--bankroll", "-b",
        type=float,
        default=50.0,
        help="Bankroll amount in USD (default: 50)"
    )

    parser.add_argument(
        "--output", "-o",
        default="config_generated.json",
        help="Output config file path"
    )

    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run interactive setup"
    )

    args = parser.parse_args()

    if args.interactive or not args.market_url:
        interactive_config_setup()
        return

    # Extract market slug
    try:
        market_slug = extract_market_slug(args.market_url)
    except ValueError as e:
        print(f"Error: {e}")
        return

    # Generate config
    print(f"Analyzing market: {market_slug}")
    config = format_config_for_market(market_slug, args.bankroll)

    # Save to file
    with open(args.output, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"✓ Configuration saved to: {args.output}")

    # Show summary
    analysis = config["_market_analysis"]
    print("\nMarket Summary:")
    print(f"  Volume: ${analysis['volume_24h']:,.0f}")
    print(f"  Traders: {analysis['active_traders']}")
    print(f"  Price: {analysis['current_price']:.3f}")
    print(f"  Status: {analysis['recommendation']}")


if __name__ == "__main__":
    main()
