# Changelog

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
