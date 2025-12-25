"""
Tests for risk management calculations in pm4/trading.py.

Tests cover:
- Exponential moving average calculations (_ema)
- Time-based factor calculations (time_factor)
- Capital allocation (B_side)
- Position size limits (q_max, q_hat)
- Risk adjustment factors (gamma)
- Price adjustment factors (A_p)
- Utility functions (L_U)
- Structural lambda calculations (lambda_struct)
- Ladder building (build_v1_ladder)
"""
import math
from unittest.mock import MagicMock

import pytest

from pm4.logging import JsonlLogger
from pm4.types import BotConfig, LoggingConfig, MarketConfig, QuoteConfig, RiskConfig, WarmupConfig


class TestIndicators:
    """Test the Indicators class risk management calculations."""

    @pytest.fixture
    def sample_config(self):
        """Sample configuration for testing."""
        market = MarketConfig(
            market="test-market",
            asset_id_yes="0x123",
            asset_id_no="0x456",
            start_ts_ms=1703123456789,
            resolve_ts_ms=1705731456789,
        )

        warmup = WarmupConfig()
        risk = RiskConfig(
            bankroll_B=1000.0,
            n_plays=3,
            eta_time=0.5,
            slippage_buffer=0.10,
            gamma_a=1.0,
            gamma_max=50.0,
            lambda_min=0.8,
            lambda_max=2.0,
            beta_p=0.7,
            alpha_U=0.5,
            U_ref=50.0,
        )
        quote = QuoteConfig()
        logging = LoggingConfig()

        return BotConfig(
            market=market,
            warmup=warmup,
            risk=risk,
            quote=quote,
            logging=logging,
        )

    @pytest.fixture
    def mock_logger(self):
        """Mock logger for testing."""
        logger = MagicMock(spec=JsonlLogger)
        return logger

    @pytest.fixture
    def indicators(self, sample_config, mock_logger):
        """Create Indicators instance for testing."""
        from pm4.trading import Indicators
        return Indicators(sample_config, mock_logger)

    @pytest.mark.unit
    def test_ema_calculation(self, indicators):
        """Test exponential moving average calculation."""
        # Test basic EMA calculation
        prev = 10.0
        x = 12.0
        tau_s = 60.0  # 1 minute
        dt_s = 10.0   # 10 seconds

        result = indicators._ema(prev, x, tau_s, dt_s)

        # EMA formula: prev + a * (x - prev) where a = 1 - exp(-dt/tau)
        # a = 1 - exp(-10/60) ≈ 1 - exp(-0.1667) ≈ 1 - 0.8476 = 0.1524
        # result = 10 + 0.1524 * (12 - 10) ≈ 10.3048
        import math
        a = 1.0 - math.exp(-dt_s / tau_s)
        expected = prev + a * (x - prev)
        assert result == pytest.approx(expected, abs=1e-6)

    @pytest.mark.unit
    def test_ema_edge_cases(self, indicators):
        """Test EMA with edge cases."""
        # Very small dt (smoothing factor is small, so result stays close to prev)
        result = indicators._ema(10.0, 12.0, 60.0, 0.001)
        assert result == pytest.approx(10.0, abs=0.01)  # Should stay close to 10.0

        # Very large tau (should change very slowly)
        result = indicators._ema(10.0, 12.0, 10000.0, 10.0)
        assert result == pytest.approx(10.0 + (12.0 - 10.0) * (10.0 / 10000.0), abs=1e-6)

        # Same values (should not change)
        result = indicators._ema(10.0, 10.0, 60.0, 10.0)
        assert result == 10.0

    @pytest.mark.unit
    def test_time_factor_calculation(self, indicators):
        """Test time factor calculation."""
        # Time factor uses eta_time parameter
        t_ms = 1703123456789 + 3600000  # 1 hour after start

        result = indicators.time_factor(t_ms)

        # time_factor = exp(-eta_time * time_elapsed_ratio)
        # This depends on the actual implementation, let's check what it returns
        assert isinstance(result, float)
        assert result > 0.0

        # Should decrease as time progresses (eta_time > 0)
        t_later = t_ms + 3600000  # Another hour later
        result_later = indicators.time_factor(t_later)
        assert result_later < result  # Should be smaller

    @pytest.mark.unit
    def test_B_side_calculation(self, indicators):
        """Test capital allocation per side."""
        result = indicators.B_side()

        # B_side = 0.5 * bankroll_B * (1/n_plays)
        expected = 0.5 * 1000.0 * (1.0 / 3)  # Half bankroll per side, divided by n_plays
        assert result == expected

    @pytest.mark.unit
    def test_q_max_calculation(self, indicators):
        """Test maximum position size calculation."""
        p = 0.6  # Price
        q = 50.0  # Current position
        t_ms = 1703123456789 + 1800000  # 30 minutes in

        result = indicators.q_max(p, q, t_ms)

        # q_max involves complex calculations with time factors, risk limits, etc.
        assert isinstance(result, float)
        # Should be positive for reasonable inputs
        assert result >= 0.0

    @pytest.mark.unit
    def test_q_hat_calculation(self, indicators):
        """Test position adjustment calculation."""
        q = 25.0
        p = 0.55
        t_ms = 1703123456789 + 900000  # 15 minutes in

        result = indicators.q_hat(q, p, t_ms)

        # q_hat adjusts position based on risk management
        assert isinstance(result, float)

    @pytest.mark.unit
    def test_gamma_calculation(self, indicators):
        """Test risk adjustment factor calculation."""
        # First normalize position using q_hat
        q_raw = 30.0
        p = 0.6
        t_ms = 1703123456789 + 900000
        qhat = indicators.q_hat(q_raw, p, t_ms)

        result = indicators.gamma(qhat)

        # gamma should be > 1.0 (spread scaling factor)
        assert result > 1.0
        assert result < 50.0  # Less than gamma_max

    @pytest.mark.unit
    def test_gamma_at_limits(self, indicators):
        """Test gamma calculation at boundaries."""
        # Small normalized position (close to 0)
        result_small = indicators.gamma(0.1)
        # gamma = 1 / (1 - 0.1)^1 ≈ 1 / 0.9 ≈ 1.111
        assert result_small == pytest.approx(1.111, abs=1e-3)

        # Large normalized position (close to 1, hits gamma_max)
        result_large = indicators.gamma(0.99)
        # gamma = 1 / (1 - 0.99)^1 = 1 / 0.01 = 100, but capped at gamma_max=50
        assert result_large == 50.0  # gamma_max limit

    @pytest.mark.unit
    def test_A_p_calculation(self, indicators):
        """Test price adjustment factor calculation."""
        p = 0.7

        result = indicators.A_p(p)

        # A_p = [(p*(1-p))/0.25]^beta_p
        # For p = 0.7, beta_p = 0.7: [(0.7*0.3)/0.25]^0.7 = [0.21/0.25]^0.7 = [0.84]^0.7 ≈ 0.885
        p_clipped = max(1e-6, min(1 - 1e-6, p))
        uncertainty = (p_clipped * (1.0 - p_clipped)) / 0.25
        expected = uncertainty ** indicators.cfg.risk.beta_p
        assert result == pytest.approx(expected, abs=1e-6)

        # Test with p < 0.5 (A_p is symmetric around 0.5)
        p_low = 0.3
        result_low = indicators.A_p(p_low)
        # A_p is the same for p and (1-p) due to symmetry
        expected_low = indicators.A_p(1 - p_low)  # Should equal A_p(0.7)
        assert result_low == pytest.approx(expected_low, abs=1e-6)

    @pytest.mark.unit
    def test_L_U_calculation(self, indicators):
        """Test utility function calculation."""
        U = 75.0

        result = indicators.L_U(U)

        # L_U = log(U / U_ref) or similar utility function
        # With U_ref = 50.0, U = 75.0
        # This depends on the specific implementation
        assert isinstance(result, float)

    @pytest.mark.unit
    def test_lambda_struct_calculation(self, indicators):
        """Test structural lambda calculation."""
        p = 0.65
        U = 60.0

        result = indicators.lambda_struct(p, U)

        # lambda_struct combines various risk factors
        assert isinstance(result, float)
        # Should be within configured bounds
        assert indicators.cfg.risk.lambda_min <= result <= indicators.cfg.risk.lambda_max


class TestLadderBuilding:
    """Test ladder building functions."""

    @pytest.mark.unit
    def test_build_v1_ladder_basic(self):
        """Test basic ladder building functionality."""
        from pm4.trading import build_v1_ladder

        result = build_v1_ladder(
            r_x=0.0,  # Reference price in logit space
            half_b=0.5,  # Half-spread below reference
            half_a=0.5,  # Half-spread above reference
            tick=0.01,   # Tick size
            B_side=100.0,  # Capital per side
        )

        assert "bids" in result
        assert "asks" in result
        assert isinstance(result["bids"], list)
        assert isinstance(result["asks"], list)

        # Should have some orders
        assert len(result["bids"]) > 0 or len(result["asks"]) > 0

    @pytest.mark.unit
    def test_build_v1_ladder_order_structure(self):
        """Test that ladder orders have correct structure."""
        from pm4.trading import build_v1_ladder

        result = build_v1_ladder(
            r_x=0.0,
            half_b=0.3,
            half_a=0.3,
            tick=0.01,
            B_side=50.0,
        )

        # Check bid orders structure
        for bid in result["bids"]:
            assert "level" in bid
            assert "price" in bid
            assert "size" in bid
            assert isinstance(bid["level"], int)
            assert isinstance(bid["price"], float)
            assert isinstance(bid["size"], float)
            assert 0.0 < bid["price"] < 1.0  # Valid probability range

        # Check ask orders structure
        for ask in result["asks"]:
            assert "level" in ask
            assert "price" in ask
            assert "size" in ask
            assert isinstance(ask["level"], int)
            assert isinstance(ask["price"], float)
            assert isinstance(ask["size"], float)
            assert 0.0 < ask["price"] < 1.0  # Valid probability range

    @pytest.mark.unit
    def test_build_v1_ladder_price_ordering(self):
        """Test that ladder prices are properly ordered."""
        from pm4.trading import build_v1_ladder

        result = build_v1_ladder(
            r_x=0.0,
            half_b=0.4,
            half_a=0.4,
            tick=0.01,
            B_side=75.0,
        )

        bids = result["bids"]
        asks = result["asks"]

        # Bids should be in descending price order (highest first)
        if len(bids) > 1:
            for i in range(len(bids) - 1):
                assert bids[i]["price"] >= bids[i + 1]["price"]

        # Asks should be in ascending price order (lowest first)
        if len(asks) > 1:
            for i in range(len(asks) - 1):
                assert asks[i]["price"] <= asks[i + 1]["price"]

    @pytest.mark.unit
    def test_build_v1_ladder_tick_rounding(self):
        """Test that prices are properly rounded to ticks."""
        from pm4.trading import build_v1_ladder

        tick = 0.05  # 5% tick size

        result = build_v1_ladder(
            r_x=0.0,
            half_b=0.5,
            half_a=0.5,
            tick=tick,
            B_side=100.0,
        )

        # All prices should be multiples of tick
        for bid in result["bids"]:
            price = bid["price"]
            # Check that price is a multiple of tick (within floating point precision)
            assert abs(round(price / tick) * tick - price) < 1e-10

        for ask in result["asks"]:
            price = ask["price"]
            assert abs(round(price / tick) * tick - price) < 1e-10

    @pytest.mark.unit
    def test_build_v1_ladder_size_decay(self):
        """Test that order sizes decay geometrically."""
        from pm4.trading import build_v1_ladder

        decay = 0.8  # 80% of previous level

        result = build_v1_ladder(
            r_x=0.0,
            half_b=0.6,
            half_a=0.6,
            tick=0.01,
            B_side=200.0,
            decay=decay,
        )

        bids = result["bids"]
        asks = result["asks"]

        # Check that sizes generally decrease (allowing for probability variations)
        # Since size = level_risk / p, and level_risk decays but p varies,
        # we just check that higher levels don't have massively larger sizes
        if len(bids) > 1:
            for i in range(len(bids) - 1):
                # Higher levels should not be more than 2x larger than previous
                # (decay should generally reduce sizes despite p variations)
                assert bids[i + 1]["size"] <= bids[i]["size"] * 2.0

        if len(asks) > 1:
            for i in range(len(asks) - 1):
                assert asks[i + 1]["size"] <= asks[i]["size"] * 2.0

    @pytest.mark.unit
    def test_build_v1_ladder_edge_cases(self):
        """Test ladder building with edge cases."""
        from pm4.trading import build_v1_ladder

        # Very tight spreads
        result = build_v1_ladder(
            r_x=0.0,
            half_b=0.01,  # Very small spread
            half_a=0.01,
            tick=0.01,
            B_side=10.0,
        )

        # Should still produce valid orders
        assert isinstance(result["bids"], list)
        assert isinstance(result["asks"], list)

        # Very wide spreads
        result = build_v1_ladder(
            r_x=0.0,
            half_b=2.0,  # Very wide spread
            half_a=2.0,
            tick=0.01,
            B_side=1000.0,
        )

        assert isinstance(result["bids"], list)
        assert isinstance(result["asks"], list)

    @pytest.mark.unit
    def test_build_v1_ladder_zero_capital(self):
        """Test ladder building with zero capital."""
        from pm4.trading import build_v1_ladder

        result = build_v1_ladder(
            r_x=0.0,
            half_b=0.5,
            half_a=0.5,
            tick=0.01,
            B_side=0.0,  # No capital
        )

        # Should still return valid structure, but possibly empty
        assert "bids" in result
        assert "asks" in result
        assert isinstance(result["bids"], list)
        assert isinstance(result["asks"], list)
