#!/usr/bin/env python3
"""
Single-market Polymarket CLOB market maker

Usage:
    pip install -r requirements.txt
    python mm_bot.py config.json
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import math
import os
import signal
import sys
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional, Set

import websockets
from dotenv import load_dotenv

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


# Load environment variables immediately
load_dotenv()


# =========================
# Utilities
# =========================

def now_ms() -> int:
    return int(time.time() * 1000)


def clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def logit(p: float, eps: float = 1e-6) -> float:
    p = clip(p, eps, 1.0 - eps)
    return math.log(p / (1.0 - p))


def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def floor_to_tick(p: float, tick: float) -> float:
    return math.floor(p / tick) * tick


def ceil_to_tick(p: float, tick: float) -> float:
    return math.ceil(p / tick) * tick


def fmt(x: float, nd: int = 4) -> str:
    return f"{x:.{nd}f}"


# =========================
# JSONL logger
# =========================

class JsonlLogger:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._fp = open(path, "a", buffering=1)

    def write(self, event_type: str, payload: Dict[str, Any]) -> None:
        rec = {"ts_ms": now_ms(), "event": event_type, **payload}
        self._fp.write(json.dumps(rec, separators=(",", ":"), ensure_ascii=False) + "\n")

    def close(self) -> None:
        try:
            self._fp.close()
        except Exception:
            pass


# =========================
# Ladder Logic (V1)
# =========================

def build_v1_ladder(
    *,
    r_x: float,
    half_b: float,
    half_a: float,
    tick: float,
    B_side: float,
    decay: float = 0.7,
    step_mult: float = 0.5,
    min_step_logit: float = 0.05,
    max_levels: int = 5,
) -> Dict[str, List[Dict[str, Any]]]:
    x_b0 = r_x - half_b
    x_a0 = r_x + half_a
    base_step = max(step_mult * (half_b + half_a) / 2.0, min_step_logit)

    x_min = logit(max(tick, 0.001))
    x_max = logit(min(1.0 - tick, 0.999))

    bids = []
    asks = []

    if base_step > 1e-9:
        N_bid = min(max_levels, int(max(0, (x_b0 - x_min) / base_step)))
        N_ask = min(max_levels, int(max(0, (x_max - x_a0) / base_step)))
    else:
        N_bid, N_ask = 0, 0

    base_risk_unit = B_side * 0.10  

    for i in range(N_bid):
        x = x_b0 - i * base_step
        p = sigmoid(x)
        p = floor_to_tick(p, tick)
        if p <= 0.001: break
        level_risk = base_risk_unit * (decay ** i)
        size = level_risk / max(p, 1e-3)
        bids.append({"level": i, "price": p, "size": size})

    for i in range(N_ask):
        x = x_a0 + i * base_step
        p = sigmoid(x)
        p = ceil_to_tick(p, tick)
        if p >= 0.999: break
        level_risk = base_risk_unit * (decay ** i)
        size = level_risk / max(1.0 - p, 1e-3)
        asks.append({"level": i, "price": p, "size": size})

    def dedupe(levels, side):
        seen = {}
        for l in levels:
            px = l["price"]
            if px not in seen:
                seen[px] = l
            else:
                if l["level"] < seen[px]["level"]:
                    seen[px] = l
        return sorted(seen.values(), key=lambda x: x["price"], reverse=(side == "bid"))

    return {
        "bids": dedupe(bids, "bid"),
        "asks": dedupe(asks, "ask"),
    }


# =========================
# Config
# =========================

@dataclass
class WarmupConfig:
    dt_sample_s: float = 5.0
    min_return_samples: int = 360
    max_warmup_s: float = 2 * 3600
    tau_fast_s: float = 30.0
    tau_slow_s: float = 30 * 60.0
    markout_h1_s: float = 10.0
    markout_h2_s: float = 60.0
    markout_w1: float = 0.6
    markout_w2: float = 0.4


@dataclass
class RiskConfig:
    bankroll_B: float = 500.0
    n_plays: int = 3
    eta_time: float = 0.5
    slippage_buffer: float = 0.10
    gamma_a: float = 1.0
    gamma_max: float = 50.0
    lambda_min: float = 0.8
    lambda_max: float = 2.0
    beta_p: float = 0.7
    alpha_U: float = 0.5
    U_ref: float = 50.0
    w_A: float = 1.0
    w_L: float = 1.0
    s_scale: float = 1.0
    I_max: float = 3.0
    c_tox: float = 1.0
    c_sigma: float = 1.0
    nu_sigma: float = 1.4
    sigma_max: float = 6.0
    sigma_tau_up_s: float = 10.0
    sigma_tau_down_s: float = 90.0


@dataclass
class QuoteConfig:
    c_risk: float = 0.06
    kappa0: float = 1.0
    rate_ref_per_s: float = 0.05
    min_half_spread_prob: float = 0.01
    max_half_spread_logit: float = 1.5
    ladder_decay: float = 0.8        
    ladder_step_mult: float = 0.5    
    ladder_min_step_logit: float = 0.05
    ladder_max_levels: int = 5
    min_order_size: float = 1.0      
    max_order_notional_side: float = 100.0 
    refresh_s: float = 2.0
    price_move_requote_ticks: int = 1


@dataclass
class MarketConfig:
    market: str
    asset_id_yes: str
    asset_id_no: str
    start_ts_ms: int
    resolve_ts_ms: int
    wss_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


@dataclass
class BotConfig:
    market: MarketConfig
    warmup: WarmupConfig
    risk: RiskConfig
    quote: QuoteConfig
    log_path: str = "./data/mm_events.jsonl"
    calib_path: str = "./data/warm_calibration.json"


# =========================
# Exchange adapter
# =========================

class ExchangeAdapter:
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

# =========================
# Market Data & Logic
# =========================

@dataclass
class BookState:
    best_bid: float = 0.0
    best_ask: float = 1.0
    mid: float = 0.5
    tick_size: float = 0.01
    last_trade_price: Optional[float] = None
    last_book_ts_ms: int = 0
    last_trade_ts_ms: int = 0


class MarketData:
    def __init__(self, logger: JsonlLogger):
        self.state = BookState()
        self.logger = logger
        self.trade_ts: Deque[int] = deque(maxlen=5000)

    def _update_mid(self):
        b, a = self.state.best_bid, self.state.best_ask
        if b > 0 and a < 1 and b < a:
            self.state.mid = 0.5 * (b + a)

    def on_book(self, msg: Dict[str, Any]) -> None:
        bids = msg.get("bids") or msg.get("buys") or []
        asks = msg.get("asks") or msg.get("sells") or []
        if bids:
            self.state.best_bid = float(bids[0]["price"])
        if asks:
            self.state.best_ask = float(asks[0]["price"])
        self.state.last_book_ts_ms = int(msg.get("timestamp", now_ms()))
        self._update_mid()
        self.logger.write("ws_book", {"best_bid": self.state.best_bid, "best_ask": self.state.best_ask, "mid": self.state.mid, "tick": self.state.tick_size})

    def on_price_change(self, msg: Dict[str, Any]) -> None:
        pcs = msg.get("price_changes", [])
        best_bid = None
        best_ask = None
        for pc in pcs:
            if pc.get("best_bid") is not None:
                try:
                    best_bid = float(pc["best_bid"])
                except Exception:
                    pass
            if pc.get("best_ask") is not None:
                try:
                    best_ask = float(pc["best_ask"])
                except Exception:
                    pass
        if best_bid is not None:
            self.state.best_bid = best_bid
        if best_ask is not None:
            self.state.best_ask = best_ask
        self.state.last_book_ts_ms = int(msg.get("timestamp", now_ms()))
        self._update_mid()
        self.logger.write("ws_price_change", {"best_bid": self.state.best_bid, "best_ask": self.state.best_ask, "mid": self.state.mid, "n_changes": len(pcs)})

    def on_tick_size_change(self, msg: Dict[str, Any]) -> None:
        self.state.tick_size = float(msg["new_tick_size"])
        self.logger.write("ws_tick_size_change", {"tick": self.state.tick_size})

    def on_last_trade_price(self, msg: Dict[str, Any]) -> None:
        p = float(msg["price"])
        ts = int(msg.get("timestamp", now_ms()))
        self.state.last_trade_price = p
        self.state.last_trade_ts_ms = ts
        self.trade_ts.append(ts)
        self.logger.write("ws_last_trade", {"price": p, "side": msg.get("side", "UNKNOWN")})

    def trade_rate_per_s(self, window_s: float = 60.0) -> float:
        if not self.trade_ts:
            return 0.0
        t_now = now_ms()
        cutoff = t_now - int(window_s * 1000)
        n = 0
        for ts in reversed(self.trade_ts):
            if ts < cutoff:
                break
            n += 1
        return n / max(window_s, 1e-9)


class Indicators:
    def __init__(self, cfg: BotConfig, logger: JsonlLogger):
        self.cfg = cfg
        self.logger = logger
        self._sigma_smoothed = 1.0
        self._ema_fast_abs = 0.0
        self._ema_slow_abs = 0.0
        self._ema_fast_r = 0.0
        self._ema_fast_abs_r = 0.0
        self._ema_slow_abs_r = 0.0
        self._returns: Deque[float] = deque(maxlen=5000)
        self._last_sample_ts_ms: Optional[int] = None
        self._last_x: Optional[float] = None
        self._fills_pending: Deque[Dict[str, Any]] = deque(maxlen=2000)
        self._tox_ema_pos_h1 = 0.0
        self._tox_ema_pos_h2 = 0.0
        self._last_print = 0.0

    def _ema(self, prev: float, x: float, tau_s: float, dt_s: float) -> float:
        if tau_s <= 0:
            return x
        a = 1.0 - math.exp(-dt_s / tau_s)
        return prev + a * (x - prev)

    def time_factor(self, t_ms: int) -> float:
        mc = self.cfg.market
        T = max(mc.resolve_ts_ms - mc.start_ts_ms, 1) / 1000.0
        tau = max(mc.resolve_ts_ms - t_ms, 0) / 1000.0
        return (tau / T) ** self.cfg.risk.eta_time if T > 0 else 1.0

    def B_side(self) -> float:
        w = 1.0 / max(self.cfg.risk.n_plays, 1)
        return 0.5 * self.cfg.risk.bankroll_B * w

    def q_max(self, p: float, q: float, t_ms: int) -> float:
        p_opp = (1.0 - p) if q >= 0 else p
        denom = max(p_opp * (1.0 + self.cfg.risk.slippage_buffer), 1e-9)
        return (self.B_side() * self.time_factor(t_ms)) / denom

    def q_hat(self, q: float, p: float, t_ms: int) -> float:
        qm = self.q_max(p, q, t_ms)
        return clip(q / qm, -1.0, 1.0) if qm > 0 else 0.0

    def gamma(self, qhat: float) -> float:
        u = clip(abs(qhat), 0.0, 0.999999)
        g = 1.0 / ((1.0 - u) ** self.cfg.risk.gamma_a)
        return clip(g, 1.0, self.cfg.risk.gamma_max)

    def A_p(self, p: float) -> float:
        p = clip(p, 1e-6, 1 - 1e-6)
        return ((p * (1.0 - p)) / 0.25) ** self.cfg.risk.beta_p

    def L_U(self, U: float) -> float:
        Uref = max(self.cfg.risk.U_ref, 1e-9)
        return (Uref / (U + Uref)) ** self.cfg.risk.alpha_U

    def lambda_struct(self, p: float, U: float) -> float:
        A = self.A_p(p)
        L = self.L_U(U)
        s = self.cfg.risk.w_A * (A - 1.0) + self.cfg.risk.w_L * (L - 1.0)
        g = clip(s / max(self.cfg.risk.s_scale, 1e-9), -1.0, 1.0)
        lam_min, lam_max = self.cfg.risk.lambda_min, self.cfg.risk.lambda_max
        lam = 1.0 + (lam_max - 1.0) * g if g > 0 else 1.0 + (1.0 - lam_min) * g
        return clip(lam, lam_min, lam_max)

    def record_fill(self, fill: Dict[str, Any]) -> None:
        self._fills_pending.append(fill)
        self.logger.write("fill", fill)

    def update_markouts(self, t_ms: int, p_mid: float) -> None:
        x_now = logit(p_mid)
        h1_ms = int(self.cfg.warmup.markout_h1_s * 1000)
        h2_ms = int(self.cfg.warmup.markout_h2_s * 1000)
        keep: Deque[Dict[str, Any]] = deque(maxlen=self._fills_pending.maxlen)
        for f in list(self._fills_pending):
            tf = int(f["ts_ms"])
            if "x_fill" not in f:
                f["x_fill"] = logit(float(f["price"]))
            s = 1.0 if f.get("side") == "BUY" else -1.0
            x_fill = float(f["x_fill"])
            if (t_ms - tf) >= h1_ms and not f.get("h1_done"):
                mo = s * (x_now - x_fill)
                pos = max(0.0, mo)
                self._tox_ema_pos_h1 = self._ema(self._tox_ema_pos_h1, pos, self.cfg.warmup.tau_fast_s, self.cfg.warmup.dt_sample_s)
                f["h1_done"] = True
                self.logger.write("markout_h1", {"mo": mo, "pos": pos})
            if (t_ms - tf) >= h2_ms and not f.get("h2_done"):
                mo = s * (x_now - x_fill)
                pos = max(0.0, mo)
                self._tox_ema_pos_h2 = self._ema(self._tox_ema_pos_h2, pos, self.cfg.warmup.tau_fast_s, self.cfg.warmup.dt_sample_s)
                f["h2_done"] = True
                self.logger.write("markout_h2", {"mo": mo, "pos": pos})
            if not (f.get("h1_done") and f.get("h2_done")):
                keep.append(f)
        self._fills_pending = keep

    def on_time_sample(self, t_ms: int, p_mid: float, trade_rate_per_s: float) -> None:
        dt_s = self.cfg.warmup.dt_sample_s
        x = logit(p_mid)
        if self._last_sample_ts_ms is None:
            self._last_sample_ts_ms = t_ms
            self._last_x = x
            return
        if (t_ms - self._last_sample_ts_ms) < int(dt_s * 1000) - 10:
            return
        r = x - (self._last_x if self._last_x is not None else x)
        self._returns.append(r)
        self._last_sample_ts_ms = t_ms
        self._last_x = x
        abs_r = abs(r)
        self._ema_fast_abs = self._ema(self._ema_fast_abs, abs_r, self.cfg.warmup.tau_fast_s, dt_s)
        self._ema_slow_abs = self._ema(self._ema_slow_abs, abs_r, self.cfg.warmup.tau_slow_s, dt_s)
        self._ema_fast_r = self._ema(self._ema_fast_r, r, self.cfg.warmup.tau_fast_s, dt_s)
        self._ema_fast_abs_r = self._ema(self._ema_fast_abs_r, abs_r, self.cfg.warmup.tau_fast_s, dt_s)
        self._ema_slow_abs_r = self._ema(self._ema_slow_abs_r, abs_r, self.cfg.warmup.tau_slow_s, dt_s)
        I = clip(trade_rate_per_s / max(self.cfg.quote.rate_ref_per_s, 1e-9), 1.0, self.cfg.risk.I_max)
        J = self._ema_fast_abs / max(self._ema_slow_abs, 1e-9)
        D = abs(self._ema_fast_r) / max(self._ema_fast_abs_r, 1e-9)
        S_sigma = max(math.log(max(J, 1.0)), 0.0) * clip(D, 0.0, 1.0) * I
        T = self.cfg.warmup.markout_w1 * self._tox_ema_pos_h1 + self.cfg.warmup.markout_w2 * self._tox_ema_pos_h2
        Z_tox = T / max(self._ema_slow_abs_r, 1e-9)
        S = S_sigma + self.cfg.risk.c_tox * Z_tox
        sigma_raw = 1.0 + self.cfg.risk.c_sigma * (S ** self.cfg.risk.nu_sigma)
        sigma_raw = clip(sigma_raw, 1.0, self.cfg.risk.sigma_max)
        tau = self.cfg.risk.sigma_tau_up_s if sigma_raw > self._sigma_smoothed else self.cfg.risk.sigma_tau_down_s
        self._sigma_smoothed = self._ema(self._sigma_smoothed, sigma_raw, tau, dt_s)
        self.logger.write("sigma_update", {"r": r, "J": J, "D": D, "I": I, "S_sigma": S_sigma, "Z_tox": Z_tox, "sigma_raw": sigma_raw, "sigma": self._sigma_smoothed})

    def sigma(self) -> float:
        return float(self._sigma_smoothed)

    def warm_ready(self) -> bool:
        return len(self._returns) >= self.cfg.warmup.min_return_samples

    def warm_snapshot(self) -> Dict[str, Any]:
        rs = list(self._returns)
        if not rs:
            return {"n_returns": 0}
        med = sorted(rs)[len(rs) // 2]
        abs_dev = [abs(x - med) for x in rs]
        mad = sorted(abs_dev)[len(abs_dev) // 2]
        sigma_base = 1.4826 * mad
        return {"n_returns": len(rs), "dt_sample_s": self.cfg.warmup.dt_sample_s, "sigma_base_logit_per_dt": sigma_base, "ema_fast_abs": self._ema_fast_abs, "ema_slow_abs": self._ema_slow_abs}


class Quoter:
    def __init__(self, cfg: BotConfig, ind: Indicators, md: MarketData, logger: JsonlLogger):
        self.cfg = cfg
        self.ind = ind
        self.md = md
        self.logger = logger
        self.U_proxy_window_s = 6 * 3600

    def estimate_U_proxy(self) -> float:
        t_now = now_ms()
        cutoff = t_now - int(self.U_proxy_window_s * 1000)
        n = 0
        for ts in reversed(self.md.trade_ts):
            if ts < cutoff:
                break
            n += 1
        return math.sqrt(n)

    def compute(self, q_yes: float) -> Dict[str, Any]:
        s = self.md.state
        p = clip(s.mid, 1e-6, 1 - 1e-6)
        t_ms = now_ms()
        qhat = self.ind.q_hat(q_yes, p, t_ms)
        gamma = self.ind.gamma(qhat)
        U = self.estimate_U_proxy()
        lam = self.ind.lambda_struct(p, U)
        sigma = self.ind.sigma()
        delta = qhat * gamma * lam * sigma
        m = logit(p)
        r_x = m - delta
        Delta_risk = self.cfg.quote.c_risk * gamma * lam * sigma
        rate = self.md.trade_rate_per_s(window_s=60.0)
        kappa_scale = 1.0 + (rate / max(self.cfg.quote.rate_ref_per_s, 1e-9))
        kappa = self.cfg.quote.kappa0 * kappa_scale
        Delta_liq = (1.0 / gamma) * math.log(1.0 + gamma / max(kappa, 1e-9))
        base_half_spread = clip(Delta_risk + Delta_liq, 0.0, self.cfg.quote.max_half_spread_logit)
        B_side = self.ind.B_side() * self.ind.time_factor(t_ms)
        ladder = build_v1_ladder(
            r_x=r_x,
            half_b=base_half_spread,
            half_a=base_half_spread,
            tick=s.tick_size,
            B_side=B_side,
            decay=self.cfg.quote.ladder_decay,
            step_mult=self.cfg.quote.ladder_step_mult,
            min_step_logit=self.cfg.quote.ladder_min_step_logit,
            max_levels=self.cfg.quote.ladder_max_levels
        )
        asset_id = self.cfg.market.asset_id_yes
        def clean_orders(raw_orders, side):
            out = []
            total_notional = 0.0
            for o in raw_orders:
                sz = max(self.cfg.quote.min_order_size, o["size"])
                px = o["price"]
                notional_impact = px * sz if side == "BUY" else (1.0 - px) * sz
                if total_notional + notional_impact > self.cfg.quote.max_order_notional_side:
                    break
                total_notional += notional_impact
                out.append({"asset_id": asset_id, "side": side, "price": px, "size": sz})
            return out
        bid_orders = clean_orders(ladder["bids"], "BUY")
        ask_orders = clean_orders(ladder["asks"], "SELL")
        return {
            "metrics": {
                "p_mid": p, "qhat": qhat, "gamma": gamma, 
                "lambda": lam, "sigma": sigma, "delta_logit": delta, 
                "r_logit": r_x, "n_bids": len(bid_orders), "n_asks": len(ask_orders)
            },
            "bids": bid_orders,
            "asks": ask_orders,
        }


class MarketMakerBot:
    def __init__(self, cfg: BotConfig, ex: ExchangeAdapter):
        self.cfg = cfg
        self.ex = ex
        self.logger = JsonlLogger(cfg.log_path)
        self.md = MarketData(self.logger)
        self.ind = Indicators(cfg, self.logger)
        self.quoter = Quoter(cfg, self.ind, self.md, self.logger)
        self._shutdown = asyncio.Event()
        self._last_fills_poll_ms = now_ms() - 60_000

    async def shutdown(self):
        self._shutdown.set()

    async def _ws_loop(self):
        mc = self.cfg.market
        async with websockets.connect(mc.wss_url, ping_interval=20, ping_timeout=20) as ws:
            sub = {"type": "subscribe", "channel": "market", "market": mc.market}
            await ws.send(json.dumps(sub))
            self.logger.write("ws_subscribe", {"payload": sub})
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    self.logger.write("ws_parse_error", {"raw": raw[:2000]})
                    continue
                et = msg.get("event_type") or msg.get("type")
                if et == "book":
                    self.md.on_book(msg)
                elif et == "price_change":
                    self.md.on_price_change(msg)
                elif et == "tick_size_change":
                    self.md.on_tick_size_change(msg)
                elif et == "last_trade_price":
                    self.md.on_last_trade_price(msg)
                else:
                    self.logger.write("ws_unknown", {"msg": msg})
                if self._shutdown.is_set():
                    break

    async def _warmup(self):
        t0 = time.time()
        self.logger.write("warmup_start", {"dt_sample_s": self.cfg.warmup.dt_sample_s, "min_samples": self.cfg.warmup.min_return_samples})
        while not self._shutdown.is_set():
            p = self.md.state.mid
            if not (0.0 < p < 1.0):
                await asyncio.sleep(0.2)
                continue
            tr = self.md.trade_rate_per_s(window_s=60.0)
            self.ind.on_time_sample(now_ms(), p, tr)
            self.ind.update_markouts(now_ms(), p)
            if self.ind.warm_ready():
                break
            if (time.time() - t0) >= self.cfg.warmup.max_warmup_s:
                break
            await asyncio.sleep(0.2)
        snap = self.ind.warm_snapshot()
        os.makedirs(os.path.dirname(self.cfg.calib_path), exist_ok=True)
        with open(self.cfg.calib_path, "w") as fp:
            json.dump(snap, fp, indent=2)
        self.logger.write("warmup_done", snap)

    async def _poll_fills(self):
        while not self._shutdown.is_set():
            try:
                fills = await self.ex.get_fills(self._last_fills_poll_ms)
                for f in fills:
                    self.ind.record_fill(f)
                if fills:
                    self._last_fills_poll_ms = max(self._last_fills_poll_ms, max(int(f["ts_ms"]) for f in fills))
            except Exception as e:
                self.logger.write("fills_poll_error", {"err": str(e)})
            await asyncio.sleep(2.0)

    async def _reconcile(self, desired: Dict[str, Any]):
        try:
            open_orders = await self.ex.list_open_orders()
        except Exception as e:
            self.logger.write("reconcile_error", {"err": f"failed to list orders: {e}"})
            return
        existing_bids: Dict[float, Any] = {}
        existing_asks: Dict[float, Any] = {}
        asset_id = self.cfg.market.asset_id_yes
        for o in open_orders:
            if str(o.get("asset_id")) != asset_id:
                continue
            p = float(o.get("price"))
            sid = o.get("side")
            if sid == "BUY":
                existing_bids[p] = o
            elif sid == "SELL":
                existing_asks[p] = o
        async def reconcile_side(wanted_list: List[Dict[str, Any]], existing_map: Dict[float, Any], side_name: str):
            claimed_prices: Set[float] = set()
            for want in wanted_list:
                wp = want["price"]
                wsize = want["size"]
                found_price = None
                for ep in existing_map:
                    if abs(ep - wp) < 1e-9:
                        found_price = ep
                        break
                if found_price is not None:
                    o = existing_map[found_price]
                    current_size = float(o.get("size_remaining", o.get("size", 0.0)))
                    sz_diff = abs(wsize - current_size) / max(current_size, 1e-9)
                    if sz_diff > 0.25: 
                        try:
                            await self.ex.cancel_order(str(o["order_id"]))
                            self.logger.write("order_cancel_resize", {"oid": o["order_id"], "old": current_size, "new": wsize})
                            oid = await self.ex.place_limit_order(want["asset_id"], want["side"], wp, wsize)
                            self.logger.write("order_place", {"oid": oid, "p": wp, "s": wsize})
                        except Exception as e:
                            self.logger.write("order_error", {"err": str(e), "action": "replace"})
                    claimed_prices.add(found_price)
                else:
                    try:
                        oid = await self.ex.place_limit_order(want["asset_id"], want["side"], wp, wsize)
                        self.logger.write("order_place", {"oid": oid, "p": wp, "s": wsize})
                    except Exception as e:
                        self.logger.write("order_error", {"err": str(e), "action": "new"})
            for ep, o in existing_map.items():
                if ep not in claimed_prices:
                    try:
                        await self.ex.cancel_order(str(o["order_id"]))
                        self.logger.write("order_cancel_prune", {"oid": o["order_id"], "p": ep})
                    except Exception as e:
                        self.logger.write("order_error", {"err": str(e), "action": "prune"})
        await reconcile_side(desired["bids"], existing_bids, "BUY")
        await reconcile_side(desired["asks"], existing_asks, "SELL")

    async def _quote_loop(self):
        while not self._shutdown.is_set():
            try:
                p = self.md.state.mid
                if not (0.0 < p < 1.0):
                    await asyncio.sleep(self.cfg.quote.refresh_s)
                    continue
                bal = await self.ex.get_balances()
                q_yes = float(bal.get("YES", 0.0))
                self.ind.update_markouts(now_ms(), p)
                desired = self.quoter.compute(q_yes)
                if time.time() - self.ind._last_print > 5.0:
                    m = desired["metrics"]
                    print(
                        f"[{dt.datetime.now().isoformat(timespec='seconds')}] "
                        f"p={fmt(m['p_mid'],3)} q={fmt(q_yes,0)} sig={fmt(m['sigma'],2)} "
                        f"r={fmt(m['r_logit'],2)} "
                        f"| Bids: {m['n_bids']} Asks: {m['n_asks']}"
                    )
                    self.ind._last_print = time.time()
                await self._reconcile(desired)
            except Exception as e:
                self.logger.write("quote_loop_error", {"err": str(e)})
            await asyncio.sleep(self.cfg.quote.refresh_s)

    async def run(self):
        ws_task = asyncio.create_task(self._ws_loop())
        await self._warmup()
        fills_task = asyncio.create_task(self._poll_fills())
        quote_task = asyncio.create_task(self._quote_loop())
        await self._shutdown.wait()
        for t in (quote_task, fills_task, ws_task):
            t.cancel()
        self.logger.write("shutdown", {})
        self.logger.close()


def load_config(path: str) -> BotConfig:
    with open(path, "r") as fp:
        d = json.load(fp)
    market = MarketConfig(**d["market"])
    warmup = WarmupConfig(**d.get("warmup", {}))
    risk = RiskConfig(**d.get("risk", {}))
    quote = QuoteConfig(**d.get("quote", {}))
    return BotConfig(
        market=market,
        warmup=warmup,
        risk=risk,
        quote=quote,
        log_path=d.get("log_path", "./data/mm_events.jsonl"),
        calib_path=d.get("calib_path", "./data/warm_calibration.json"),
    )

async def _amain():
    if len(sys.argv) < 2:
        print("Usage: python mm_bot.py config.json")
        sys.exit(1)
    
    cfg = load_config(sys.argv[1])
    
    # Initialize real adapter (Secrets read internally from os.environ)
    ex = PolymarketAdapter(
        asset_yes=cfg.market.asset_id_yes,
        asset_no=cfg.market.asset_id_no
    )

    bot = MarketMakerBot(cfg, ex)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(bot.shutdown()))
        except NotImplementedError:
            pass
    await bot.run()


if __name__ == "__main__":
    asyncio.run(_amain())