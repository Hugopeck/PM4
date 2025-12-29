"""
Polymarket market analysis utilities for PM4 dry-run validation.

This module provides automated market evaluation to help select suitable
markets for market making, checking volume, liquidity, activity, and other
key metrics before running PM4.
"""

import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .utils import now_ms


def extract_market_slug(url_or_slug: str) -> str:
    """Extract market slug from Polymarket URL or return slug as-is."""
    import re

    # Check if it's already a slug (no protocol/domain)
    if not url_or_slug.startswith(('http://', 'https://', 'www.')):
        return url_or_slug

    # Handle various Polymarket URL formats
    patterns = [
        r'polymarket\.com/market/([^/?]+)',
        r'gamma\.polymarket\.com/market/([^/?]+)',
        r'https?://[^/]+/market/([^/?]+)'
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_slug)
        if match:
            return match.group(1)

    raise ValueError(f"Could not extract market slug from: {url_or_slug}. Please provide either a Polymarket URL or market slug.")


@dataclass
class MarketAnalysis:
    """Comprehensive market analysis result."""
    market_slug: str
    condition_id: str
    volume_24h: float
    active_traders: int
    last_trade_hours: float
    price_range_24h: Tuple[float, float]
    current_price: float
    time_to_resolution_days: int
    recommendation: str
    reasons: List[str]

    @property
    def is_recommended(self) -> bool:
        return self.recommendation == "RECOMMENDED"


class MarketAnalyzer:
    """Analyze Polymarket data for PM4 trading suitability."""

    def __init__(self, base_url: str = "https://gamma-api.polymarket.com"):
        self.base_url = base_url
        self.session = requests.Session()

    def get_market_data(self, market_slug: str) -> Optional[Dict]:
        """Fetch comprehensive market data from Polymarket API."""
        url = f"{self.base_url}/markets/{market_slug}"

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching market data for {market_slug}: {e}")
            return None

    def get_recent_trades(self, asset_id: str, hours: int = 24) -> List[Dict]:
        """Get recent trades for price movement analysis."""
        # Note: Polymarket API may have rate limits
        # This is a placeholder for trade history analysis
        try:
            # This would need actual Polymarket trades API endpoint
            # For now, return empty list
            return []
        except Exception:
            return []

    def analyze_market(self, market_slug: str) -> MarketAnalysis:
        """Perform comprehensive market analysis for PM4 compatibility."""

        data = self.get_market_data(market_slug)
        if not data:
            return MarketAnalysis(
                market_slug=market_slug,
                condition_id="",
                volume_24h=0,
                active_traders=0,
                last_trade_hours=999,
                price_range_24h=(0, 1),
                current_price=0.5,
                time_to_resolution_days=0,
                recommendation="ERROR",
                reasons=["Failed to fetch market data"]
            )

        # Extract basic market info
        market_id = data.get('id', '')
        volume_24h = float(data.get('volume', 0))
        active_traders = int(data.get('activeUsers', 0))  # May vary by API

        # Get current price
        try:
            yes_price = float(data.get('outcomePrices', ['0.5', '0.5'])[0])
            no_price = float(data.get('outcomePrices', ['0.5', '0.5'])[1])
            current_price = yes_price  # Focus on YES outcome
        except (IndexError, ValueError):
            current_price = 0.5

        # Calculate time to resolution
        try:
            end_date_str = data.get('endDate', '')
            if end_date_str:
                # Handle ISO format dates
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                now = datetime.now(end_date.tzinfo)
                days_to_resolution = max(0, (end_date - now).days)
            else:
                days_to_resolution = 365  # Default assumption
        except Exception:
            days_to_resolution = 365

        # Check recent activity (simplified - would need trades API)
        last_trade_ts = data.get('lastTradeTimestamp', 0)
        if last_trade_ts:
            hours_since_trade = (now_ms() - last_trade_ts) / (1000 * 3600)
        else:
            hours_since_trade = 24  # Assume no recent activity

        # Analyze price movement (placeholder - would need trades)
        price_range = (max(0.01, current_price - 0.1), min(0.99, current_price + 0.1))

        # Evaluate market suitability
        reasons = []
        score = 0

        # Volume check
        if volume_24h >= 50000:
            score += 2
            reasons.append(f"✓ Excellent volume: ${volume_24h:,.0f}")
        elif volume_24h >= 25000:
            score += 1
            reasons.append(f"✓ Good volume: ${volume_24h:,.0f}")
        else:
            reasons.append(f"✗ Low volume: ${volume_24h:,.0f}")

        # Traders check
        if active_traders >= 100:
            score += 2
            reasons.append(f"✓ High trader count: {active_traders}")
        elif active_traders >= 50:
            score += 1
            reasons.append(f"✓ Moderate trader count: {active_traders}")
        else:
            reasons.append(f"? Low trader visibility: {active_traders}")

        # Activity check
        if hours_since_trade <= 2:
            score += 2
            reasons.append(f"✓ Very active: {hours_since_trade:.1f}h ago")
        elif hours_since_trade <= 6:
            score += 1
            reasons.append(f"⚠ Moderate activity: {hours_since_trade:.1f}h ago")
        else:
            reasons.append(f"✗ Stagnant: {hours_since_trade:.1f}h ago")
        # Time to resolution check
        if days_to_resolution >= 30:
            score += 1
            reasons.append(f"✓ Long time horizon: {days_to_resolution} days")
        elif days_to_resolution >= 7:
            reasons.append(f"⚠ Moderate time horizon: {days_to_resolution} days")
        else:
            reasons.append(f"✗ Short time horizon: {days_to_resolution} days")

        # Price position check
        if 0.15 <= current_price <= 0.85:
            score += 1
            reasons.append(f"✓ Price in good range: {current_price:.2f}")
        else:
            reasons.append(f"⚠ Price at extreme: {current_price:.2f}")
        # Determine recommendation
        if score >= 5:
            recommendation = "RECOMMENDED"
        elif score >= 3:
            recommendation = "CONDITIONAL"
        else:
            recommendation = "NOT_RECOMMENDED"

        return MarketAnalysis(
            market_slug=market_slug,
            condition_id=market_id,
            volume_24h=volume_24h,
            active_traders=active_traders,
            last_trade_hours=hours_since_trade,
            price_range_24h=price_range,
            current_price=current_price,
            time_to_resolution_days=days_to_resolution,
            recommendation=recommendation,
            reasons=reasons
        )

    def print_analysis_report(self, analysis: MarketAnalysis) -> None:
        """Print formatted analysis report."""
        print(f"\n{'='*60}")
        print(f"MARKET ANALYSIS: {analysis.market_slug}")
        print(f"{'='*60}")
        print(f"Condition ID: {analysis.condition_id}")
        print(f"Current Price: {analysis.current_price:.3f}")
        print(f"24h Volume: ${analysis.volume_24h:,.0f}")
        print(f"Active Traders: {analysis.active_traders}")
        print(f"Last Trade: {analysis.last_trade_hours:.1f} hours ago")
        print(f"Time to Resolution: {analysis.time_to_resolution_days} days")
        print(f"Price Range (24h): {analysis.price_range_24h[0]:.3f} - {analysis.price_range_24h[1]:.3f}")

        print(f"\nRECOMMENDATION: {analysis.recommendation}")
        print("\nDETAILED ANALYSIS:")
        for reason in analysis.reasons:
            print(f"  {reason}")

        if analysis.is_recommended:
            print("\n✅ SUITABLE FOR PM4 MARKET MAKING")
            print("  Proceed with warmup and dry-run testing")
        elif analysis.recommendation == "CONDITIONAL":
            print("\n⚠️  MAY BE SUITABLE WITH CAUTION")
            print("  Consider if other factors justify trading")
        else:
            print("\n❌ NOT RECOMMENDED FOR PM4")
            print("  Look for markets with higher volume/liquidity")

        print(f"{'='*60}\n")


def main():
    """Command-line interface for market analysis."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze Polymarket for PM4 trading suitability"
    )
    parser.add_argument(
        "market_input",
        help="Polymarket market URL or slug (e.g., 'https://polymarket.com/market/will-ethereum-reach-10k-before-2025' or 'will-ethereum-reach-10k-before-2025')"
    )

    args = parser.parse_args()

    # Extract market slug from URL or use slug directly
    try:
        market_slug = extract_market_slug(args.market_input)
        print(f"Analyzing market: {market_slug}")
        print("-" * 50)
    except ValueError as e:
        print(f"Error: {e}")
        return

    analyzer = MarketAnalyzer()
    analysis = analyzer.analyze_market(market_slug)
    analyzer.print_analysis_report(analysis)


if __name__ == "__main__":
    main()
