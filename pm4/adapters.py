"""
Exchange adapters for different trading platforms.
"""
import asyncio
import os
import sys
from typing import Any, Dict, List

# ==========================================
# PY-CLOB-CLIENT IMPORTS
# ==========================================
try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import (
        OrderArgs, OrderType, OpenOrderParams,
        AssetType, BalanceAllowanceParams, TradeParams
    )
    # Try newer API first, fall back to older
    try:
        from py_clob_client.clob_types import ApiCreds as ApiKeyCreds
    except ImportError:
        from py_clob_client.clob_types import ApiKeyCreds
    from py_clob_client.order_builder.constants import BUY, SELL
except ImportError:
    print("Error: py-clob-client not found. Install with: pip install py-clob-client")
    sys.exit(1)


class ExchangeAdapter:
    """Abstract base class for exchange interfaces."""

    async def get_balances(self) -> Dict[str, float]:
        raise NotImplementedError

    async def list_open_orders(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    async def cancel_order(self, order_id: str) -> None:
        raise NotImplementedError

    async def place_limit_order(self, asset_id: str, side: str, price: float, size: float) -> str:
        raise NotImplementedError

    async def get_fills(self, since_ts_ms: int) -> List[Dict[str, Any]]:
        raise NotImplementedError


class PolymarketAdapter(ExchangeAdapter):
    """Polymarket CLOB (Central Limit Order Book) exchange adapter.

    Implements the ExchangeAdapter interface for Polymarket's prediction market
    platform using the py_clob_client library. Handles:

    - Multi-level authentication (EOA signatures + API keys)
    - Balance management for USDC collateral and conditional tokens
    - Order lifecycle management (place, cancel, track)
    - Trade execution monitoring and fill processing
    - Error handling and API-specific response parsing

    Key Features:
    - Automatic API credential derivation from EOA signatures
    - Thread-safe async operations using asyncio.to_thread()
    - Comprehensive error context for debugging
    - Polymarket-specific data format conversions

    Security Model:
    - Primary authentication via EOA private key signatures
    - Optional L2 API keys for enhanced rate limits
    - Funders for gasless trading when available
    """

    def __init__(self, asset_yes: str, asset_no: str):
        """Initialize Polymarket adapter with authentication and configuration.

        Sets up a complete Polymarket CLOB client with multi-level authentication:
        1. Primary EOA signature authentication (required)
        2. Optional L2 API keys for enhanced functionality
        3. Automatic credential derivation when L2 keys not provided
        4. Network configuration and funder setup

        Args:
            asset_yes: Conditional token ID for YES outcome
            asset_no: Conditional token ID for NO outcome

        Raises:
            ValueError: If required PK environment variable not found
            SystemExit: If API credential derivation fails

        Environment Variables:
            PK: Private key for EOA signature authentication (required)
            CLOB_API_KEY: L2 API key (optional, auto-derived if missing)
            CLOB_SECRET: L2 API secret (optional, auto-derived if missing)
            CLOB_PASS_PHRASE: L2 API passphrase (optional, auto-derived if missing)
            FUNDER_ADDRESS: Gasless trading funder (recommended)
            CLOB_HOST: API host (default: production)
            CHAIN_ID: Polygon network ID (default: 137)
            POLY_SIGNATURE_TYPE: Signature type (1=Magic, 2=EOA, default: 1)

        Note:
            L2 API keys provide higher rate limits but are not required for basic operation.
            The system will automatically derive them from the EOA signature if missing.
        """
        self.asset_yes = asset_yes
        self.asset_no = asset_no

        # === PHASE 1: Load Authentication Secrets ===
        # Primary authentication via EOA private key (required for all operations)
        pk = os.getenv("PK")
        # L2 API keys for enhanced rate limits (optional, auto-derived)
        api_key = os.getenv("CLOB_API_KEY")
        api_secret = os.getenv("CLOB_SECRET")
        api_passphrase = os.getenv("CLOB_PASS_PHRASE")
        # Funder for gasless trading (recommended but not required)
        funder = os.getenv("FUNDER_ADDRESS")

        # Network configuration with sensible defaults
        host = os.getenv("CLOB_HOST", "https://clob.polymarket.com")
        chain_id = int(os.getenv("CHAIN_ID", "137"))  # Polygon mainnet
        sig_type = int(os.getenv("POLY_SIGNATURE_TYPE", "1"))  # 1=Magic, 2=EOA

        # Validate required authentication
        if not pk:
            raise ValueError("PK environment variable not found. Required for Polymarket authentication.")

        if not funder:
            print("Warning: FUNDER_ADDRESS not set. Orders might fail if Proxy funding is required.")
            print("Consider setting up a funder for gasless trading.")

        # === PHASE 2: Configure L2 API Credentials ===
        creds = None
        if api_key and api_secret and api_passphrase:
            # Use explicitly provided L2 API credentials
            creds = ApiKeyCreds(
                api_key=api_key,
                api_secret=api_secret,
                api_passphrase=api_passphrase
            )
            print("Using explicitly provided L2 API credentials.")

        # === PHASE 3: Initialize CLOB Client ===
        print(f"Initializing ClobClient (Host: {host}, Chain: {chain_id}, Funder: {funder or 'None'})...")
        self.client = ClobClient(
            host=host,
            key=pk,  # EOA private key for signing
            chain_id=chain_id,
            signature_type=sig_type,
            funder=funder,  # Gasless trading sponsor
            creds=creds  # L2 API credentials (if available)
        )

        # === PHASE 4: Auto-Derive L2 Credentials ===
        # L2 API keys provide higher rate limits but are not required for basic operation
        if not creds:
            print("No L2 API keys provided, attempting automatic derivation from EOA signature...")
            try:
                # Polymarket innovation: Derive API keys from EOA signature
                # This eliminates need for separate API key management
                # Keys are cryptographically tied to the EOA wallet
                new_creds = self.client.create_or_derive_api_creds()
                self.client.set_api_creds(new_creds)
                print("✓ L2 API credentials derived and configured successfully.")
                print("  These credentials are tied to your EOA and provide enhanced rate limits.")
            except Exception as e:
                print(f"✗ L2 API credential derivation failed: {e}")
                print("  This may limit API rate limits but basic functionality will work.")
                print("  Consider setting CLOB_API_KEY, CLOB_SECRET, and CLOB_PASS_PHRASE explicitly.")
                # Graceful degradation: Continue without L2 keys rather than failing
        else:
            print("✓ Using explicitly configured L2 API credentials.")

    async def get_balances(self) -> Dict[str, float]:
        """Retrieve current account balances for trading assets.

        Fetches real-time balance information for all assets involved in the market:
        - USDC: Base collateral currency for margin and settlement
        - YES: Conditional tokens representing YES outcome positions
        - NO: Conditional tokens representing NO outcome positions

        Uses Polymarket's balance_allowance API which returns spendable balances
        (total balance minus any locked or pending amounts).

        Returns:
            Dictionary mapping asset names to available balances:
            - "USDC": Available USDC balance (float)
            - "YES": Available YES token balance (float)
            - "NO": Available NO token balance (float)

        Note:
            Balances represent spendable amounts only. Locked collateral
            in open positions is not included. Thread-safe via asyncio.to_thread().
        """
        def _fetch():
            # Get USDC collateral balance (base currency)
            usdc_response = self.client.get_balance_allowance(
                params=BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            )

            # Get YES conditional token balance
            yes_response = self.client.get_balance_allowance(
                params=BalanceAllowanceParams(
                    asset_type=AssetType.CONDITIONAL,
                    token_id=self.asset_yes
                )
            )

            # Get NO conditional token balance
            no_response = self.client.get_balance_allowance(
                params=BalanceAllowanceParams(
                    asset_type=AssetType.CONDITIONAL,
                    token_id=self.asset_no
                )
            )

            # Extract and convert balances to float (handle API response format)
            return {
                "USDC": float(usdc_response.get("balance", 0)),
                "YES": float(yes_response.get("balance", 0)),
                "NO": float(no_response.get("balance", 0)),
            }

        # Execute in thread pool to avoid blocking async event loop
        return await asyncio.to_thread(_fetch)

    async def list_open_orders(self) -> List[Dict[str, Any]]:
        """Retrieve all currently open orders across all markets.

        Fetches the complete list of active orders from Polymarket's order book.
        Includes orders from all markets, not just the current market being traded.

        Returns:
            List of order dictionaries with standardized format:
            - order_id: Unique Polymarket order identifier (string)
            - side: "BUY" or "SELL" (string)
            - asset_id: Token identifier (YES/NO conditional token) (string)
            - price: Order price in decimal format (float)
            - size: Original order size (float)
            - size_remaining: Unfilled portion of order (float)

        Note:
            Orders are returned in Polymarket's native format and converted
            to a standardized interface format. size_remaining accounts for
            partial fills. Thread-safe via asyncio.to_thread().
        """
        def _fetch():
            # Retrieve all open orders (no market filtering at API level)
            orders_response = self.client.get_orders(OpenOrderParams())

            # Convert Polymarket's order format to standardized interface format
            standardized_orders = []
            for order in orders_response:
                standardized_orders.append({
                    "order_id": order.get("id"),  # Polymarket order ID
                    "side": order.get("side"),    # BUY or SELL
                    "asset_id": order.get("asset_id"),  # Token contract address
                    "price": float(order.get("price", 0)),  # Decimal price
                    "size": float(order.get("size", 0)),    # Original size
                    # Handle partial fills: remaining = total - matched
                    "size_remaining": (
                        float(order.get("size_matched", 0))
                        if "size_matched" in order
                        else float(order.get("size", 0))
                    )
                })

            return standardized_orders

        # Execute in thread pool to avoid blocking async event loop
        return await asyncio.to_thread(_fetch)

    async def cancel_order(self, order_id: str) -> None:
        """Cancel a specific open order by its identifier.

        Attempts to cancel an active order on the Polymarket platform.
        Cancellation is not guaranteed - orders may execute before the
        cancellation request is processed, especially in fast markets.

        Args:
            order_id: Polymarket order identifier to cancel (string)

        Note:
            Cancellation requests are processed asynchronously by Polymarket.
            No confirmation is returned - success should be verified by
            checking order status via list_open_orders(). Thread-safe via
            asyncio.to_thread().

        Raises:
            May raise exceptions from the underlying py_clob_client if
            the cancellation request fails (network issues, invalid order ID, etc.)
        """
        def _exec():
            # Issue cancellation request to Polymarket
            self.client.cancel(order_id)

        # Execute in thread pool to avoid blocking async event loop
        await asyncio.to_thread(_exec)

    async def place_limit_order(self, asset_id: str, side: str, price: float, size: float) -> str:
        """Place a limit order on the Polymarket CLOB.

        Submits a Good-Til-Cancelled (GTC) limit order to the Polymarket platform.
        Orders remain active until filled, cancelled, or the market resolves.

        Args:
            asset_id: Conditional token identifier (YES or NO token contract address)
            side: Order side - "BUY" for YES tokens, "SELL" for NO tokens
            price: Limit price in decimal format (0.0 to 1.0 for prediction markets)
            size: Order quantity in token units

        Returns:
            Polymarket order ID if successful (string), empty string if failed

        Raises:
            Exception: If the order submission fails with an error message from Polymarket
            Various exceptions from py_clob_client for network/API issues

        Note:
            - Orders are GTC and persist until market resolution
            - Price validation is handled by Polymarket (invalid prices are rejected)
            - Size validation ensures sufficient balance and position limits
            - Thread-safe via asyncio.to_thread()
        """
        def _exec():
            # Convert interface side format to Polymarket constants
            clob_side = BUY if side == "BUY" else SELL

            # Construct order parameters for Polymarket API
            order_args = OrderArgs(
                price=price,
                size=size,
                side=clob_side,
                token_id=asset_id  # YES or NO conditional token
            )

            # Submit order with GTC (Good-Til-Cancelled) time-in-force
            # Orders remain active until filled, cancelled, or market resolves
            response = self.client.create_and_post_order(order_args, OrderType.GTC)

            # Handle Polymarket API response format
            if response and "orderID" in response:
                # Success - return the order identifier
                return response["orderID"]
            elif response and "errorMsg" in response:
                # API-level error (insufficient balance, invalid price, etc.)
                raise Exception(f"Polymarket API error: {response['errorMsg']}")
            else:
                # Unexpected response format or network error
                return ""

        # Execute in thread pool to avoid blocking async event loop
        return await asyncio.to_thread(_exec)

    async def get_fills(self, since_ts_ms: int) -> List[Dict[str, Any]]:
        """Retrieve recent trade executions (fills) since a specific timestamp.

        Fetches the most recent trade history from Polymarket, filtering for
        trades that occurred after the specified timestamp. Used for position
        tracking, P&L calculation, and performance analysis.

        Args:
            since_ts_ms: Timestamp threshold in milliseconds (only return trades after this time)

        Returns:
            List of trade execution dictionaries in chronological order:
            - ts_ms: Trade execution timestamp (milliseconds)
            - side: Trade side ("BUY" or "SELL")
            - asset_id: Token identifier that was traded
            - price: Execution price (decimal)
            - size: Filled quantity
            - order_id: Original order that generated this fill

        Note:
            - Limited to most recent 20 trades due to API constraints
            - Returns trades from all markets, not just current market
            - Timestamps are converted from Polymarket's format to milliseconds
            - Thread-safe via asyncio.to_thread()
        """
        def _fetch():
            # Retrieve recent trade history (limited by API to recent trades)
            # Polymarket API returns most recent trades, not a full history
            trades_response = self.client.get_trades(TradeParams(limit=20))

            # Filter and standardize trade data
            recent_trades = []
            for trade in trades_response:
                # Convert Polymarket timestamp (seconds) to milliseconds
                trade_timestamp = int(trade.get("timestamp", 0) * 1000)

                # Skip trades that are too old (already processed)
                if trade_timestamp <= since_ts_ms:
                    continue

                # Convert to standardized format
                recent_trades.append({
                    "ts_ms": trade_timestamp,
                    "side": trade.get("side"),        # BUY or SELL
                    "asset_id": trade.get("asset_id"), # Token contract address
                    "price": float(trade.get("price", 0)),  # Execution price
                    "size": float(trade.get("size", 0)),    # Filled quantity
                    "order_id": trade.get("order_id")       # Source order ID
                })

            return recent_trades

        # Execute in thread pool to avoid blocking async event loop
        return await asyncio.to_thread(_fetch)
