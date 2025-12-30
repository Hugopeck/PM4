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
        r'polymarket\.com/market/([^/?]+)',           # Standard market URLs
        r'polymarket\.com/event/[^/]+/([^/?]+)',      # Event URLs: /event/event-id/market-slug
        r'gamma\.polymarket\.com/market/([^/?]+)',    # Gamma market URLs
        r'https?://[^/]+/market/([^/?]+)',            # Generic market URLs
        r'https?://[^/]+/event/[^/]+/([^/?]+)'        # Generic event URLs
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
    # Extended fields from Polymarket API
    end_date: Optional[str] = None
    start_date: Optional[str] = None
    volume24hr: float = 0.0
    volume1wk: float = 0.0
    volume24hrAmm: float = 0.0
    volume1wkAmm: float = 0.0
    volume24hrClob: float = 0.0
    volume1wkClob: float = 0.0
    volumeAmm: float = 0.0
    volumeClob: float = 0.0
    liquidityAmm: float = 0.0
    liquidityClob: float = 0.0
    # Order book and price change fields
    rewardsMinSize: float = 0.0
    rewardsMaxSpread: float = 0.0
    spread: float = 0.0
    bestBid: float = 0.0
    bestAsk: float = 0.0
    oneDayPriceChange: float = 0.0
    oneHourPriceChange: float = 0.0
    oneWeekPriceChange: float = 0.0
    # Token IDs for YES/NO outcomes
    token_id_yes: Optional[str] = None
    token_id_no: Optional[str] = None

    @property
    def is_recommended(self) -> bool:
        return self.recommendation == "RECOMMENDED"


class MarketAnalyzer:
    """Analyze Polymarket data for PM4 trading suitability."""

    def __init__(self, base_url: str = "https://gamma-api.polymarket.com"):
        self.base_url = base_url
        self.session = requests.Session()

    def get_market_data(self, market_slug: str) -> Optional[Dict]:
        """
        Fetch comprehensive market data from Polymarket API.
        
        Uses the correct Gamma API endpoints per Polymarket documentation:
        - GET /events/slug/{slug} for events
        - GET /markets/slug/{slug} for markets
        
        Reference: https://docs.polymarket.com/developers/gamma-markets-api/fetch-markets-guide
        """
        # Try events endpoint first (most markets are events)
        event_url = f"{self.base_url}/events/slug/{market_slug}"
        market_url = f"{self.base_url}/markets/slug/{market_slug}"
        
        try:
            # Try events endpoint first
            response = self.session.get(event_url, timeout=10)
            if response.status_code == 200:
                event_data = response.json()
                # Events contain markets, so extract the first market if available
                if isinstance(event_data, dict):
                    # If event has markets array, return the event with first market
                    if 'markets' in event_data and isinstance(event_data['markets'], list) and len(event_data['markets']) > 0:
                        # Merge event data with market data
                        market_data = event_data['markets'][0]
                        market_data.update({
                            'event_id': event_data.get('id'),
                            'event_slug': event_data.get('slug'),
                            'event_question': event_data.get('question')
                        })
                        return market_data
                    # If no markets array, return event data as-is
                    return event_data
                return event_data
            
            # If event endpoint fails, try markets endpoint
            response = self.session.get(market_url, timeout=10)
            if response.status_code == 200:
                return response.json()
            
            # If both fail, return None
            return None
            
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
                reasons=["Failed to fetch market data"],
                end_date=None,
                start_date=None,
                volume24hr=0.0,
                volume1wk=0.0,
                volume24hrAmm=0.0,
                volume1wkAmm=0.0,
                volume24hrClob=0.0,
                volume1wkClob=0.0,
                volumeAmm=0.0,
                volumeClob=0.0,
                liquidityAmm=0.0,
                liquidityClob=0.0,
                rewardsMinSize=0.0,
                rewardsMaxSpread=0.0,
                spread=0.0,
                bestBid=0.0,
                bestAsk=0.0,
                oneDayPriceChange=0.0,
                oneHourPriceChange=0.0,
                oneWeekPriceChange=0.0,
                token_id_yes=None,
                token_id_no=None
            )

        # Extract basic market info
        condition_id = data.get('conditionId', data.get('id', ''))
        volume_24h = float(data.get('volume', data.get('liquidity', 0)))
        active_traders = int(data.get('activeUsers', data.get('uniqueTraders', 0)))

        # Get current price - API may have different field names
        current_price = 0.5  # Default
        try:
            # Try various possible price field names
            if 'outcomePrices' in data:
                prices = data.get('outcomePrices', [])
                if isinstance(prices, list) and len(prices) > 0:
                    current_price = float(prices[0])
            elif 'price' in data:
                current_price = float(data.get('price', 0.5))
            elif 'yesPrice' in data:
                current_price = float(data.get('yesPrice', 0.5))
        except (ValueError, TypeError, IndexError):
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

        # Extract extended fields from API response
        def safe_float(value, default=0.0):
            """Safely convert to float with default."""
            try:
                return float(value) if value is not None else default
            except (ValueError, TypeError):
                return default

        end_date = data.get('endDate', None)
        start_date = data.get('startDate', None)
        volume24hr = safe_float(data.get('volume24hr', data.get('volume24h', 0)))
        volume1wk = safe_float(data.get('volume1wk', data.get('volume1w', 0)))
        volume24hrAmm = safe_float(data.get('volume24hrAmm', data.get('volume24hAmm', 0)))
        volume1wkAmm = safe_float(data.get('volume1wkAmm', data.get('volume1wAmm', 0)))
        volume24hrClob = safe_float(data.get('volume24hrClob', data.get('volume24hClob', 0)))
        volume1wkClob = safe_float(data.get('volume1wkClob', data.get('volume1wClob', 0)))
        volumeAmm = safe_float(data.get('volumeAmm', 0))
        volumeClob = safe_float(data.get('volumeClob', 0))
        liquidityAmm = safe_float(data.get('liquidityAmm', 0))
        liquidityClob = safe_float(data.get('liquidityClob', 0))
        
        # Extract order book and price change fields
        rewardsMinSize = safe_float(data.get('rewardsMinSize', 0))
        rewardsMaxSpread = safe_float(data.get('rewardsMaxSpread', 0))
        spread = safe_float(data.get('spread', 0))
        bestBid = safe_float(data.get('bestBid', 0))
        bestAsk = safe_float(data.get('bestAsk', 0))
        oneDayPriceChange = safe_float(data.get('oneDayPriceChange', 0))
        oneHourPriceChange = safe_float(data.get('oneHourPriceChange', data.get('oneHourPriceChange', 0)))
        oneWeekPriceChange = safe_float(data.get('oneWeekPriceChange', 0))
        
        # Extract token IDs from clobTokenIds array
        token_id_yes = None
        token_id_no = None
        clob_token_ids = data.get('clobTokenIds', [])
        
        # Handle case where clobTokenIds might be a JSON string
        if isinstance(clob_token_ids, str):
            try:
                import json
                clob_token_ids = json.loads(clob_token_ids)
            except (json.JSONDecodeError, ValueError):
                clob_token_ids = []
        
        if isinstance(clob_token_ids, list) and len(clob_token_ids) >= 2:
            # First token is typically YES, second is NO
            token_id_yes = str(clob_token_ids[0])
            token_id_no = str(clob_token_ids[1])
        # Also check for tokens array if available
        elif 'tokens' in data:
            tokens = data['tokens']
            # Handle JSON string
            if isinstance(tokens, str):
                try:
                    import json
                    tokens = json.loads(tokens)
                except (json.JSONDecodeError, ValueError):
                    tokens = []
            if isinstance(tokens, list):
                for token in tokens:
                    if isinstance(token, dict):
                        outcome = token.get('outcome', '').upper()
                        token_id = token.get('token_id') or token.get('id')
                        if outcome == 'YES' and token_id:
                            token_id_yes = str(token_id)
                        elif outcome == 'NO' and token_id:
                            token_id_no = str(token_id)

        return MarketAnalysis(
            market_slug=market_slug,
            condition_id=condition_id,
            volume_24h=volume_24h,
            active_traders=active_traders,
            last_trade_hours=hours_since_trade,
            price_range_24h=price_range,
            current_price=current_price,
            time_to_resolution_days=days_to_resolution,
            recommendation=recommendation,
            reasons=reasons,
            end_date=end_date,
            start_date=start_date,
            volume24hr=volume24hr,
            volume1wk=volume1wk,
            volume24hrAmm=volume24hrAmm,
            volume1wkAmm=volume1wkAmm,
            volume24hrClob=volume24hrClob,
            volume1wkClob=volume1wkClob,
            volumeAmm=volumeAmm,
            volumeClob=volumeClob,
            liquidityAmm=liquidityAmm,
            liquidityClob=liquidityClob,
            rewardsMinSize=rewardsMinSize,
            rewardsMaxSpread=rewardsMaxSpread,
            spread=spread,
            bestBid=bestBid,
            bestAsk=bestAsk,
            oneDayPriceChange=oneDayPriceChange,
            oneHourPriceChange=oneHourPriceChange,
            oneWeekPriceChange=oneWeekPriceChange,
            token_id_yes=token_id_yes,
            token_id_no=token_id_no
        )

    def print_analysis_report(self, analysis: MarketAnalysis) -> None:
        """Print formatted analysis report."""
        print(f"\n{'='*60}")
        print(f"MARKET ANALYSIS: {analysis.market_slug}")
        print(f"{'='*60}")
        print(f"Condition ID: {analysis.condition_id}")
        print(f"Current Price: {analysis.current_price:.3f}")
        
        # Dates
        if analysis.start_date:
            print(f"Start Date: {analysis.start_date}")
        if analysis.end_date:
            print(f"End Date: {analysis.end_date}")
        print(f"Time to Resolution: {analysis.time_to_resolution_days} days")
        
        # Volume metrics
        print(f"\n--- Volume Metrics ---")
        print(f"24h Volume (Total): ${analysis.volume_24h:,.2f}")
        if analysis.volume24hr > 0:
            print(f"24h Volume (API): ${analysis.volume24hr:,.2f}")
        if analysis.volume1wk > 0:
            print(f"1 Week Volume: ${analysis.volume1wk:,.2f}")
        
        # AMM vs CLOB breakdown
        if analysis.volume24hrAmm > 0 or analysis.volume24hrClob > 0:
            print(f"\n--- 24h Volume Breakdown ---")
            print(f"  AMM: ${analysis.volume24hrAmm:,.2f}")
            print(f"  CLOB: ${analysis.volume24hrClob:,.2f}")
        
        if analysis.volume1wkAmm > 0 or analysis.volume1wkClob > 0:
            print(f"\n--- 1 Week Volume Breakdown ---")
            print(f"  AMM: ${analysis.volume1wkAmm:,.2f}")
            print(f"  CLOB: ${analysis.volume1wkClob:,.2f}")
        
        if analysis.volumeAmm > 0 or analysis.volumeClob > 0:
            print(f"\n--- Total Volume Breakdown ---")
            print(f"  AMM: ${analysis.volumeAmm:,.2f}")
            print(f"  CLOB: ${analysis.volumeClob:,.2f}")
        
        # Liquidity metrics
        if analysis.liquidityAmm > 0 or analysis.liquidityClob > 0:
            print(f"\n--- Liquidity Breakdown ---")
            print(f"  AMM: ${analysis.liquidityAmm:,.2f}")
            print(f"  CLOB: ${analysis.liquidityClob:,.2f}")
        
        # Order book metrics
        if analysis.bestBid > 0 or analysis.bestAsk > 0:
            print(f"\n--- Order Book ---")
            print(f"Best Bid: {analysis.bestBid:.4f}")
            print(f"Best Ask: {analysis.bestAsk:.4f}")
            print(f"Spread: {analysis.spread:.4f} ({analysis.spread*100:.2f}%)")
        
        # Price changes
        if analysis.oneHourPriceChange != 0 or analysis.oneDayPriceChange != 0 or analysis.oneWeekPriceChange != 0:
            print(f"\n--- Price Changes ---")
            if analysis.oneHourPriceChange != 0:
                print(f"1 Hour: {analysis.oneHourPriceChange:+.4f} ({analysis.oneHourPriceChange*100:+.2f}%)")
            if analysis.oneDayPriceChange != 0:
                print(f"1 Day: {analysis.oneDayPriceChange:+.4f} ({analysis.oneDayPriceChange*100:+.2f}%)")
            if analysis.oneWeekPriceChange != 0:
                print(f"1 Week: {analysis.oneWeekPriceChange:+.4f} ({analysis.oneWeekPriceChange*100:+.2f}%)")
        
        # Rewards info
        if analysis.rewardsMinSize > 0 or analysis.rewardsMaxSpread > 0:
            print(f"\n--- Liquidity Rewards ---")
            print(f"Min Size: ${analysis.rewardsMinSize:,.0f}")
            print(f"Max Spread: {analysis.rewardsMaxSpread:.2f}%")
        
        # Token IDs
        if analysis.token_id_yes or analysis.token_id_no:
            print(f"\n--- Token IDs ---")
            if analysis.token_id_yes:
                print(f"YES Token ID: {analysis.token_id_yes}")
            if analysis.token_id_no:
                print(f"NO Token ID: {analysis.token_id_no}")
        
        # Other metrics
        print(f"\n--- Market Activity ---")
        print(f"Active Traders: {analysis.active_traders}")
        print(f"Last Trade: {analysis.last_trade_hours:.1f} hours ago")
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
