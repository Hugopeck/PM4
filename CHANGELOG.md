# Changelog

## [0.1.3] - 2024-12-30

### Added
- **Meta-Calibration System**: Self-tuning warmup parameters based on market activity
  - Three-phase warmup: observation → meta-calibration → calibration
  - Adaptive sampling intervals (`dt_sample_s`) based on price change frequency
  - Market-aware EMA time constants (`tau_fast_s`, `tau_slow_s`) using autocorrelation analysis
  - Activity-based markout horizons (`markout_h1_s`, `markout_h2_s`) from trade inter-arrival patterns
  - Continuous parameter adaptation during live trading with EMA-style updates
  - Separate meta-calibration persistence in `meta_warmup_params.json`
- **Activity Metrics Tracking**: Enhanced Indicators class with market microstructure analysis
  - Price change interval monitoring for optimal sampling rates
  - Trade inter-arrival time distribution analysis
  - Return autocorrelation half-life estimation for volatility clustering detection
  - Real-time activity pattern recognition for parameter optimization

### Technical Details
- **Meta-Calibration Algorithm**: Analyzes 100+ activity metrics to optimize 5 warmup parameters
- **Activity-Based Adaptation**: Parameters evolve with market conditions using 2-hour adaptation windows
- **Backward Compatibility**: Falls back to config defaults when meta-calibration unavailable
- **Robust Statistical Methods**: Uses median-based metrics to handle outliers and market noise

## [0.1.2] - 2024-12-30

### Added
- Comprehensive API data expansion in `market_analyzer`:
  - Volume breakdowns: AMM vs CLOB volumes (24h, 1wk, total)
  - Liquidity metrics: AMM and CLOB liquidity tracking
  - Order book data: Best bid/ask, spread analysis
  - Price change metrics: 1-hour, 1-day, 1-week price movements
  - Liquidity rewards: Min size and max spread parameters
  - Automatic token ID extraction: YES/NO token IDs from API response
- Enhanced `market_config_helper` with automatic field population:
  - Auto-extracts token IDs from Polymarket API (no manual copying needed)
  - Automatic timestamp conversion from market start/end dates
  - Embedded market analysis data in generated configs
  - Full API integration for zero-manual-config workflows

### Changed
- **API Endpoint Updates**: 
  - Updated to use Polymarket Gamma API endpoints: `/events/slug/{slug}` and `/markets/slug/{slug}`
  - Improved error handling with fallback between event and market endpoints
  - Enhanced data extraction to handle both event and market data structures
- **Format Improvements**:
  - Expanded `MarketAnalysis` dataclass with 15+ new fields for comprehensive market data
  - Enhanced analysis reports with detailed volume breakdowns, order book metrics, and price change data
  - Improved API response parsing with robust field name handling and JSON string parsing
- **Documentation Updates**:
  - Updated README.md to emphasize fully automated workflow (removed manual configuration steps)
  - Updated DRY_RUN_GUIDE.md to focus on automated tools only (removed manual market selection steps)
  - Streamlined documentation to reflect zero-manual-config capabilities
- **Code Cleanup**:
  - Removed unused `ExchangeAdapter` import from `pm4/run_bot.py`
  - Cleaned up Python cache directories (`__pycache__/`) 
  - Removed duplicate virtual environment (`.venv/` removed, standardized on `venv/`)
  - Removed system files (`.DS_Store`)
  - Updated `.gitignore` to include `venv/` directory

### Technical Details
- **API Integration**: 
  - Uses `https://gamma-api.polymarket.com` as base URL for all market data requests
  - Implements dual-endpoint strategy: tries events endpoint first, falls back to markets endpoint
  - Handles nested market data structures (events contain markets arrays)
  - Robust JSON parsing with fallbacks for string-encoded JSON fields
- **Data Extraction**:
  - Extracts token IDs from `clobTokenIds` array or nested `tokens` array
  - Parses ISO date formats with timezone handling for accurate timestamp conversion
  - Handles multiple field name variations (e.g., `volume24hr` vs `volume24h`)
  - Safe float conversion with defaults for missing or invalid values
- **Configuration Generation**:
  - Eliminates all manual steps: condition IDs, token IDs, timestamps all auto-filled
  - Embeds complete market analysis in generated config files
  - Uses API-derived dates for accurate start/resolution timestamps

## [0.1.1] - 2024-12-29

### Added
- `pm4.market_analyzer` module for automated market suitability analysis
- `pm4.market_config_helper` module for guided configuration generation
- Date conversion utilities in `pm4.utils` (`date_to_timestamp`, `timestamp_to_date`)
- Enhanced `config.json` with comprehensive parameter documentation and ranges
- Market analysis integration in `DRY_RUN_GUIDE.md`
- Interactive configuration setup workflow

### Changed
- Updated README.md with new workflow and tool documentation
- Enhanced dry-run guide with automated market analysis options
- Improved configuration safety with detailed parameter ranges

### Technical Details
- Market analyzer provides objective scoring (volume, traders, activity, time-to-resolution)
- Configuration helper extracts market slugs from Polymarket URLs
- Date utilities support multiple formats (YYYY-MM-DD, Month DD, YYYY, etc.)
- Comprehensive config documentation prevents misconfiguration

## [0.1.0] - 2024-12-29

### Added
- `pm4.warmup` module for standalone calibration and data collection
- `pm4.run_bot` module for trading execution with dry-run support
- `pm4.config` module for configuration loading utilities
- Human-in-the-loop workflow: separate calibration from execution for safety
- Dry-run mode (`--dry-run` flag) for testing quotes without placing orders
- Calibration persistence: save/load calibration state across sessions
- Comprehensive calibration reports with volatility analysis and sanity checks

### Changed
- Separated warmup (calibration) from execution (trading) phases
- New recommended workflow:
  1. `python -m pm4.warmup config.json` (calibration)
  2. `python -m pm4.run_bot config.json --dry-run` (test quotes)
  3. `python -m pm4.run_bot config.json` (live trading)

### Removed
- `pm4.main` module and `python -m pm4 config.json` entry point (replaced by new workflow)

### Technical Details
- Enhanced `Indicators` class with `save_calibration()` and `load_calibration()` methods
- Added full state persistence for calibration data including EMAs, returns deque, and timestamps
- Implemented `DryRunAdapter` for safe quote testing
- Improved error handling and validation throughout the calibration and trading pipeline

---

## Version Management

PM4 follows [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions
- **PATCH** version for backwards-compatible bug fixes

### Current Version: 0.1.2

**Version History:**
- `0.1.x`: Human-in-the-loop workflow and market analysis tools
- Future `0.2.x`: Production hardening and performance optimizations
- Future `1.0.x`: Stable API for production deployment

### Version Update Process
1. Update version in `pm4/__init__.py`
2. Add changelog entry in `CHANGELOG.md`
3. Update version badges in `README.md`
4. Tag release: `git tag v0.1.1 && git push --tags`
