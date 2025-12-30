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
        r'polymarket\.com/event/([^/?]+)',            # Direct event URLs: /event/market-slug (no event-id)
        r'gamma\.polymarket\.com/market/([^/?]+)',    # Gamma market URLs
        r'https?://[^/]+/market/([^/?]+)',            # Generic market URLs
        r'https?://[^/]+/event/[^/]+/([^/?]+)',       # Generic event URLs with event-id
        r'https?://[^/]+/event/([^/?]+)'              # Generic direct event URLs
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_slug)
        if match:
            return match.group(1)

    raise ValueError(f"Could not extract market slug from: {url_or_slug}. Please provide either a Polymarket URL or market slug.")


@dataclass
class MarketAnalysis:
    """Market status report with factual metrics for market making evaluation."""
    market_slug: str
    condition_id: str
    # Core market making metrics (most important)
    spread: float  # Bid-ask spread (0-1 scale)
    bestBid: float
    bestAsk: float
    liquidityClob: float  # CLOB liquidity (USD)
    liquidityAmm: float  # AMM liquidity (USD)
    current_price: float
    # Activity metrics
    volume24hr: float  # 24h volume (USD)
    volume24hrClob: float  # 24h CLOB volume (USD)
    volume24hrAmm: float  # 24h AMM volume (USD)
    last_trade_hours: Optional[float]  # None if unknown but recent activity, 999 if no activity
    # Market structure
    time_to_resolution_days: int
    end_date: Optional[str] = None
    start_date: Optional[str] = None
    created_date: Optional[str] = None
    # Extended metrics
    volume1wk: float = 0.0
    volume1wkAmm: float = 0.0
    volume1wkClob: float = 0.0
    volumeAmm: float = 0.0
    volumeClob: float = 0.0
    active_traders: int = 0
    # Price movement
    oneHourPriceChange: float = 0.0
    oneDayPriceChange: float = 0.0
    oneWeekPriceChange: float = 0.0
    # Liquidity rewards
    rewardsMinSize: float = 0.0
    rewardsMaxSpread: float = 0.0
    # Token IDs
    token_id_yes: Optional[str] = None
    token_id_no: Optional[str] = None
    # Legacy fields (kept for compatibility)
    volume_24h: float = 0.0
    price_range_24h: Tuple[float, float] = (0.0, 1.0)
    
    @property
    def recommendation(self) -> str:
        """
        Simple status based on key market making requirements.
        Returns factual status, not a recommendation.
        """
        # Check if we have critical data
        if self.spread == 0 and self.bestBid == 0:
            return "NO_DATA"
        
        # Check critical market making requirements
        has_liquidity = (self.liquidityClob + self.liquidityAmm) > 1000
        has_tight_spread = self.spread > 0 and self.spread < 0.05
        has_activity = self.volume24hr > 10000 or (self.last_trade_hours is not None and self.last_trade_hours < 24)
        has_time = self.time_to_resolution_days >= 7
        
        if has_liquidity and has_tight_spread and has_activity and has_time:
            return "VIABLE"
        elif has_liquidity and has_activity:
            return "MARGINAL"
        else:
            return "LIMITED"


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
                spread=0.0,
                bestBid=0.0,
                bestAsk=0.0,
                liquidityClob=0.0,
                liquidityAmm=0.0,
                current_price=0.5,
                volume24hr=0.0,
                volume24hrClob=0.0,
                volume24hrAmm=0.0,
                last_trade_hours=999.0,  # No data available
                time_to_resolution_days=0,
                end_date=None,
                start_date=None,
                created_date=None,
                volume_24h=0.0,
                price_range_24h=(0.0, 1.0)
            )

        # Extract basic market info
        condition_id = data.get('conditionId', data.get('id', ''))
        active_traders = int(data.get('activeUsers', data.get('uniqueTraders', 0)))

        def safe_float(value, default=0.0):
            """Safely convert to float with default."""
            try:
                return float(value) if value is not None else default
            except (ValueError, TypeError):
                return default

        # Extract dates
        end_date = data.get('endDate', None)
        start_date = data.get('startDate', None)
        created_date = data.get('createdAt', data.get('created_at', None))
        
        # Calculate time to resolution
        try:
            if end_date:
                end_date_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                now = datetime.now(end_date_dt.tzinfo)
                days_to_resolution = max(0, (end_date_dt - now).days)
            else:
                days_to_resolution = 365  # Default assumption
        except Exception:
            days_to_resolution = 365

        # Extract order book metrics (most important for market making)
        bestBid = safe_float(data.get('bestBid', 0))
        bestAsk = safe_float(data.get('bestAsk', 0))
        spread = safe_float(data.get('spread', 0))
        # Calculate spread from bid/ask if not provided
        if spread == 0 and bestBid > 0 and bestAsk > 0:
            spread = bestAsk - bestBid

        # Get current price (prefer mid price from bid/ask, then try API fields)
        current_price = 0.5  # Default
        # First try to calculate from bid/ask (most reliable)
        if bestBid > 0 and bestAsk > 0:
            current_price = (bestBid + bestAsk) / 2.0
        else:
            # Fall back to API price fields
            try:
                if 'outcomePrices' in data:
                    prices = data.get('outcomePrices', [])
                    if isinstance(prices, list) and len(prices) > 0:
                        current_price = float(prices[0])
                elif 'price' in data:
                    current_price = float(data.get('price', 0.5))
                elif 'yesPrice' in data:
                    current_price = float(data.get('yesPrice', 0.5))
            except (ValueError, TypeError, IndexError):
                pass  # Keep default 0.5

        # Extract liquidity (critical for market making)
        liquidityClob = safe_float(data.get('liquidityClob', 0))
        liquidityAmm = safe_float(data.get('liquidityAmm', 0))
        
        # Extract volume metrics
        volume24hr = safe_float(data.get('volume24hr', data.get('volume24h', 0)))
        volume1wk = safe_float(data.get('volume1wk', data.get('volume1w', 0)))
        volume24hrAmm = safe_float(data.get('volume24hrAmm', data.get('volume24hAmm', 0)))
        volume1wkAmm = safe_float(data.get('volume1wkAmm', data.get('volume1wAmm', 0)))
        volume24hrClob = safe_float(data.get('volume24hrClob', data.get('volume24hClob', 0)))
        volume1wkClob = safe_float(data.get('volume1wkClob', data.get('volume1wClob', 0)))
        volumeAmm = safe_float(data.get('volumeAmm', 0))
        volumeClob = safe_float(data.get('volumeClob', 0))
        
        # Extract price changes
        oneDayPriceChange = safe_float(data.get('oneDayPriceChange', 0))
        oneHourPriceChange = safe_float(data.get('oneHourPriceChange', 0))
        oneWeekPriceChange = safe_float(data.get('oneWeekPriceChange', 0))
        
        # Extract liquidity rewards
        rewardsMinSize = safe_float(data.get('rewardsMinSize', 0))
        rewardsMaxSpread = safe_float(data.get('rewardsMaxSpread', 0))
        
        # Check recent activity
        # Note: Polymarket Gamma API doesn't provide lastTradeTimestamp
        # We can only infer activity from volume data
        last_trade_ts = data.get('lastTradeTimestamp', None)
        if last_trade_ts:
            # If timestamp is provided (in milliseconds), calculate hours
            if isinstance(last_trade_ts, (int, float)) and last_trade_ts > 0:
                # Handle both milliseconds and seconds
                if last_trade_ts < 1e10:  # Likely seconds
                    last_trade_ts = int(last_trade_ts * 1000)
                hours_since_trade = (now_ms() - last_trade_ts) / (1000 * 3600)
            else:
                hours_since_trade = None  # Invalid timestamp
        else:
            # No timestamp available - infer from volume
            # If there's 24h volume, there was trading recently, but we don't know exactly when
            if volume24hr > 0:
                hours_since_trade = None  # Unknown but recent (within 24h)
            else:
                hours_since_trade = 999  # No recent activity (no volume)

        # Legacy fields for compatibility
        volume_24h = volume24hr
        price_range = (max(0.01, current_price - 0.1), min(0.99, current_price + 0.1))
        
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
            # Core market making metrics
            spread=spread,
            bestBid=bestBid,
            bestAsk=bestAsk,
            liquidityClob=liquidityClob,
            liquidityAmm=liquidityAmm,
            current_price=current_price,
            # Activity metrics
            volume24hr=volume24hr,
            volume24hrClob=volume24hrClob,
            volume24hrAmm=volume24hrAmm,
            last_trade_hours=hours_since_trade,
            # Market structure
            time_to_resolution_days=days_to_resolution,
            end_date=end_date,
            start_date=start_date,
            created_date=created_date,
            # Extended metrics
            volume1wk=volume1wk,
            volume1wkAmm=volume1wkAmm,
            volume1wkClob=volume1wkClob,
            volumeAmm=volumeAmm,
            volumeClob=volumeClob,
            active_traders=active_traders,
            oneHourPriceChange=oneHourPriceChange,
            oneDayPriceChange=oneDayPriceChange,
            oneWeekPriceChange=oneWeekPriceChange,
            rewardsMinSize=rewardsMinSize,
            rewardsMaxSpread=rewardsMaxSpread,
            token_id_yes=token_id_yes,
            token_id_no=token_id_no,
            # Legacy fields
            volume_24h=volume_24h,
            price_range_24h=price_range
        )

    def print_analysis_report(self, analysis: MarketAnalysis) -> None:
        """Print factual market status report with definitions and context."""
        
        print(f"\n{'='*70}")
        print(f"MARKET STATUS REPORT: {analysis.market_slug}")
        print(f"{'='*70}")
        print(f"Condition ID: {analysis.condition_id}")
        if analysis.start_date:
            print(f"Start Date: {analysis.start_date}")
        if analysis.end_date:
            print(f"End Date: {analysis.end_date}")
        
        # ===== DEFINITIONS =====
        print(f"\n{'─'*70}")
        print("DEFINITIONS")
        print(f"{'─'*70}")
        print("Spread: Difference between best ask and best bid prices.")
        print("        Lower spread = tighter market = easier to profit from market making.")
        print("        Typical range: 0.5-5% (0.005-0.05 in probability space).")
        print()
        print("Liquidity: Available capital in order book (CLOB) or AMM pool.")
        print("          Higher liquidity = easier to enter/exit positions without slippage.")
        print("          Typical range: $1k-$100k+ for active markets.")
        print()
        print("Volume: Total trading activity over time period.")
        print("       Higher volume = more opportunities to capture spread.")
        print("       Typical range: $10k-$500k+ per day for active markets.")
        print()
        print("CLOB: Central Limit Order Book - traditional exchange with limit orders.")
        print("AMM: Automated Market Maker - liquidity pool with constant product formula.")
        print()
        
        # ===== CORE MARKET MAKING METRICS (Most Important) =====
        print(f"{'─'*70}")
        print("CORE MARKET MAKING METRICS")
        print(f"{'─'*70}")
        
        # Spread (most important)
        if analysis.bestBid > 0 and analysis.bestAsk > 0:
            print(f"Order Book:")
            print(f"  Best Bid:  {analysis.bestBid:.4f} ({analysis.bestBid*100:.2f}%)")
            print(f"  Best Ask:  {analysis.bestAsk:.4f} ({analysis.bestAsk*100:.2f}%)")
            print(f"  Spread:    {analysis.spread:.4f} ({analysis.spread*100:.2f}%)")
            if analysis.spread > 0:
                if analysis.spread < 0.01:
                    print(f"  Context:   Very tight spread (typical: 0.5-2%)")
                elif analysis.spread < 0.03:
                    print(f"  Context:   Moderate spread (typical: 0.5-2%)")
                elif analysis.spread < 0.05:
                    print(f"  Context:   Wide spread (typical: 0.5-2%)")
                else:
                    print(f"  Context:   Very wide spread (typical: 0.5-2%)")
        else:
            print(f"Order Book: No data available")
        
        print()
        
        # Liquidity
        total_liquidity = analysis.liquidityClob + analysis.liquidityAmm
        if total_liquidity > 0:
            print(f"Liquidity:")
            if analysis.liquidityClob > 0:
                print(f"  CLOB: ${analysis.liquidityClob:,.0f}")
            if analysis.liquidityAmm > 0:
                print(f"  AMM:  ${analysis.liquidityAmm:,.0f}")
            print(f"  Total: ${total_liquidity:,.0f}")
            if total_liquidity < 1000:
                print(f"  Context: Low liquidity (typical: $1k-$100k+)")
            elif total_liquidity < 10000:
                print(f"  Context: Moderate liquidity (typical: $1k-$100k+)")
            else:
                print(f"  Context: High liquidity (typical: $1k-$100k+)")
        else:
            print(f"Liquidity: No data available")
        
        print()
        
        # Current price
        print(f"Current Price: {analysis.current_price:.4f} ({analysis.current_price*100:.2f}%)")
        if analysis.current_price < 0.1:
            print(f"  Context: Low extreme (<10%) - limited upward price movement room")
        elif analysis.current_price > 0.9:
            print(f"  Context: High extreme (>90%) - limited downward price movement room")
        elif analysis.current_price < 0.2:
            print(f"  Context: Near low extreme (10-20%) - reduced upward movement room")
        elif analysis.current_price > 0.8:
            print(f"  Context: Near high extreme (80-90%) - reduced downward movement room")
        else:
            print(f"  Context: Mid-range price (20-80%) - typical for market making")
        
        print()
        
        # ===== ACTIVITY METRICS =====
        print(f"{'─'*70}")
        print("ACTIVITY METRICS")
        print(f"{'─'*70}")
        
        # Volume metrics
        if analysis.volume24hr > 0:
            print(f"24h Volume:")
            print(f"  Total: ${analysis.volume24hr:,.0f}")
            if analysis.volume24hrClob > 0:
                print(f"  CLOB: ${analysis.volume24hrClob:,.0f} ({analysis.volume24hrClob/analysis.volume24hr*100:.1f}%)")
            if analysis.volume24hrAmm > 0:
                print(f"  AMM:  ${analysis.volume24hrAmm:,.0f} ({analysis.volume24hrAmm/analysis.volume24hr*100:.1f}%)")
            
            if analysis.volume24hr < 10000:
                print(f"  Context: Low volume (typical: $10k-$500k+ per day)")
            elif analysis.volume24hr < 50000:
                print(f"  Context: Moderate volume (typical: $10k-$500k+ per day)")
            else:
                print(f"  Context: High volume (typical: $10k-$500k+ per day)")
        else:
            print(f"24h Volume: No data available")
        
        if analysis.volume1wk > 0:
            print(f"1 Week Volume: ${analysis.volume1wk:,.0f}")
        
        print()
        
        # Price changes
        if analysis.oneHourPriceChange != 0 or analysis.oneDayPriceChange != 0 or analysis.oneWeekPriceChange != 0:
            print(f"Price Changes:")
            if analysis.oneHourPriceChange != 0:
                print(f"  1 Hour:  {analysis.oneHourPriceChange*100:+.2f}%")
            if analysis.oneDayPriceChange != 0:
                print(f"  1 Day:   {analysis.oneDayPriceChange*100:+.2f}%")
            if analysis.oneWeekPriceChange != 0:
                print(f"  1 Week:  {analysis.oneWeekPriceChange*100:+.2f}%")
            print()
        
        # Additional activity indicators
        if analysis.active_traders > 0:
            print(f"Active Traders: {analysis.active_traders}")
            print()
        
        # Liquidity rewards (if available)
        if analysis.rewardsMinSize > 0:
            print(f"Liquidity Rewards:")
            print(f"  Min Size: ${analysis.rewardsMinSize:,.0f}")
            if analysis.rewardsMaxSpread > 0:
                print(f"  Max Spread: {analysis.rewardsMaxSpread:.2f}%")
            print()
        
        # ===== MARKET STRUCTURE =====
        print(f"{'─'*70}")
        print("MARKET STRUCTURE")
        print(f"{'─'*70}")
        
        # Market creation date
        if analysis.created_date:
            try:
                created_dt = datetime.fromisoformat(analysis.created_date.replace('Z', '+00:00'))
                now = datetime.now(created_dt.tzinfo)
                days_since_creation = (now - created_dt).days
                print(f"Created: {analysis.created_date[:10]} ({days_since_creation} days ago)")
            except Exception:
                print(f"Created: {analysis.created_date}")
        
        # Start and end dates
        if analysis.start_date:
            print(f"Start Date: {analysis.start_date[:10] if len(analysis.start_date) > 10 else analysis.start_date}")
        if analysis.end_date:
            print(f"End Date: {analysis.end_date[:10] if len(analysis.end_date) > 10 else analysis.end_date}")
        
        print(f"Time to Resolution: {analysis.time_to_resolution_days} days")
        if analysis.time_to_resolution_days < 7:
            print(f"  Context: Short horizon - limited trading window")
        elif analysis.time_to_resolution_days < 30:
            print(f"  Context: Medium horizon (typical: 30+ days preferred)")
        else:
            print(f"  Context: Long horizon - extended trading opportunity")
        
        print()
        
        # ===== TECHNICAL DETAILS =====
        if analysis.token_id_yes or analysis.token_id_no:
            print(f"{'─'*70}")
            print("TECHNICAL DETAILS")
            print(f"{'─'*70}")
            if analysis.token_id_yes:
                print(f"YES Token ID: {analysis.token_id_yes}")
            if analysis.token_id_no:
                print(f"NO Token ID: {analysis.token_id_no}")
            print()
        
        print(f"{'='*70}\n")


def main():
    """Command-line interface for market analysis."""
    import argparse
    import os
    import sys
    from io import StringIO

    parser = argparse.ArgumentParser(
        description="Analyze Polymarket for PM4 trading suitability"
    )
    parser.add_argument(
        "market_input",
        help="Polymarket market URL or slug (e.g., 'https://polymarket.com/market/will-ethereum-reach-10k-before-2025' or 'will-ethereum-reach-10k-before-2025')"
    )
    parser.add_argument(
        "--output", "-o",
        help="Save report to file (default: print to console)",
        type=str,
        default=None
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
    
    # If output file specified, capture output and save to file
    if args.output:
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            analyzer.print_analysis_report(analysis)
            report_content = captured_output.getvalue()
        finally:
            sys.stdout = old_stdout
        
        # Save to file
        output_path = args.output
        # If relative path, save to data/temp/ directory
        if not os.path.isabs(output_path):
            os.makedirs("data/temp", exist_ok=True)
            output_path = os.path.join("data/temp", output_path)
        
        with open(output_path, 'w') as f:
            f.write(report_content)
        
        print(f"✓ Report saved to: {output_path}")
        # Also print to console
        print(report_content)
    else:
        # Print to console only
        analyzer.print_analysis_report(analysis)


if __name__ == "__main__":
    main()
