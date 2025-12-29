# Changelog

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

### Current Version: 0.1.1

**Version History:**
- `0.1.x`: Human-in-the-loop workflow and market analysis tools
- Future `0.2.x`: Production hardening and performance optimizations
- Future `1.0.x`: Stable API for production deployment

### Version Update Process
1. Update version in `pm4/__init__.py`
2. Add changelog entry in `CHANGELOG.md`
3. Update version badges in `README.md`
4. Tag release: `git tag v0.1.1 && git push --tags`
