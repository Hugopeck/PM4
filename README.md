# PM4 - Prediction Market's Market Maker

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.1.3-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A high-frequency market making bot implementing the **PM4 model**: an Avellaneda-Stoikov inspired quantitative framework specifically adapted for prediction markets. Combines position sizing, real-time toxicity detection, and marchetype-aware structural risk adjustment.

## 📈 Overview

PM4 implements a **quantitative market making framework specifically designed for prediction markets**, extending the classical Avellaneda-Stoikov model to handle bounded price spaces, binary resolution, and information asymmetry.

### Core Innovation: Prediction Market Adaptation

Traditional A-S models assume unbounded prices and infinite horizons. PM4 addresses fundamental differences:

- **Bounded Arithmetic**: Prices ∈ [0,1] with logit-space calculations
- **Binary Resolution**: Hard stop at T with time-decaying risk limits
- **Marchetype Awareness**: 6 market types based on information availability and resolution timing
- **Toxicity Detection**: Real-time adverse selection using multi-scale volatility analysis
- **Structural Risk**: Market-type specific adjustments independent of short-term noise

### Mathematical Foundation

**Reservation Price (Logit Space):**
```
r = logit(p) - δ
```

**Skew Equation (PM4 Core):**
```
δ = q̂ × γ_dyn × λ × σ
```

Where:
- **q̂**: Normalized inventory relative to Kelly-optimal capacity limits
- **γ_dyn**: Dynamic solvency fear with self-correcting feedback loops
- **λ**: Structural market risk multiplier (bounded [1,2])
- **σ**: Toxicity multiplier from real-time adverse selection detection

**Optimal Half-Spread (PM4 Core):**
```
Δ_risk = c_risk × γ × λ × σ

Δ_liq,b = (1/γ) × ln(1 + γ/κ_b)
Δ_liq,a = (1/γ) × ln(1 + γ/κ_a)

Δ_b = Δ_risk + Δ_liq,b
Δ_a = Δ_risk + Δ_liq,a

Δ_tot = Δ_a + Δ_b
```

Where:
- **Δ_risk**: Inventory-independent risk term (base spread width in logit units)
- **c_risk**: Base spread scale parameter (typically 0.2 in logit units)
- **γ**: Dynamic solvency fear multiplier (≥ 1)
- **λ**: Structural market risk multiplier (bounded [1,2])
- **σ**: Toxicity multiplier from real-time adverse selection detection (≥ 1)
- **Δ_liq,b/Δ_liq,a**: Liquidity terms capturing fill intensity on bid/ask sides
- **κ_b/κ_a**: Effective order arrival intensity parameters per side (regime-dependent)
- **Δ_b/Δ_a**: Final half-spreads for bid and ask quotes (in logit space)
- **Δ_tot**: Total spread width (sum of bid and ask half-spreads)

### Key Features

- 🧮 **Kelly-Optimal Sizing**: Position limits based on opposite-side hedging costs and time decay
- 🕵️ **Toxicity Detection**: Multi-scale volatility analysis distinguishing chop from informed flow
- 🎯 **Marchetype Tuning**: Parameter optimization for 6 market types (a1-a3, e1-e3)
- 💰 **Dynamic Cash Floor**: Solvency protection with liability-matched capital reserves
- 📊 **Real-Time Calibration**: Continuous parameter adaptation from market microstructure
- 🧠 **Meta-Calibration**: Self-tuning warmup parameters based on market activity patterns
- 🔒 **Production Hardened**: Multi-level auth, comprehensive logging, graceful degradation

## 🏗️ Architecture

```
PM4/
├── warmup.py            # Standalone calibration & data collection
├── run_bot.py           # Trading execution with dry-run support
├── config.py            # Configuration loading utilities
├── types.py             # Configuration dataclasses & type definitions
├── utils.py             # Mathematical utilities & helper functions
├── logging.py           # Hierarchical logging & debugging system
├── adapters.py          # Exchange interfaces (Polymarket API)
├── market_data.py       # Real-time market data processing & trade analysis
├── trading.py           # PM4 model implementation & risk management
├── config.json          # Runtime configuration
└── requirements.txt     # Python dependencies
```

### PM4 Model Components

| Component | Mathematical Role | Key Innovation |
|-----------|------------------|----------------|
| **Meta-Calibrator** | Self-tuning warmup parameters | Market-activity-based parameter optimization |
| **Inventory Manager (q̂)** | Normalized position relative to Kelly capacity | Time-decaying limits based on hedging costs |
| **Solvency Fear (γ_dyn)** | Dynamic risk aversion with feedback loops | Self-correcting capital preservation |
| **Structural Risk (λ)** | Marchetype-aware market adjustment | Bounded multiplier [1,λ_max] for market types |
| **Toxicity Detector (σ)** | Real-time adverse selection | Multi-scale volatility distinguishing chop from informed flow |
| **Market Data** | State estimation & microstructure analysis | WebSocket processing with trade rate monitoring |
| **Exchange Adapter** | Order lifecycle & balance management | Multi-level authentication with automatic derivation |

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Polymarket account with API access
- Environment variables for authentication

### Installation

```bash
# Clone the repository
git clone https://github.com/Hugopeck/PM4
cd pm4

# Install dependencies
pip install -r requirements.txt
```

### Configuration

1. **Set Environment Variables:**
```bash
export PK="your_private_key"
export CLOB_API_KEY="your_api_key"          # Optional, auto-derived if missing
export CLOB_SECRET="your_api_secret"        # Optional, auto-derived if missing
export CLOB_PASS_PHRASE="your_passphrase"   # Optional, auto-derived if missing
export FUNDER_ADDRESS="your_funder_address" # Optional, for gasless trading
```

2. **Automated Market Setup:**
Use PM4's automated tools to generate complete configurations:

```bash
# Generate config automatically from Polymarket URL
python -m pm4.market_config_helper "https://polymarket.com/market/your-market-url"

# Or use interactive mode for guided setup
python -m pm4.market_config_helper --interactive
```

The config helper automatically:
- Extracts market condition ID and token IDs from Polymarket API
- Sets timestamps from market start/end dates
- Includes market analysis data
- Uses safe default risk parameters

### Market Analysis & Setup

PM4 includes automated tools to help you select suitable markets and generate configurations:

#### **Analyze Market Suitability:**
```bash
# Automatically evaluate market for PM4 compatibility
# Accepts both full URLs and market slugs
python -m pm4.market_analyzer "https://polymarket.com/market/ethereum-to-10k-before-2025"
# OR: python -m pm4.market_analyzer "ethereum-to-10k-before-2025"

# Save report to file
python -m pm4.market_analyzer "market-url" --output "report.txt"
```

**Example Output:**
```
======================================================================
MARKET STATUS REPORT: ethereum-to-10k-before-2025
======================================================================
Condition ID: 0x1234567890abcdef
Start Date: 2025-01-01T00:00:00Z
End Date: 2025-12-31T23:59:59Z

──────────────────────────────────────────────────────────────────────
DEFINITIONS
──────────────────────────────────────────────────────────────────────
Spread: Difference between best ask and best bid prices.
        Lower spread = tighter market = easier to profit from market making.
        Typical range: 0.5-5% (0.005-0.05 in probability space).

Liquidity: Available capital in order book (CLOB) or AMM pool.
          Higher liquidity = easier to enter/exit positions without slippage.
          Typical range: $1k-$100k+ for active markets.

──────────────────────────────────────────────────────────────────────
CORE MARKET MAKING METRICS
──────────────────────────────────────────────────────────────────────
Order Book:
  Best Bid:  0.3450 (34.50%)
  Best Ask:  0.3550 (35.50%)
  Spread:    0.0100 (1.00%)
  Context:   Moderate spread (typical: 0.5-2%)

Liquidity:
  CLOB: $45,230
  Context: Moderate liquidity (typical: $1k-$100k+)

Current Price: 0.3500 (35.00%)
  Context: Mid-range price (20-80%) - typical for market making

──────────────────────────────────────────────────────────────────────
ACTIVITY METRICS
──────────────────────────────────────────────────────────────────────
24h Volume:
  Total: $125,430
  Context: High volume (typical: $10k-$500k+ per day)

Last Trade: 0.8 hours ago
  Context: Recent activity (typical: < 6 hours)
```

#### **Generate Configuration Templates:**
```bash
# Create config from Polymarket URL
python -m pm4.market_config_helper "https://polymarket.com/market/ethereum-to-10k-before-2025"

# Interactive setup (guided configuration)
python -m pm4.market_config_helper --interactive
```

**Benefits:**
- Fully automated market evaluation based on comprehensive API data
- Factual status reporting with definitions and context (no arbitrary scoring)
- Automatic extraction of market IDs, token IDs, and timestamps from Polymarket
- Metrics organized by importance with typical ranges for interpretation
- Complete configuration generation with embedded market analysis
- Interactive workflow for guided setup
- Save reports to file with `--output` flag

### Running

PM4 uses a human-in-the-loop workflow that separates calibration from trading for safety and control:

```bash
# Step 1: Calibration - collect data and calculate risk parameters
python -m pm4.warmup config.json

# Step 2: Dry-run test - verify quotes without placing orders
python -m pm4.run_bot config.json --dry-run

# Step 3: Live trading - start automated market making
python -m pm4.run_bot config.json
```

**Workflow Explanation:**
1. **Calibration**: Three-phase process - observes market activity, meta-calibrates warmup parameters, then collects data with optimized settings
2. **Dry-run**: Loads calibration data, computes quotes in real-time, prints theoretical orders without executing them
3. **Live Trading**: Loads calibration data and begins automated market making with continuous parameter adaptation

**Benefits:**
- Human-in-the-loop validation of calibration results
- Ability to test quote behavior before risking capital
- Reuse calibration across multiple trading sessions

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PK` | ✅ | EOA private key for signature authentication |
| `CLOB_API_KEY` | ❌ | L2 API key (derived from PK if missing) |
| `CLOB_SECRET` | ❌ | L2 API secret (derived from PK if missing) |
| `CLOB_PASS_PHRASE` | ❌ | L2 API passphrase (derived from PK if missing) |
| `FUNDER_ADDRESS` | ❌ | Gasless trading funder address |
| `CLOB_HOST` | ❌ | API host (default: production) |
| `CHAIN_ID` | ❌ | Polygon network ID (default: 137) |
| `POLY_SIGNATURE_TYPE` | ❌ | Signature type (default: 1) |

### Configuration Parameters

#### Market Configuration
```json
{
  "market": {
    "market": "0x_CONDITION_ID",
    "asset_id_yes": "0x_YES_TOKEN_ID",
    "asset_id_no": "0x_NO_TOKEN_ID",
    "start_ts_ms": 1710000000000,
    "resolve_ts_ms": 1720000000000,
    "wss_url": "wss://ws-subscriptions-clob.polymarket.com/ws/market"
  }
}
```

#### Risk Management (PM4 Core Parameters)
```json
{
  "risk": {
    "bankroll_B": 500.0,        // Total capital allocation
    "n_plays": 3,               // Number of concurrent markets (1/n_plays = per-market weight)
    "eta_time": 0.5,            // Time decay exponent for capacity limits [0.25,0.75]
    "slippage_buffer": 0.10,    // Execution cost buffer (unused in current implementation)
    "gamma_a": 1.0,             // Solvency fear curvature (γ_dyn = 1/(1-|q̂|)^γ_a)
    "lambda_min": 1.0,          // Minimum structural risk multiplier
    "lambda_max": 2.0,          // Maximum structural risk multiplier (typically 2.0)
    "beta_p": 0.8,              // Ambiguity score curvature (market-type dependent)
    "alpha_U": 1.0,             // Crowd weakness curvature (market-type dependent)
    "U_ref": 100,               // Reference unique users for crowd strength
    "nu_sigma": 1.4             // Toxicity scaling exponent (convex response)
  }
}
```

#### Trading Parameters (Execution & Liquidity)
```json
{
  "quote": {
    "c_risk": 0.2,             // Base spread scale in logit units (Δ_risk = c_risk × γ × λ × σ)
    "kappa0": 1.0,              // Liquidity intensity parameter (unused in current implementation)
    "min_order_size": 1.0,      // Minimum order size in shares
    "max_order_notional_side": 100.0,  // Max notional exposure per side ($)
    "refresh_s": 2.0            // Quote refresh interval (seconds)
  }
}
```

#### Logging Configuration
```json
{
  "logging": {
    "level": "DEBUG",           // DEBUG, INFO, WARNING, ERROR, CRITICAL
    "enable_performance": true, // Function timing
    "enable_context_tracking": false  // Future feature
  }
}
```

## 🎯 Marchetypes: Market Classification System

PM4 uses a **marchetype system** to classify prediction markets based on information availability and resolution timing, enabling market-specific parameter tuning.

### Information Availability Levels

- **High Information**: Continuous, structured data feeds (crypto prices, sports scores, on-chain metrics)
- **Medium Information**: Public but noisy signals (news, polls, macro data, public company info)
- **Low Information**: Opaque or private information (insider decisions, leaks, unobservable processes)

### Resolution Types

- **Anytime Resolution**: Event can occur at any time before deadline T
- **End-of-Period Resolution**: Outcome determined only at fixed time T

### The 6 Marchetypes

| Type | Information | Resolution | Examples | Key Challenge |
|------|-------------|------------|----------|---------------|
| **a1** | Low | Anytime | CEO resignation, court ruling (opaque) | Price can be "fake"; insider dominance |
| **a2** | Medium | Anytime | Candidate withdrawal, merger announcement | Public info exists but jumps possible |
| **a3** | High | Anytime | BTC > 70k, team leads by 20 points | Barrier events with continuous monitoring |
| **e1** | Low | End-of-Period | Private startup ARR, confidential treaty | Interim signals unreliable |
| **e2** | Medium | End-of-Period | Election results, inflation data | Wisdom-of-crowds becomes decisive |
| **e3** | High | End-of-Period | Stock close, gold price at expiry | Underlying variable directly observable |

### Marchetype-Specific Tuning

Each marchetype requires different λ (structural risk) parameters:

```json
// Example: Election market (e2 - medium info, end-of-period)
{
  "beta_p": 1.0,     // Moderate ambiguity collapse away from 0.5
  "alpha_U": 1.5,    // Trust accelerates with participation
  "U_ref": 50        // Medium threshold for crowd strength
}

// Example: Barrier event (a3 - high info, anytime)
{
  "beta_p": 0.5,     // Keep ambiguity elevated at extremes
  "alpha_U": 0.8,    // Slower trust in crowd (observable underlying)
  "U_ref": 30        // Lower threshold (less need for massive participation)
}
```

## 🔍 Logging & Debugging

### Log Levels

PM4 uses hierarchical logging with configurable verbosity:

| Level | Purpose | Example Events |
|-------|---------|----------------|
| `DEBUG` | Development debugging | Function timing, variable dumps |
| `INFO` | Normal operations | Trades, orders, state changes |
| `WARNING` | Potential issues | Performance degradation, unusual conditions |
| `ERROR` | Operation failures | API errors, connection drops |
| `CRITICAL` | System failures | Data corruption, crashes |

### Performance Monitoring

Enable function timing with `@performance_trace()`:

```python
# Automatic performance logging when DEBUG enabled
@performance_trace()
def compute_quotes(self, q_yes: float) -> Dict[str, Any]:
    # Function execution time automatically logged
    return self.quoter.compute(q_yes)
```

### Error Context Capture

Comprehensive error logging with stack traces:

```python
try:
    risky_operation()
except Exception as e:
    ErrorContext.log_operation_error(logger, "risky_operation", e, {
        "context": "additional_data"
    })
```

## 🧪 Development

### Testing Philosophy

PM4's test suite validates **mathematical correctness without external dependencies**:

- **No API Mocking**: Tests focus on algorithmic validation, not network integration
- **Mathematical Verification**: Validates Kelly criterion, logit transformations, volatility calculations
- **Component Isolation**: Tests each PM4 component (q̂, γ_dyn, λ, σ) independently
- **Edge Case Coverage**: Boundary conditions, numerical stability, convergence behavior

### Test Coverage

```bash
# Run complete test suite (104+ tests, 80%+ coverage)
python -m pytest tests/

# Run with coverage reporting
python -m pytest tests/ --cov=pm4 --cov-report=html

# Test specific PM4 components
python -m pytest tests/test_utils.py          # Mathematical utilities (logit, sigmoid, price rounding)
python -m pytest tests/test_market_data.py   # WebSocket processing & trade analysis
python -m pytest tests/test_risk_management.py  # Kelly sizing, skew calculations, marchetype logic
python -m pytest tests/test_config.py        # Configuration loading & validation
python -m pytest tests/test_logging.py       # Performance tracing & error context
```

**Test Categories:**
- **Utility Functions**: Logit/sigmoid transformations, tick rounding, time utilities
- **Configuration**: JSON loading, parameter validation, default handling
- **Market Data**: Order book processing, trade rate calculations, buffer management
- **Risk Management**: Kelly-optimal sizing, solvency fear, structural risk (λ), toxicity detection (σ)
- **Logging**: JSONL output, performance monitoring, hierarchical error handling

### Setup Development Environment

```bash
# Install dependencies (includes testing framework)
pip install -r requirements.txt

# Run tests
python -m pytest

# Generate coverage report
python -m pytest --cov=pm4 --cov-report=html

# View coverage report
open htmlcov/index.html
```

## 🚨 Production Deployment

### Monitoring

1. **Log Analysis**: Monitor JSONL log files for events and performance
2. **Performance Metrics**: Enable `enable_performance: true` for timing data
3. **Error Tracking**: Set `level: "ERROR"` for production error monitoring

### Health Checks

```bash
# Check log files for recent activity
tail -f data/mm_events.jsonl | jq '.event'

# Monitor error rates
grep '"event": "error_' data/mm_events.jsonl | wc -l

# Check performance metrics
grep 'perf_' data/mm_events.jsonl | jq '.duration_ms' | sort -n
```

### Scaling Considerations

- **Single Market Focus**: Designed for one market per instance
- **Concurrent Markets**: Run multiple instances for different markets
- **Resource Usage**: Monitor memory and CPU for optimization
- **Rate Limits**: Respect Polymarket API limits and backoff on errors

## 🤝 Contributing

### Development Workflow

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/new-feature`
3. **Make** your changes with comprehensive tests
4. **Run** the test suite: `python -m pytest`
5. **Check** code quality: `mypy pm4/ && pylint pm4/`
6. **Submit** a pull request with detailed description

### Code Standards

- **Type Hints**: Full type annotation required
- **Documentation**: Comprehensive docstrings for all public APIs
- **Testing**: Unit tests for algorithms, integration tests for APIs
- **Logging**: Appropriate log levels and structured error handling
- **Performance**: Profile and optimize critical paths

### Adding New Features

1. **Exchange Adapters**: Extend `ExchangeAdapter` for new platforms
2. **Trading Strategies**: Implement new algorithms in `trading.py`
3. **Risk Models**: Add new risk management in `Indicators` class
4. **Data Sources**: Extend `MarketData` for additional feeds

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This software is for educational and research purposes. Trading cryptocurrencies and prediction markets involves substantial risk of loss. The authors and contributors are not responsible for any financial losses incurred through the use of this software.

### Risk Warnings

- **Market Risk**: Prediction markets can be highly volatile
- **Technical Risk**: Software bugs or network issues can cause losses
- **Regulatory Risk**: Ensure compliance with local laws and regulations
- **Operational Risk**: Monitor systems continuously in production

## 📚 References

### PM4 Model Documentation
- [PM4 Mathematical Foundation](PM4.md) - Complete model derivation and theoretical background
- [Marchetypes System](Marchetypes.md) - Market classification and information availability levels
- [Bounded Lambda](bounded%20lambda.md) - Structural risk multiplier derivation
- [Q_max Calculation](Q_max.md) - Kelly-optimal inventory limits
- [Sigma to Lambda Relationship](sigma%20to%20lambda%20rel.md) - Toxicity vs structural risk interaction
- [Marchetype Tuning](tunning%20per%20marchetype.md) - Parameter optimization by market type

### Academic Foundations
- **Avellaneda-Stoikov Model**: Classical market making with inventory risk
- **Kelly Criterion**: Optimal position sizing for favorable bets
- **Market Microstructure**: Price formation in limit order books
- **Prediction Market Theory**: Bounded prices, binary resolution, information asymmetry

### Related Research
- [High-Frequency Trading](https://en.wikipedia.org/wiki/High-frequency_trading) - Execution algorithms
- [Adverse Selection](https://en.wikipedia.org/wiki/Adverse_selection) - Informed trading detection
- [Volatility Estimation](https://en.wikipedia.org/wiki/Realized_volatility) - Multi-scale price movement analysis

### Technical References
- [Polymarket CLOB](https://docs.polymarket.com/#introduction) - Official API documentation
- [py_clob_client](https://github.com/Polymarket/py_clob_client) - Python SDK for Polymarket integration

---

**PM4**: Quantitative market making for prediction markets, extending Avellaneda-Stoikov to bounded prices, binary resolution, and information asymmetry. 🚀
