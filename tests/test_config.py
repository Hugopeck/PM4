"""
Tests for configuration loading and validation.

Tests cover:
- BotConfig dataclass creation and validation
- Individual config dataclasses (MarketConfig, RiskConfig, etc.)
- Config loading from JSON files
- Default value handling
- Invalid configuration handling
"""
import json
import tempfile
from pathlib import Path

import pytest

from pm4.main import load_config
from pm4.types import (
    BotConfig,
    LoggingConfig,
    MarketConfig,
    QuoteConfig,
    RiskConfig,
    WarmupConfig,
)


class TestMarketConfig:
    """Test MarketConfig dataclass."""

    @pytest.mark.unit
    def test_market_config_creation(self):
        """Test creating a valid MarketConfig."""
        config = MarketConfig(
            market="test-market",
            asset_id_yes="0x1234567890abcdef",
            asset_id_no="0xfedcba0987654321",
            start_ts_ms=1703123456789,
            resolve_ts_ms=1705731456789,
        )

        assert config.market == "test-market"
        assert config.asset_id_yes == "0x1234567890abcdef"
        assert config.asset_id_no == "0xfedcba0987654321"
        assert config.start_ts_ms == 1703123456789
        assert config.resolve_ts_ms == 1705731456789
        assert config.wss_url == "wss://ws-subscriptions-clob.polymarket.com/ws/market"

    @pytest.mark.unit
    def test_market_config_custom_wss_url(self):
        """Test MarketConfig with custom WebSocket URL."""
        config = MarketConfig(
            market="test-market",
            asset_id_yes="0x1234567890abcdef",
            asset_id_no="0xfedcba0987654321",
            start_ts_ms=1703123456789,
            resolve_ts_ms=1705731456789,
            wss_url="wss://custom.polymarket.com/ws/market"
        )

        assert config.wss_url == "wss://custom.polymarket.com/ws/market"


class TestWarmupConfig:
    """Test WarmupConfig dataclass."""

    @pytest.mark.unit
    def test_warmup_config_defaults(self):
        """Test WarmupConfig with default values."""
        config = WarmupConfig()

        assert config.dt_sample_s == 5.0
        assert config.min_return_samples == 360
        assert config.max_warmup_s == 2 * 3600
        assert config.tau_fast_s == 30.0
        assert config.tau_slow_s == 30 * 60.0
        assert config.markout_h1_s == 10.0
        assert config.markout_h2_s == 60.0
        assert config.markout_w1 == 0.6
        assert config.markout_w2 == 0.4

    @pytest.mark.unit
    def test_warmup_config_custom_values(self):
        """Test WarmupConfig with custom values."""
        config = WarmupConfig(
            dt_sample_s=10.0,
            min_return_samples=500,
            max_warmup_s=3600,
        )

        assert config.dt_sample_s == 10.0
        assert config.min_return_samples == 500
        assert config.max_warmup_s == 3600


class TestRiskConfig:
    """Test RiskConfig dataclass."""

    @pytest.mark.unit
    def test_risk_config_defaults(self):
        """Test RiskConfig with default values."""
        config = RiskConfig()

        assert config.bankroll_B == 500.0
        assert config.n_plays == 3
        assert config.eta_time == 0.5
        assert config.slippage_buffer == 0.10
        assert config.gamma_a == 1.0
        assert config.gamma_max == 50.0
        assert config.lambda_min == 0.8
        assert config.lambda_max == 2.0
        assert config.beta_p == 0.7
        assert config.alpha_U == 0.5
        assert config.U_ref == 50.0
        assert config.w_A == 1.0
        assert config.w_L == 1.0
        assert config.s_scale == 1.0
        assert config.I_max == 3.0
        assert config.c_tox == 1.0
        assert config.c_sigma == 1.0
        assert config.nu_sigma == 1.4
        assert config.sigma_max == 6.0
        assert config.sigma_tau_up_s == 10.0
        assert config.sigma_tau_down_s == 90.0

    @pytest.mark.unit
    def test_risk_config_custom_values(self):
        """Test RiskConfig with custom risk parameters."""
        config = RiskConfig(
            bankroll_B=1000.0,
            gamma_max=100.0,
            slippage_buffer=0.05,
        )

        assert config.bankroll_B == 1000.0
        assert config.gamma_max == 100.0
        assert config.slippage_buffer == 0.05


class TestQuoteConfig:
    """Test QuoteConfig dataclass."""

    @pytest.mark.unit
    def test_quote_config_defaults(self):
        """Test QuoteConfig with default values."""
        config = QuoteConfig()

        assert config.c_risk == 0.2
        assert config.kappa0 == 1.0
        assert config.rate_ref_per_s == 0.05
        assert config.min_half_spread_prob == 0.01
        assert config.max_half_spread_logit == 1.5
        assert config.ladder_decay == 0.8
        assert config.ladder_step_mult == 0.5
        assert config.ladder_min_step_logit == 0.05
        assert config.ladder_max_levels == 5
        assert config.min_order_size == 1.0
        assert config.max_order_notional_side == 100.0
        assert config.refresh_s == 2.0
        assert config.price_move_requote_ticks == 1

    @pytest.mark.unit
    def test_quote_config_custom_values(self):
        """Test QuoteConfig with custom quoting parameters."""
        config = QuoteConfig(
            ladder_max_levels=10,
            min_order_size=0.1,
            refresh_s=1.0,
        )

        assert config.ladder_max_levels == 10
        assert config.min_order_size == 0.1
        assert config.refresh_s == 1.0


class TestLoggingConfig:
    """Test LoggingConfig dataclass."""

    @pytest.mark.unit
    def test_logging_config_defaults(self):
        """Test LoggingConfig with default values."""
        config = LoggingConfig()

        assert config.level == "INFO"
        assert config.enable_performance is False
        assert config.enable_context_tracking is False

    @pytest.mark.unit
    def test_logging_config_custom_values(self):
        """Test LoggingConfig with custom logging settings."""
        config = LoggingConfig(
            level="DEBUG",
            enable_performance=True,
            enable_context_tracking=True,
        )

        assert config.level == "DEBUG"
        assert config.enable_performance is True
        assert config.enable_context_tracking is True


class TestBotConfig:
    """Test BotConfig dataclass."""

    @pytest.mark.unit
    def test_bot_config_creation(self, sample_config):
        """Test creating a complete BotConfig."""
        config = sample_config

        assert isinstance(config.market, MarketConfig)
        assert isinstance(config.warmup, WarmupConfig)
        assert isinstance(config.risk, RiskConfig)
        assert isinstance(config.quote, QuoteConfig)
        assert isinstance(config.logging, LoggingConfig)

        assert config.log_path == "./data/mm_events.jsonl"
        assert config.calib_path == "./data/warm_calibration.json"

    @pytest.mark.unit
    def test_bot_config_custom_paths(self):
        """Test BotConfig with custom file paths."""
        market = MarketConfig(
            market="test-market",
            asset_id_yes="0x123",
            asset_id_no="0x456",
            start_ts_ms=1703123456789,
            resolve_ts_ms=1705731456789,
        )

        config = BotConfig(
            market=market,
            warmup=WarmupConfig(),
            risk=RiskConfig(),
            quote=QuoteConfig(),
            logging=LoggingConfig(),
            log_path="/custom/path/events.jsonl",
            calib_path="/custom/path/calibration.json",
        )

        assert config.log_path == "/custom/path/events.jsonl"
        assert config.calib_path == "/custom/path/calibration.json"


class TestConfigLoading:
    """Test configuration loading from JSON files."""

    @pytest.mark.unit
    def test_load_config_success(self, sample_config_file):
        """Test successful config loading from JSON file."""
        config = load_config(str(sample_config_file))

        assert isinstance(config, BotConfig)
        assert config.market.market == "test-market"
        assert config.market.asset_id_yes == "0x1234567890abcdef"
        assert config.market.asset_id_no == "0xfedcba0987654321"
        assert config.market.start_ts_ms == 1703123456789
        assert config.market.resolve_ts_ms == 1705731456789

        # Check defaults are applied
        assert config.warmup.dt_sample_s == 5.0
        assert config.risk.bankroll_B == 500.0
        assert config.quote.c_risk == 0.2
        assert config.logging.level == "INFO"

    @pytest.mark.unit
    def test_load_config_with_custom_values(self, temp_dir):
        """Test loading config with custom values."""
        config_data = {
            "market": {
                "market": "custom-market",
                "asset_id_yes": "0x789",
                "asset_id_no": "0x012",
                "start_ts_ms": 1704000000000,
                "resolve_ts_ms": 1705000000000,
            },
            "warmup": {
                "dt_sample_s": 10.0,
                "min_return_samples": 500,
            },
            "risk": {
                "bankroll_B": 1000.0,
                "gamma_max": 100.0,
            },
            "quote": {
                "ladder_max_levels": 10,
                "refresh_s": 1.0,
            },
            "logging": {
                "level": "DEBUG",
                "enable_performance": True,
            },
            "log_path": "./custom/events.jsonl",
            "calib_path": "./custom/calibration.json",
        }

        config_path = temp_dir / "custom_config.json"
        with open(config_path, 'w') as f:
            json.dump(config_data, f)

        config = load_config(str(config_path))

        assert config.market.market == "custom-market"
        assert config.warmup.dt_sample_s == 10.0
        assert config.warmup.min_return_samples == 500
        assert config.risk.bankroll_B == 1000.0
        assert config.risk.gamma_max == 100.0
        assert config.quote.ladder_max_levels == 10
        assert config.quote.refresh_s == 1.0
        assert config.logging.level == "DEBUG"
        assert config.logging.enable_performance is True

    @pytest.mark.unit
    def test_load_config_missing_required_fields(self, temp_dir):
        """Test loading config with missing required market fields."""
        # Missing required market field
        config_data = {
            "market": {
                "asset_id_yes": "0x123",
                "asset_id_no": "0x456",
                "start_ts_ms": 1703123456789,
                "resolve_ts_ms": 1705731456789,
                # Missing "market" field
            }
        }

        config_path = temp_dir / "incomplete_config.json"
        with open(config_path, 'w') as f:
            json.dump(config_data, f)

        with pytest.raises(KeyError):
            load_config(str(config_path))

    @pytest.mark.unit
    def test_load_config_file_not_found(self):
        """Test loading config from non-existent file."""
        with pytest.raises(FileNotFoundError):
            load_config("/non/existent/config.json")

    @pytest.mark.unit
    def test_load_config_invalid_json(self, temp_dir):
        """Test loading config with invalid JSON."""
        config_path = temp_dir / "invalid_config.json"
        with open(config_path, 'w') as f:
            f.write("invalid json content {")

        with pytest.raises(json.JSONDecodeError):
            load_config(str(config_path))

    @pytest.mark.unit
    def test_load_config_empty_sections(self, temp_dir):
        """Test loading config with empty optional sections."""
        config_data = {
            "market": {
                "market": "test-market",
                "asset_id_yes": "0x123",
                "asset_id_no": "0x456",
                "start_ts_ms": 1703123456789,
                "resolve_ts_ms": 1705731456789,
            },
            # Empty sections should use defaults
            "warmup": {},
            "risk": {},
            "quote": {},
            "logging": {},
        }

        config_path = temp_dir / "minimal_config.json"
        with open(config_path, 'w') as f:
            json.dump(config_data, f)

        config = load_config(str(config_path))

        assert isinstance(config, BotConfig)
        # Should have default values
        assert config.warmup.dt_sample_s == 5.0
        assert config.risk.bankroll_B == 500.0
        assert config.quote.c_risk == 0.2
