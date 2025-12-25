# PM4 - Polymarket CLOB Market Maker

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A high-frequency, algorithmic market making bot for Polymarket's prediction markets, built with sophisticated risk management and real-time market data processing.

## 📈 Overview

PM4 is a production-ready market making bot that automatically provides liquidity in Polymarket's prediction markets. It implements advanced quantitative strategies including:

- **Kelly Criterion** position sizing for optimal risk-adjusted returns
- **Dynamic spread scaling** based on market volatility and inventory
- **Real-time market microstructure** analysis
- **Multi-level authentication** with automatic credential derivation
- **Comprehensive performance monitoring** and error handling

### Key Features

- 🚀 **High-Frequency Trading**: Sub-millisecond response times with WebSocket connectivity
- 🧮 **Advanced Risk Management**: Kelly criterion, volatility estimation, markout analysis
- 📊 **Real-Time Analytics**: Market data processing, trade rate monitoring, spread analysis
- 🔧 **Production Ready**: Comprehensive logging, error handling, graceful degradation
- 🏗️ **Modular Architecture**: Clean separation of concerns, extensible design
- 🔒 **Secure**: Multi-level authentication with automatic credential management

## 🏗️ Architecture

```
PM4/
├── main.py              # Application entry point & orchestration
├── types.py             # Configuration dataclasses & type definitions
├── utils.py             # Mathematical utilities & helper functions
├── logging.py           # Hierarchical logging & debugging system
├── adapters.py          # Exchange interfaces (Polymarket API)
├── market_data.py       # Real-time market data processing
├── trading.py           # Core trading algorithms & risk management
├── config.json          # Runtime configuration
└── requirements.txt     # Python dependencies
```

### Core Components

| Component | Purpose | Key Features |
|-----------|---------|--------------|
| **Trading Engine** | Risk management & order generation | Kelly criterion, dynamic spreads, position sizing |
| **Market Data** | Real-time data processing | WebSocket feeds, order book state, trade analysis |
| **Exchange Adapter** | API integration | Authentication, order lifecycle, balance management |
| **Logging System** | Debugging & monitoring | Hierarchical levels, performance tracing, error context |

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Polymarket account with API access
- Environment variables for authentication

### Installation

```bash
# Clone the repository
git clone <repository-url>
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

2. **Configure Markets:**
Edit `config.json` to specify target markets and risk parameters:

```json
{
  "market": {
    "market": "0x_CONDITION_ID",
    "asset_id_yes": "0x_YES_TOKEN_ID",
    "asset_id_no": "0x_NO_TOKEN_ID",
    "start_ts_ms": 1710000000000,
    "resolve_ts_ms": 1720000000000
  },
  "risk": {
    "bankroll_B": 500.0,
    "n_plays": 3
  },
  "logging": {
    "level": "INFO",
    "enable_performance": false
  }
}
```

### Running

```bash
# Start the market maker
python pm4.py config.json

# The bot will:
# 1. Connect to Polymarket WebSocket feeds
# 2. Perform market calibration (warmup phase)
# 3. Begin automated market making
# 4. Log activity and performance metrics
```

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

#### Risk Management
```json
{
  "risk": {
    "bankroll_B": 500.0,        // Total capital allocation
    "n_plays": 3,               // Number of concurrent markets
    "eta_time": 0.5,            // Time decay exponent
    "slippage_buffer": 0.10,    // Execution cost buffer
    "gamma_a": 1.0,             // Spread scaling parameter
    "lambda_min": 0.8,          // Minimum regime factor
    "lambda_max": 2.0           // Maximum regime factor
  }
}
```

#### Trading Parameters
```json
{
  "quote": {
    "c_risk": 0.06,             // Risk coefficient
    "kappa0": 1.0,              // Liquidity scaling base
    "min_order_size": 1.0,      // Minimum order size
    "max_order_notional_side": 100.0,  // Max notional per side
    "refresh_s": 2.0            // Quote refresh interval
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

## 📊 Trading Algorithms

### Kelly Criterion Position Sizing

PM4 uses the Kelly Criterion for optimal position sizing:

```
q_max = (B_side × time_factor) / (p_opp × (1 + slippage_buffer))
```

Where:
- `q_max`: Maximum position size for optimal growth
- `B_side`: Capital allocated per side
- `time_factor`: Time-based risk decay
- `p_opp`: Probability of adverse outcome
- `slippage_buffer`: Execution cost adjustment

### Dynamic Spread Scaling

Bid-ask spreads scale with position size and volatility:

```
γ = 1 / (1 - |q̂|)ᵧₐ
```

Where:
- `γ`: Spread multiplier (> 1.0)
- `q̂`: Normalized position size [-1, 1]
- `γₐ`: Aggressiveness parameter

### Volatility Estimation

Multi-timeframe exponential moving averages:

```python
# Fast EMA (short-term volatility)
ema_fast = ema(prev_fast, abs_return, τ_fast, dt)

# Slow EMA (baseline volatility)
ema_slow = ema(prev_slow, abs_return, τ_slow, dt)

# Volatility ratio for stress detection
J = ema_fast / ema_slow
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

### Setup Development Environment

```bash
# Install development dependencies
pip install -r requirements-dev.txt  # If available

# Run tests
python -m pytest

# Check code quality
mypy pm4/                    # Type checking
pylint pm4/                  # Code quality
black pm4/ --check          # Formatting check
```

### Project Structure

```
pm4/
├── __init__.py           # Package initialization
├── main.py              # Entry point and configuration loading
├── types.py             # Configuration dataclasses and types
├── utils.py             # Mathematical utilities and helpers
├── logging.py           # Logging system with debugging features
├── adapters.py          # Exchange API interfaces
├── market_data.py       # Real-time market data processing
└── trading.py           # Core trading algorithms
```

### Key Classes

| Class | Module | Purpose |
|-------|--------|---------|
| `MarketMakerBot` | `trading.py` | Main orchestration and control |
| `Indicators` | `trading.py` | Risk management and volatility estimation |
| `Quoter` | `trading.py` | Order generation and pricing |
| `PolymarketAdapter` | `adapters.py` | Exchange API integration |
| `MarketData` | `market_data.py` | Real-time data processing |
| `DebugLogger` | `logging.py` | Enhanced logging with levels |

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

### Academic Papers
- [Kelly Criterion](https://en.wikipedia.org/wiki/Kelly_criterion) - Optimal bet sizing
- [Market Microstructure](https://en.wikipedia.org/wiki/Market_microstructure) - Trading mechanics
- [High-Frequency Trading](https://en.wikipedia.org/wiki/High-frequency_trading) - HFT principles

### Related Projects
- [Polymarket CLOB](https://docs.polymarket.com/#introduction) - Official API documentation
- [py_clob_client](https://github.com/Polymarket/py_clob_client) - Python SDK

---

**PM4**: Professional market making for prediction markets. 🚀
