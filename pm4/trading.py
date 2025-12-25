"""
Core trading logic for PM4 market maker.
"""
import asyncio
import datetime as dt
import json
import math
import os
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Set

from .adapters import ExchangeAdapter
from .logging import DebugLogger, ErrorContext, JsonlLogger, performance_trace
from .market_data import MarketData
from .types import BotConfig
from .utils import clip, fmt, logit, now_ms, sigmoid


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
    """Build a ladder of orders for market making.

    Constructs a series of limit orders on both sides of the market with
    geometrically decaying sizes. Orders are placed at optimal locations
    in logit space and converted back to probability space.

    Args:
        r_x: Reference price in logit space (optimal quote location)
        half_b: Half-spread below reference (bid side) in logit space
        half_a: Half-spread above reference (ask side) in logit space
        tick: Minimum price tick size for rounding
        B_side: Available capital per side for position sizing
        decay: Size decay factor between levels (0.7 = 30% smaller each level)
        step_mult: Step size multiplier for level spacing
        min_step_logit: Minimum step size in logit space
        max_levels: Maximum number of orders per side

    Returns:
        Dictionary with 'bids' and 'asks' containing order ladders:
        Each order has 'level', 'price', and 'size' fields

    Note:
        Uses Kelly criterion sizing with geometric decay for inventory management.
        Prices are tick-rounded and deduplicated to prevent overlapping orders.
    """
    # Calculate ladder boundaries in logit space
    x_b0 = r_x - half_b  # Start of bid ladder
    x_a0 = r_x + half_a  # Start of ask ladder

    # Determine step size for ladder levels
    base_step = max(step_mult * (half_b + half_a) / 2.0, min_step_logit)

    # Define valid price range boundaries in logit space
    x_min = logit(max(tick, 0.001))  # Minimum valid logit price
    x_max = logit(min(1.0 - tick, 0.999))  # Maximum valid logit price

    bids = []
    asks = []

    # Calculate number of levels for each side
    if base_step > 1e-9:
        N_bid = min(max_levels, int(max(0, (x_b0 - x_min) / base_step)))
        N_ask = min(max_levels, int(max(0, (x_max - x_a0) / base_step)))
    else:
        N_bid, N_ask = 0, 0

    # Base risk allocation per level (10% of available capital)
    base_risk_unit = B_side * 0.10

    # Generate bid orders (below reference price)
    for i in range(N_bid):
        # Calculate logit price for this level
        x = x_b0 - i * base_step
        # Convert back to probability space
        p = sigmoid(x)
        # Round down to tick size for valid price
        p = math.floor(p / tick) * tick

        # Stop if price becomes invalid (too close to 0)
        if p <= 0.001:
            break

        # Calculate size using Kelly criterion: risk / probability
        level_risk = base_risk_unit * (decay ** i)  # Geometrically decaying risk
        size = level_risk / max(p, 1e-3)  # Size = risk / win_probability
        bids.append({"level": i, "price": p, "size": size})

    # Generate ask orders (above reference price)
    for i in range(N_ask):
        # Calculate logit price for this level
        x = x_a0 + i * base_step
        # Convert back to probability space
        p = sigmoid(x)
        # Round up to tick size for valid price
        p = math.ceil(p / tick) * tick

        # Stop if price becomes invalid (too close to 1)
        if p >= 0.999:
            break

        # Calculate size using Kelly criterion: risk / (1 - probability)
        level_risk = base_risk_unit * (decay ** i)  # Geometrically decaying risk
        size = level_risk / max(1.0 - p, 1e-3)  # Size = risk / loss_probability
        asks.append({"level": i, "price": p, "size": size})

    def dedupe(levels, side):
        """Remove duplicate prices, keeping the best level for each price."""
        seen = {}
        for l in levels:
            px = l["price"]
            if px not in seen:
                seen[px] = l
            else:
                # Keep the level closest to reference price (smallest level number)
                if l["level"] < seen[px]["level"]:
                    seen[px] = l
        # Sort by price (descending for bids, ascending for asks)
        return sorted(seen.values(), key=lambda x: x["price"], reverse=(side == "bid"))

    return {
        "bids": dedupe(bids, "bid"),
        "asks": dedupe(asks, "ask"),
    }


class Indicators:
    """Risk management and market volatility indicators for market making.

    This class implements sophisticated risk management algorithms including:
    - Kelly criterion-based position sizing (q_max, q_hat)
    - Dynamic spread scaling (gamma function)
    - Market regime detection (lambda_struct)
    - Volatility estimation with exponential moving averages
    - Markout analysis for performance attribution

    The indicators adapt position sizes and spreads based on:
    - Market volatility (sigma estimation)
    - Time to market resolution (time_factor)
    - Probability weighting (A_p function)
    - Liquidity conditions (L_U function)
    """

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
        """Exponential moving average calculation.

        Implements the standard EMA formula: EMA_new = prev * (1-α) + x * α
        where α = 1 - exp(-dt/τ) provides the smoothing factor.

        Args:
            prev: Previous EMA value
            x: New observation to incorporate
            tau_s: Time constant in seconds (higher = smoother)
            dt_s: Time step between observations

        Returns:
            Updated exponential moving average value
        """
        if tau_s <= 0:
            return x
        # Calculate smoothing factor α = 1 - exp(-dt/τ)
        # This ensures stability and proper time-based smoothing
        a = 1.0 - math.exp(-dt_s / tau_s)
        return prev + a * (x - prev)

    def time_factor(self, t_ms: int) -> float:
        """Calculate time-based risk adjustment factor.

        Reduces position sizes as market resolution approaches, implementing
        a time-decay risk management strategy. Uses exponential decay where
        eta_time controls the decay rate.

        Args:
            t_ms: Current timestamp in milliseconds

        Returns:
            Risk adjustment factor in [0, 1] where:
            - 1.0 = maximum risk (far from resolution)
            - < 1.0 = reduced risk (close to resolution)
        """
        mc = self.cfg.market
        # Total market duration in seconds
        T = max(mc.resolve_ts_ms - mc.start_ts_ms, 1) / 1000.0
        # Time remaining until resolution in seconds
        tau = max(mc.resolve_ts_ms - t_ms, 0) / 1000.0

        # Exponential decay: (τ/T)^η where η = eta_time
        # Higher eta_time = more aggressive risk reduction near resolution
        return (tau / T) ** self.cfg.risk.eta_time if T > 0 else 1.0

    def B_side(self) -> float:
        """Calculate one-sided bankroll allocation.

        Allocates bankroll across multiple concurrent trading opportunities.
        For n_plays concurrent markets, each gets an equal share of total bankroll.

        Returns:
            One-sided bankroll allocation (half of total per market)
        """
        # Equal allocation across n_plays concurrent markets
        w = 1.0 / max(self.cfg.risk.n_plays, 1)
        # Allocate half bankroll to each side (buy/sell)
        return 0.5 * self.cfg.risk.bankroll_B * w

    def q_max(self, p: float, q: float, t_ms: int) -> float:
        """Calculate maximum position size using Kelly criterion.

        Implements Kelly criterion for optimal position sizing in prediction markets.
        The formula maximizes long-term growth by balancing expected return vs risk.

        Args:
            p: Current market probability [0, 1]
            q: Desired position size (positive = buy YES, negative = buy NO)
            t_ms: Current timestamp for time-based risk adjustment

        Returns:
            Maximum allowable position size for optimal risk-adjusted growth

        Note:
            Formula: q_max = (B_side * time_factor) / (p_opp * (1 + slippage_buffer))
            where p_opp is the probability of the opposite outcome.
        """
        # Determine which side we're trading (probability of opposite outcome)
        p_opp = (1.0 - p) if q >= 0 else p

        # Add slippage buffer to account for execution costs and adverse selection
        denom = max(p_opp * (1.0 + self.cfg.risk.slippage_buffer), 1e-9)

        # Kelly position size with time and bankroll adjustments
        return (self.B_side() * self.time_factor(t_ms)) / denom

    def q_hat(self, q: float, p: float, t_ms: int) -> float:
        """Calculate normalized position size [-1, 1].

        Normalizes desired position size against Kelly-optimal maximum,
        producing a value in [-1, 1] suitable for spread scaling calculations.

        Args:
            q: Raw desired position size
            p: Current market probability [0, 1]
            t_ms: Current timestamp

        Returns:
            Normalized position size in [-1, 1]:
            - 1.0 = maximum long position (full Kelly)
            - 0.0 = neutral/no position
            - -1.0 = maximum short position (full Kelly)
        """
        qm = self.q_max(p, q, t_ms)
        # Normalize to [-1, 1] range, handling edge cases
        return clip(q / qm, -1.0, 1.0) if qm > 0 else 0.0

    def gamma(self, qhat: float) -> float:
        """Calculate dynamic spread scaling factor.

        Implements power-law scaling of bid-ask spreads based on position size.
        Larger positions require wider spreads to manage inventory risk.

        Args:
            qhat: Normalized position size in [-1, 1]

        Returns:
            Spread scaling factor >= 1.0:
            - 1.0 = minimum spread (neutral position)
            - > 1.0 = wider spread (larger position)

        Note:
            Formula: γ = 1 / (1 - |q̂|)^γₐ
            where γₐ controls the aggressiveness of spread scaling.
        """
        # Ensure |qhat| is in [0, 1) to avoid division by zero
        u = clip(abs(qhat), 0.0, 0.999999)

        # Power-law spread scaling: higher positions = wider spreads
        g = 1.0 / ((1.0 - u) ** self.cfg.risk.gamma_a)

        # Cap maximum spread scaling for stability
        return clip(g, 1.0, self.cfg.risk.gamma_max)

    def A_p(self, p: float) -> float:
        """Calculate probability weighting adjustment factor.

        Adjusts strategy based on market probability distribution. Uses the
        variance of a Bernoulli random variable (p*(1-p)) as a measure of
        market uncertainty, normalized by maximum variance (0.25 at p=0.5).

        Args:
            p: Market probability in [0, 1]

        Returns:
            Probability weighting factor where:
            - > 1.0 for probabilities away from 0.5 (more certain markets)
            - = 1.0 at p = 0.5 (maximum uncertainty)
            - < 1.0 for extreme probabilities (less certain)

        Note:
            Formula: A(p) = [(p*(1-p))/0.25]^β_p
            Higher β_p increases sensitivity to probability extremes.
        """
        p = clip(p, 1e-6, 1 - 1e-6)
        # Variance normalized by maximum variance (0.25 at p=0.5)
        uncertainty = (p * (1.0 - p)) / 0.25
        return uncertainty ** self.cfg.risk.beta_p

    def L_U(self, U: float) -> float:
        """Calculate liquidity adjustment factor.

        Adjusts strategy based on market activity/liquidity proxy.
        Higher activity suggests better liquidity, allowing more aggressive trading.

        Args:
            U: Liquidity proxy (typically market activity measure)

        Returns:
            Liquidity adjustment factor where:
            - > 1.0 for high liquidity (more aggressive trading)
            - = 1.0 for reference liquidity level
            - < 1.0 for low liquidity (more conservative trading)

        Note:
            Formula: L(U) = (U_ref / (U + U_ref))^α_U
            α_U controls sensitivity to liquidity changes.
        """
        Uref = max(self.cfg.risk.U_ref, 1e-9)
        # Sigmoid-like response to liquidity changes
        return (Uref / (U + Uref)) ** self.cfg.risk.alpha_U

    def lambda_struct(self, p: float, U: float) -> float:
        """Calculate market regime adjustment factor.

        Combines probability weighting and liquidity adjustments to determine
        overall market regime factor. This allows the strategy to adapt to
        different market conditions (high/low liquidity, certain/uncertain probs).

        Args:
            p: Market probability [0, 1]
            U: Liquidity proxy value

        Returns:
            Market regime adjustment factor in [λ_min, λ_max] where:
            - > 1.0 = more aggressive trading (favorable conditions)
            - = 1.0 = baseline trading
            - < 1.0 = more conservative trading (adverse conditions)

        Note:
            Combines A(p) and L(U) with configurable weights w_A and w_L.
            Output is linearly scaled to stay within configured bounds.
        """
        # Calculate individual adjustment factors
        A = self.A_p(p)
        L = self.L_U(U)

        # Weighted combination of probability and liquidity factors
        s = self.cfg.risk.w_A * (A - 1.0) + self.cfg.risk.w_L * (L - 1.0)

        # Normalize to [-1, 1] range for linear scaling
        g = clip(s / max(self.cfg.risk.s_scale, 1e-9), -1.0, 1.0)

        # Linear interpolation between min and max bounds
        lam_min, lam_max = self.cfg.risk.lambda_min, self.cfg.risk.lambda_max
        if g > 0:
            lam = 1.0 + (lam_max - 1.0) * g
        else:
            lam = 1.0 + (1.0 - lam_min) * g

        return clip(lam, lam_min, lam_max)

    def record_fill(self, fill: Dict[str, Any]) -> None:
        """Record a trade execution for markout analysis.

        Stores fill information for later P&L attribution analysis.
        Fills are processed in time windows to measure profitability.

        Args:
            fill: Fill event data containing price, size, timestamp, etc.
        """
        self._fills_pending.append(fill)
        self.logger.write("fill", fill)

    def update_markouts(self, t_ms: int, p_mid: float) -> None:
        """Update markout analysis for performance attribution.

        Measures P&L evolution over time after trade execution to assess
        strategy effectiveness and market impact. Uses two time horizons
        to capture different aspects of trade performance.

        Args:
            t_ms: Current timestamp for markout calculation
            p_mid: Current market midpoint probability

        Note:
            Markout analysis helps identify:
            - Market impact costs (immediate P&L movement)
            - Holding period returns (longer-term performance)
            - Adverse selection vs execution quality
        """
        # Convert current market probability to logit space for analysis
        x_now = logit(p_mid)

        # Define markout horizons in milliseconds
        h1_ms = int(self.cfg.warmup.markout_h1_s * 1000)  # Short-term horizon
        h2_ms = int(self.cfg.warmup.markout_h2_s * 1000)  # Long-term horizon

        # Process pending fills that have reached analysis horizons
        keep: Deque[Dict[str, Any]] = deque(maxlen=self._fills_pending.maxlen)

        for f in list(self._fills_pending):
            tf = int(f["ts_ms"])

            # Convert fill price to logit space on first analysis
            if "x_fill" not in f:
                f["x_fill"] = logit(float(f["price"]))

            # Determine position direction (+1 for BUY, -1 for SELL)
            s = 1.0 if f.get("side") == "BUY" else -1.0
            x_fill = float(f["x_fill"])

            # Short-term markout analysis (h1 horizon)
            if (t_ms - tf) >= h1_ms and not f.get("h1_done"):
                # Calculate markout: direction * (current_logit - fill_logit)
                # Positive markout = profitable, negative = loss
                mo = s * (x_now - x_fill)
                # Only consider positive outcomes for toxicity measure
                pos = max(0.0, mo)

                # Update exponential moving average of positive markouts
                self._tox_ema_pos_h1 = self._ema(
                    self._tox_ema_pos_h1, pos,
                    self.cfg.warmup.tau_fast_s,
                    self.cfg.warmup.dt_sample_s
                )
                f["h1_done"] = True
                self.logger.write("markout_h1", {"mo": mo, "pos": pos})

            # Long-term markout analysis (h2 horizon)
            if (t_ms - tf) >= h2_ms and not f.get("h2_done"):
                mo = s * (x_now - x_fill)
                pos = max(0.0, mo)

                self._tox_ema_pos_h2 = self._ema(
                    self._tox_ema_pos_h2, pos,
                    self.cfg.warmup.tau_fast_s,
                    self.cfg.warmup.dt_sample_s
                )
                f["h2_done"] = True
                self.logger.write("markout_h2", {"mo": mo, "pos": pos})

            # Keep fills that haven't completed both analyses
            if not (f.get("h1_done") and f.get("h2_done")):
                keep.append(f)

        self._fills_pending = keep

    def on_time_sample(self, t_ms: int, p_mid: float, trade_rate_per_s: float) -> None:
        """Update volatility estimates and market condition indicators.

        Implements sophisticated volatility estimation using multiple EMAs
        to capture different aspects of market dynamics. Combines price movement
        analysis with trading activity and adverse selection measures.

        The algorithm estimates:
        - Short-term vs long-term volatility (J ratio)
        - Directional bias (D statistic)
        - Trading intensity (I factor)
        - Adverse selection costs (toxicity measure)

        Args:
            t_ms: Current timestamp
            p_mid: Current market midpoint probability
            trade_rate_per_s: Recent trading activity rate

        Note:
            This is the core volatility estimation engine that drives
            dynamic risk management and spread scaling decisions.
        """
        dt_s = self.cfg.warmup.dt_sample_s

        # Convert market probability to logit space for analysis
        x = logit(p_mid)

        # Initialize or validate sampling timing
        if self._last_sample_ts_ms is None:
            self._last_sample_ts_ms = t_ms
            self._last_x = x
            return

        # Ensure minimum time between samples to prevent noise
        if (t_ms - self._last_sample_ts_ms) < int(dt_s * 1000) - 10:
            return

        # Calculate log-return (price change in logit space)
        r = x - (self._last_x if self._last_x is not None else x)
        self._returns.append(r)
        self._last_sample_ts_ms = t_ms
        self._last_x = x
        abs_r = abs(r)

        # Multi-timeframe volatility estimation using EMAs
        # Fast EMAs capture short-term dynamics, slow EMAs provide baseline
        self._ema_fast_abs = self._ema(self._ema_fast_abs, abs_r, self.cfg.warmup.tau_fast_s, dt_s)
        self._ema_slow_abs = self._ema(self._ema_slow_abs, abs_r, self.cfg.warmup.tau_slow_s, dt_s)

        # Directional momentum indicators
        self._ema_fast_r = self._ema(self._ema_fast_r, r, self.cfg.warmup.tau_fast_s, dt_s)
        self._ema_fast_abs_r = self._ema(self._ema_fast_abs_r, abs_r, self.cfg.warmup.tau_fast_s, dt_s)
        self._ema_slow_abs_r = self._ema(self._ema_slow_abs_r, abs_r, self.cfg.warmup.tau_slow_s, dt_s)

        # Trading intensity factor (normalized trading activity)
        I = clip(trade_rate_per_s / max(self.cfg.quote.rate_ref_per_s, 1e-9), 1.0, self.cfg.risk.I_max)

        # Volatility ratio: fast/slow EMA of absolute returns
        # J > 1 indicates increasing volatility, J < 1 indicates decreasing
        J = self._ema_fast_abs / max(self._ema_slow_abs, 1e-9)

        # Directional bias: |momentum| / volatility
        # D close to 1 indicates strong directional movement
        D = abs(self._ema_fast_r) / max(self._ema_fast_abs_r, 1e-9)

        # Combined volatility-stress indicator
        S_sigma = max(math.log(max(J, 1.0)), 0.0) * clip(D, 0.0, 1.0) * I

        # Toxicity measure: weighted combination of markout horizons
        # Measures adverse selection costs from trade execution
        T = (self.cfg.warmup.markout_w1 * self._tox_ema_pos_h1 +
             self.cfg.warmup.markout_w2 * self._tox_ema_pos_h2)

        # Normalized toxicity relative to baseline volatility
        Z_tox = T / max(self._ema_slow_abs_r, 1e-9)

        # Total stress indicator combining volatility and toxicity
        S = S_sigma + self.cfg.risk.c_tox * Z_tox

        # Final volatility estimate with configurable scaling
        sigma_raw = 1.0 + self.cfg.risk.c_sigma * (S ** self.cfg.risk.nu_sigma)
        sigma_raw = clip(sigma_raw, 1.0, self.cfg.risk.sigma_max)

        # Adaptive smoothing: faster response to volatility increases
        tau = (self.cfg.risk.sigma_tau_up_s if sigma_raw > self._sigma_smoothed
               else self.cfg.risk.sigma_tau_down_s)

        self._sigma_smoothed = self._ema(self._sigma_smoothed, sigma_raw, tau, dt_s)

        self.logger.write("sigma_update", {
            "r": r, "J": J, "D": D, "I": I,
            "S_sigma": S_sigma, "Z_tox": Z_tox,
            "sigma_raw": sigma_raw, "sigma": self._sigma_smoothed
        })

    @performance_trace()
    def sigma(self) -> float:
        """Get current volatility estimate.

        Returns the smoothed volatility estimate used for risk management
        and spread scaling decisions.

        Returns:
            Current volatility multiplier (>= 1.0):
            - 1.0 = baseline volatility
            - > 1.0 = higher volatility requiring wider spreads/conservative sizing
        """
        return float(self._sigma_smoothed)

    def warm_ready(self) -> bool:
        """Check if warmup period is complete.

        Determines if sufficient market data has been collected for
        reliable volatility estimation and strategy initialization.

        Returns:
            True if warmup requirements are met, False otherwise
        """
        return len(self._returns) >= self.cfg.warmup.min_return_samples

    def warm_snapshot(self) -> Dict[str, Any]:
        """Generate warmup calibration snapshot.

        Creates a statistical summary of the warmup period for persistence
        and analysis. Uses robust statistics (median/MAD) to handle outliers.

        Returns:
            Dictionary containing:
            - n_returns: Number of samples collected
            - sigma_base_logit_per_dt: Baseline volatility estimate
            - ema_fast_abs, ema_slow_abs: Volatility EMA values
        """
        rs = list(self._returns)
        if not rs:
            return {"n_returns": 0}

        # Use median and MAD (Median Absolute Deviation) for robust statistics
        # More resistant to outliers than mean/std approaches
        med = sorted(rs)[len(rs) // 2]  # Median return
        abs_dev = [abs(x - med) for x in rs]
        mad = sorted(abs_dev)[len(abs_dev) // 2]  # MAD

        # Convert MAD to standard deviation estimate (robust scale factor)
        sigma_base = 1.4826 * mad

        return {
            "n_returns": len(rs),
            "dt_sample_s": self.cfg.warmup.dt_sample_s,
            "sigma_base_logit_per_dt": sigma_base,
            "ema_fast_abs": self._ema_fast_abs,
            "ema_slow_abs": self._ema_slow_abs
        }


class Quoter:
    """Order quote generation and risk-adjusted pricing engine.

    This class implements the core quoting algorithm that combines:
    - Risk management from Indicators class
    - Market data from real-time feeds
    - Kelly criterion position sizing
    - Dynamic spread scaling based on volatility
    - Order ladder construction for market making

    The quoting process involves:
    1. Estimating market activity (liquidity proxy)
    2. Calculating optimal position sizes
    3. Determining appropriate bid-ask spreads
    4. Constructing order ladders for execution
    """

    def __init__(self, cfg: BotConfig, ind: Indicators, md: MarketData, logger: JsonlLogger):
        """Initialize quoter with required dependencies.

        Args:
            cfg: Complete bot configuration
            ind: Risk management and volatility indicators
            md: Real-time market data processor
            logger: Event logging system
        """
        self.cfg = cfg
        self.ind = ind
        self.md = md
        self.logger = logger
        # 6-hour window for liquidity proxy estimation
        self.U_proxy_window_s = 6 * 3600

    def estimate_U_proxy(self) -> float:
        """Estimate market liquidity proxy from recent trading activity.

        Uses trade count within a time window as a proxy for market liquidity.
        Higher trade frequency suggests better liquidity conditions.

        Returns:
            Liquidity proxy value (square root of trade count):
            - Higher values indicate more liquid markets
            - Used by Indicators.lambda_struct() for regime adjustment
        """
        t_now = now_ms()
        cutoff = t_now - int(self.U_proxy_window_s * 1000)

        # Count trades within the analysis window
        n = 0
        for ts in reversed(self.md.trade_ts):
            if ts < cutoff:
                break
            n += 1

        # Square root provides smoother scaling and prevents extreme values
        return math.sqrt(n)

    @performance_trace()
    def compute(self, q_yes: float) -> Dict[str, Any]:
        """Compute optimal quotes for market making.

        This is the core quoting algorithm that combines multiple risk factors
        to generate optimal bid/ask prices and sizes. The algorithm:

        1. Assesses current market conditions and position
        2. Calculates risk-adjusted position sizing (Kelly criterion)
        3. Determines appropriate spread width (volatility + liquidity)
        4. Constructs order ladders for execution

        Args:
            q_yes: Current YES token position (positive = long YES)

        Returns:
            Dictionary containing:
            - metrics: Calculation details for analysis
            - bids: List of buy orders with prices and sizes
            - asks: List of sell orders with prices and sizes

        Note:
            This implements the complete market making decision pipeline,
            from risk assessment to executable order generation.
        """
        s = self.md.state

        # Ensure market probability is in valid range for calculations
        p = clip(s.mid, 1e-6, 1 - 1e-6)
        t_ms = now_ms()

        # === RISK MANAGEMENT CALCULATIONS ===

        # Normalize position size to Kelly-optimal scale [-1, 1]
        qhat = self.ind.q_hat(q_yes, p, t_ms)

        # Calculate spread scaling factor based on position size
        gamma = self.ind.gamma(qhat)

        # Estimate market liquidity from recent trading activity
        U = self.estimate_U_proxy()

        # Market regime adjustment (probability + liquidity factors)
        lam = self.ind.lambda_struct(p, U)

        # Current volatility estimate for risk adjustment
        sigma = self.ind.sigma()

        # === PRICING MODEL ===

        # Total risk adjustment in logit space
        # Combines position size, spread scaling, regime, and volatility
        delta = qhat * gamma * lam * sigma

        # Reference price in logit space
        m = logit(p)

        # Optimal quote location: reference price adjusted for risk
        r_x = m - delta

        # === SPREAD CALCULATION ===

        # Risk-based spread component (accounts for position and volatility)
        Delta_risk = self.cfg.quote.c_risk * gamma * lam * sigma

        # Liquidity-based spread component (market impact consideration)
        rate = self.md.trade_rate_per_s(window_s=60.0)
        kappa_scale = 1.0 + (rate / max(self.cfg.quote.rate_ref_per_s, 1e-9))
        kappa = self.cfg.quote.kappa0 * kappa_scale

        # Liquidity-adjusted spread using market impact model
        Delta_liq = (1.0 / gamma) * math.log(1.0 + gamma / max(kappa, 1e-9))

        # Total half-spread in logit space
        base_half_spread = clip(Delta_risk + Delta_liq, 0.0, self.cfg.quote.max_half_spread_logit)

        # === ORDER LADDER CONSTRUCTION ===

        # Available capital per side with time decay adjustment
        B_side = self.ind.B_side() * self.ind.time_factor(t_ms)

        # Generate order ladder with risk-adjusted pricing
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

        # === ORDER SIZE MANAGEMENT ===

        asset_id = self.cfg.market.asset_id_yes

        def clean_orders(raw_orders, side):
            """Filter and size orders according to risk limits."""
            out = []
            total_notional = 0.0

            for o in raw_orders:
                # Ensure minimum order size
                sz = max(self.cfg.quote.min_order_size, o["size"])
                px = o["price"]

                # Calculate notional impact (risk exposure)
                # BUY: cost is price, SELL: opportunity cost is (1-price)
                notional_impact = px * sz if side == "BUY" else (1.0 - px) * sz

                # Enforce per-side notional limits
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
    """Main market making bot orchestration and control system.

    This class coordinates all aspects of automated market making:
    - Real-time market data processing via WebSocket
    - Risk management and volatility estimation
    - Quote generation and order ladder construction
    - Order execution and inventory management
    - Performance monitoring and position tracking

    The bot operates in a continuous loop:
    1. Warmup: Calibrate models on market data
    2. Quote: Generate and maintain order book
    3. Monitor: Track fills and update positions
    4. Reconcile: Synchronize desired vs actual orders

    Key features:
    - Asynchronous operation with proper shutdown handling
    - Configurable logging and performance monitoring
    - Graceful error handling and recovery
    - Position-aware risk management
    """

    def __init__(self, cfg: BotConfig, ex: ExchangeAdapter):
        self.cfg = cfg
        self.ex = ex

        # Conditionally create enhanced logger based on configuration
        if cfg.logging.level != "INFO" or cfg.logging.enable_performance:
            self.logger = DebugLogger(cfg.log_path, level=cfg.logging.level)
        else:
            self.logger = JsonlLogger(cfg.log_path)  # Backward compatibility

        self.md = MarketData(self.logger)
        self.ind = Indicators(cfg, self.logger)
        self.quoter = Quoter(cfg, self.ind, self.md, self.logger)
        self._shutdown = asyncio.Event()
        self._last_fills_poll_ms = now_ms() - 60_000

    async def shutdown(self):
        self._shutdown.set()

    async def _ws_loop(self):
        import websockets
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
        """Perform market calibration and model warm-up phase.

        Collects market data to calibrate volatility models and risk parameters
        before enabling live trading. This ensures stable operation by:

        1. Gathering sufficient price return samples for volatility estimation
        2. Calibrating exponential moving averages
        3. Establishing baseline market conditions
        4. Saving calibration data for persistence

        The warmup continues until either:
        - Sufficient samples collected (min_return_samples)
        - Maximum warmup time exceeded
        - Manual shutdown requested

        Note:
            Critical for stable operation - prevents erratic behavior from
            insufficient calibration data.
        """
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
                ErrorContext.log_operation_error(
                    self.logger, "poll_fills", e,
                    {"last_poll_ms": self._last_fills_poll_ms}
                )
                self.logger.write("fills_poll_error", {"err": str(e)})  # Keep for backward compatibility
            await asyncio.sleep(2.0)

    async def _reconcile(self, desired: Dict[str, Any]):
        """Reconcile desired orders with current order book state.

        Synchronizes the desired order ladder with actual exchange orders by:
        1. Fetching current open orders from exchange
        2. Comparing with desired order ladder
        3. Placing new orders where needed
        4. Canceling obsolete orders
        5. Resizing orders that differ in quantity

        Handles complex scenarios:
        - Order placement failures (continues with others)
        - Cancellation failures (logs but continues)
        - Size discrepancies (replaces with correct size)
        - Price overlaps (deduplicates intelligently)

        Args:
            desired: Dictionary with 'bids' and 'asks' containing
                    desired order specifications

        Note:
            Critical for maintaining correct market presence.
            Implements robust error handling to prevent order book drift.
        """
        try:
            open_orders = await self.ex.list_open_orders()
        except Exception as e:
            ErrorContext.log_operation_error(
                self.logger, "list_open_orders", e,
                {"asset_id": self.cfg.market.asset_id_yes}
            )
            self.logger.write("reconcile_error", {"err": f"failed to list orders: {e}"})  # Keep for backward compatibility
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
                            ErrorContext.log_operation_error(
                                self.logger, "place_limit_order_resize", e,
                                {"asset_id": want["asset_id"], "side": want["side"], "price": wp, "size": wsize}
                            )
                            self.logger.write("order_error", {"err": str(e), "action": "replace"})  # Keep for backward compatibility
                    claimed_prices.add(found_price)
                else:
                    try:
                        oid = await self.ex.place_limit_order(want["asset_id"], want["side"], wp, wsize)
                        self.logger.write("order_place", {"oid": oid, "p": wp, "s": wsize})
                    except Exception as e:
                        ErrorContext.log_operation_error(
                            self.logger, "place_limit_order_new", e,
                            {"asset_id": want["asset_id"], "side": want["side"], "price": wp, "size": wsize}
                        )
                        self.logger.write("order_error", {"err": str(e), "action": "new"})  # Keep for backward compatibility
            for ep, o in existing_map.items():
                if ep not in claimed_prices:
                    try:
                        await self.ex.cancel_order(str(o["order_id"]))
                        self.logger.write("order_cancel_prune", {"oid": o["order_id"], "p": ep})
                    except Exception as e:
                        ErrorContext.log_operation_error(
                            self.logger, "cancel_order_prune", e,
                            {"order_id": str(o["order_id"]), "price": ep}
                        )
                        self.logger.write("order_error", {"err": str(e), "action": "prune"})  # Keep for backward compatibility
        await reconcile_side(desired["bids"], existing_bids, "BUY")
        await reconcile_side(desired["asks"], existing_asks, "SELL")

    async def _quote_loop(self):
        """Main quoting and trading loop.

        Continuously maintains optimal market making quotes by:
        1. Monitoring market conditions and position
        2. Computing optimal quotes using risk-adjusted algorithms
        3. Reconciling desired orders with current order book
        4. Tracking performance and position changes

        The loop runs at configurable intervals (refresh_s) and handles:
        - Invalid market conditions (skips until valid)
        - Balance updates and position tracking
        - Markout analysis for performance attribution
        - Periodic status logging for monitoring

        This is the core operational loop that implements the complete
        market making strategy in real-time.
        """
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
                ErrorContext.capture_error(self.logger, e, {
                    "operation": "quote_loop",
                    "mid_price": self.md.state.mid if hasattr(self.md, 'state') else None
                })
                self.logger.write("quote_loop_error", {"err": str(e)})  # Keep for backward compatibility
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
