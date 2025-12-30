"""
Configuration types and dataclasses for PM4.
"""
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class WarmupConfig:
    """Configuration for market warmup and calibration phase."""
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
    """Risk management configuration parameters."""
    bankroll_B: float = 50.0
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
    """Quote generation and ladder configuration."""
    c_risk: float = 0.2
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
    """Market and asset configuration."""
    market: str
    asset_id_yes: str
    asset_id_no: str
    start_ts_ms: int
    resolve_ts_ms: int
    wss_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


@dataclass
class LoggingConfig:
    """Logging configuration for debugging and monitoring."""
    level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    enable_performance: bool = False
    enable_context_tracking: bool = False


@dataclass
class MetaWarmupParams:
    """Meta-calibrated warmup parameters based on market activity."""
    dt_sample_s: float
    tau_fast_s: float
    tau_slow_s: float
    markout_h1_s: float
    markout_h2_s: float
    calibrated_at_ms: int
    market_activity_summary: Dict[str, float] = field(default_factory=dict)


@dataclass
class BotConfig:
    """Complete bot configuration."""
    market: MarketConfig
    warmup: WarmupConfig
    risk: RiskConfig
    quote: QuoteConfig
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    log_path: str = "./data/logs/mm_events.jsonl"
    calib_path: str = "./data/calibration/warm_calibration.json"
