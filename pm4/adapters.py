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
        AssetType, BalanceAllowanceParams, ApiKeyCreds, TradeParams
    )
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
    """Polymarket CLOB exchange adapter."""

    def __init__(self, asset_yes: str, asset_no: str):
        self.asset_yes = asset_yes
        self.asset_no = asset_no

        # 1. Load Secrets from ENV
        pk = os.getenv("PK")
        api_key = os.getenv("CLOB_API_KEY")
        api_secret = os.getenv("CLOB_SECRET")
        api_passphrase = os.getenv("CLOB_PASS_PHRASE")
        funder = os.getenv("FUNDER_ADDRESS")
        host = os.getenv("CLOB_HOST", "https://clob.polymarket.com")
        chain_id = int(os.getenv("CHAIN_ID", "137"))
        sig_type = int(os.getenv("POLY_SIGNATURE_TYPE", "1")) # 1=Magic, 2=EOA

        if not pk:
            raise ValueError("PK not found in .env")
        if not funder:
            print("Warning: FUNDER_ADDRESS not set in .env. Orders might fail if Proxy is needed.")

        # 2. Configure L2 Credentials if provided
        creds = None
        if api_key and api_secret and api_passphrase:
            creds = ApiKeyCreds(
                api_key=api_key,
                api_secret=api_secret,
                api_passphrase=api_passphrase
            )

        # 3. Initialize Client
        print(f"Initializing ClobClient (Host: {host}, Chain: {chain_id}, Funder: {funder})...")
        self.client = ClobClient(
            host,
            key=pk,
            chain_id=chain_id,
            signature_type=sig_type,
            funder=funder,
            creds=creds
        )

        # 4. Auto-derive if no L2 keys provided
        if not creds:
            print("No L2 keys in .env, attempting derivation...")
            try:
                new_creds = self.client.create_or_derive_api_creds()
                self.client.set_api_creds(new_creds)
                print("Derived credentials successfully.")
            except Exception as e:
                print(f"Credential derivation failed: {e}")
                sys.exit(1)
        else:
            print("Using L2 API Keys from .env.")

    async def get_balances(self) -> Dict[str, float]:
        def _fetch():
            usdc = self.client.get_balance_allowance(
                params=BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            )
            yes = self.client.get_balance_allowance(
                params=BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL, token_id=self.asset_yes)
            )
            no = self.client.get_balance_allowance(
                params=BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL, token_id=self.asset_no)
            )
            return {
                "USDC": float(usdc.get("balance", 0)),
                "YES": float(yes.get("balance", 0)),
                "NO": float(no.get("balance", 0)),
            }
        return await asyncio.to_thread(_fetch)

    async def list_open_orders(self) -> List[Dict[str, Any]]:
        def _fetch():
            orders = self.client.get_orders(OpenOrderParams())
            out = []
            for o in orders:
                out.append({
                    "order_id": o.get("id"),
                    "side": o.get("side"),
                    "asset_id": o.get("asset_id"),
                    "price": float(o.get("price")),
                    "size": float(o.get("size")),
                    "size_remaining": float(o.get("size_matched", 0)) if "size_matched" in o else float(o.get("size"))
                })
            return out
        return await asyncio.to_thread(_fetch)

    async def cancel_order(self, order_id: str) -> None:
        def _exec():
            self.client.cancel(order_id)
        await asyncio.to_thread(_exec)

    async def place_limit_order(self, asset_id: str, side: str, price: float, size: float) -> str:
        def _exec():
            clob_side = BUY if side == "BUY" else SELL
            args = OrderArgs(price=price, size=size, side=clob_side, token_id=asset_id)
            resp = self.client.create_and_post_order(args, OrderType.GTC)
            if resp and "orderID" in resp:
                return resp["orderID"]
            if resp and "errorMsg" in resp:
                raise Exception(resp["errorMsg"])
            return ""
        return await asyncio.to_thread(_exec)

    async def get_fills(self, since_ts_ms: int) -> List[Dict[str, Any]]:
        def _fetch():
            trades = self.client.get_trades(TradeParams(limit=20))
            out = []
            for t in trades:
                ts = int(t.get("timestamp", 0) * 1000)
                if ts <= since_ts_ms:
                    continue
                out.append({
                    "ts_ms": ts,
                    "side": t.get("side"),
                    "asset_id": t.get("asset_id"),
                    "price": float(t.get("price")),
                    "size": float(t.get("size")),
                    "order_id": t.get("order_id")
                })
            return out
        return await asyncio.to_thread(_fetch)
