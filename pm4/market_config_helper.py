"""
Market configuration helper for PM4.

This script helps extract market information from Polymarket URLs
and generates the correct configuration format for config.json.
"""

import argparse
import json
import re
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List

from .market_analyzer import MarketAnalyzer
from .utils import date_to_timestamp, timestamp_to_date


# Parameter ranges based on PM4 documentation and recommendations
PARAMETER_RANGES: Dict[str, Dict[str, Tuple[float, float]]] = {
    "warmup": {
        "dt_sample_s": (1.0, 10.0),
        "min_return_samples": (120, 720),
        "max_warmup_s": (1800.0, 7200.0),
        "tau_fast_s": (10.0, 60.0),
        "tau_slow_s": (600.0, 3600.0),
        "markout_h1_s": (5.0, 30.0),
        "markout_h2_s": (30.0, 300.0),
    },
    "risk": {
        "bankroll_B": (10.0, 100.0),
        "n_plays": (1, 4),
        "eta_time": (0.25, 0.75),
        "slippage_buffer": (0.02, 0.12),
        "gamma_a": (0.8, 1.2),
        "gamma_max": (5.0, 10.0),
        "lambda_min": (0.5, 1.0),
        "lambda_max": (1.5, 3.0),
        "beta_p": (0.3, 1.0),
        "alpha_U": (0.2, 0.8),
        "U_ref": (10.0, 100.0),
        "w_A": (0.5, 2.0),
        "w_L": (0.5, 2.0),
        "s_scale": (0.5, 2.0),
        "I_max": (1.0, 5.0),
        "c_tox": (0.5, 2.0),
        "c_sigma": (0.5, 2.0),
        "nu_sigma": (1.0, 2.0),
        "sigma_max": (3.0, 10.0),
        "sigma_tau_up_s": (5.0, 30.0),
        "sigma_tau_down_s": (30.0, 300.0),
    },
    "quote": {
        "c_risk": (0.1, 0.5),
        "kappa0": (0.5, 2.0),
        "rate_ref_per_s": (0.01, 0.2),
        "min_half_spread_prob": (0.005, 0.02),
        "max_half_spread_logit": (1.0, 3.0),
        "ladder_decay": (0.7, 0.9),
        "ladder_step_mult": (0.3, 0.7),
        "ladder_min_step_logit": (0.02, 0.1),
        "ladder_max_levels": (3, 8),
        "min_order_size": (0.1, 5.0),
        "max_order_notional_side": (50.0, 500.0),
        "refresh_s": (1.0, 5.0),
        "price_move_requote_ticks": (1, 5),
    },
}


def clamp_value(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value to the specified range."""
    return max(min_val, min(max_val, value))


def validate_parameter(section: str, param_name: str, value: Any, strict: bool = False) -> Any:
    """
    Validate a parameter value against its documented range.
    
    Args:
        section: Configuration section name (e.g., 'warmup', 'risk', 'quote')
        param_name: Parameter name
        value: Parameter value to validate
        strict: If True, raise ValueError on out-of-range. If False, clamp to range.
    
    Returns:
        Validated (and potentially clamped) value
    
    Raises:
        ValueError: If strict=True and value is out of range
        KeyError: If section or param_name not found in ranges
    """
    if section not in PARAMETER_RANGES:
        return value
    
    if param_name not in PARAMETER_RANGES[section]:
        return value  # No validation defined for this parameter
    
    min_val, max_val = PARAMETER_RANGES[section][param_name]
    
    # Convert to float for comparison
    float_value = float(value)
    
    if strict:
        if float_value < min_val or float_value > max_val:
            raise ValueError(
                f"Parameter {section}.{param_name} = {value} is out of range "
                f"[{min_val}, {max_val}]"
            )
        return value
    else:
        # Clamp to valid range
        clamped = clamp_value(float_value, min_val, max_val)
        if clamped != float_value:
            print(f"Warning: {section}.{param_name} = {value} clamped to {clamped} "
                  f"(valid range: [{min_val}, {max_val}])")
        # Return original type (int if it was int, float if it was float)
        if isinstance(value, int) and clamped == int(clamped):
            return int(clamped)
        return clamped


def validate_config(config: Dict[str, Any], strict: bool = False) -> Tuple[bool, List[str]]:
    """
    Validate all parameters in a configuration dictionary.
    
    Args:
        config: Configuration dictionary to validate
        strict: If True, raise ValueError on first out-of-range parameter.
                If False, clamp values and collect warnings.
    
    Returns:
        Tuple of (is_valid, warnings_list)
    
    Raises:
        ValueError: If strict=True and any parameter is out of range
    """
    warnings: List[str] = []
    
    for section_name, section_ranges in PARAMETER_RANGES.items():
        if section_name not in config:
            continue
            
        section_config = config[section_name]
        
        for param_name in section_ranges:
            if param_name not in section_config:
                continue
            
            try:
                original_value = section_config[param_name]
                validated_value = validate_parameter(
                    section_name, param_name, original_value, strict=strict
                )
                
                if validated_value != original_value:
                    section_config[param_name] = validated_value
                    if not strict:
                        warnings.append(
                            f"{section_name}.{param_name}: {original_value} -> {validated_value}"
                        )
                        
            except ValueError as e:
                if strict:
                    raise
                warnings.append(str(e))
    
    return (len(warnings) == 0, warnings)


def extract_market_slug(url: str) -> str:
    """Extract market slug from Polymarket URL."""
    # Handle various Polymarket URL formats
    patterns = [
        r'polymarket\.com/market/([^/?]+)',           # Standard market URLs
        r'polymarket\.com/event/[^/]+/([^/?]+)',      # Event URLs: /event/event-id/market-slug
        r'gamma\.polymarket\.com/market/([^/?]+)',    # Gamma market URLs
        r'https?://[^/]+/market/([^/?]+)',            # Generic market URLs
        r'https?://[^/]+/event/[^/]+/([^/?]+)'        # Generic event URLs
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
        # Convert dates to timestamps
        start_ts_ms = 1700000000000  # Default
        resolve_ts_ms = 1735000000000  # Default
        
        if analysis.start_date:
            try:
                from datetime import datetime
                start_dt = datetime.fromisoformat(analysis.start_date.replace('Z', '+00:00'))
                start_ts_ms = int(start_dt.timestamp() * 1000)
            except Exception:
                pass
        
        if analysis.end_date:
            try:
                from datetime import datetime
                end_dt = datetime.fromisoformat(analysis.end_date.replace('Z', '+00:00'))
                resolve_ts_ms = int(end_dt.timestamp() * 1000)
            except Exception:
                pass
        
        # Use token IDs from analysis if available, otherwise use placeholders
        asset_id_yes = analysis.token_id_yes if analysis.token_id_yes else "0x_YES_TOKEN_ID"
        asset_id_no = analysis.token_id_no if analysis.token_id_no else "0x_NO_TOKEN_ID"
        
        # Use actual market data
        config = {
            "market": {
                "market": analysis.condition_id,
                "asset_id_yes": asset_id_yes,
                "asset_id_no": asset_id_no,
                "start_ts_ms": start_ts_ms,
                "resolve_ts_ms": resolve_ts_ms,
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
    # Validate and clamp bankroll to valid range
    bankroll = validate_parameter("risk", "bankroll_B", bankroll, strict=False)

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
            "slippage_buffer": 0.05,
            "gamma_a": 0.8,
            "gamma_max": 8.0,
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
        "log_path": "./data/logs/mm_events.jsonl",
        "calib_path": "./data/calibration/warm_calibration.json"
    }

    config.update(base_config)
    
    # Validate all parameters in the generated config
    is_valid, warnings = validate_config(config, strict=False)
    if warnings:
        print("\n⚠️  Parameter validation warnings (values clamped to valid ranges):")
        for warning in warnings:
            print(f"  - {warning}")
    
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
            # Validate against range
            try:
                bankroll = validate_parameter("risk", "bankroll_B", bankroll, strict=True)
                break
            except ValueError as e:
                print(f"✗ {e}")
                min_val, max_val = PARAMETER_RANGES["risk"]["bankroll_B"]
                print(f"  Valid range: ${min_val}-${max_val}")
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

    # Save config to temp directory
    import os
    os.makedirs("data/temp", exist_ok=True)
    output_file = "data/temp/config_generated.json"
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
        default="data/temp/config_generated.json",
        help="Output config file path (default: data/temp/config_generated.json)"
    )

    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run interactive setup"
    )

    parser.add_argument(
        "--strict", "-s",
        action="store_true",
        help="Strict validation mode (raise errors instead of clamping values)"
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
    
    # Validate config (will clamp or raise depending on strict mode)
    try:
        is_valid, warnings = validate_config(config, strict=args.strict)
        if args.strict and not is_valid:
            print("✗ Configuration validation failed")
            return
    except ValueError as e:
        print(f"✗ Configuration validation error: {e}")
        return

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
