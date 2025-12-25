"""
Pytest configuration and shared fixtures for PM4 tests.

This module provides:
- Common test fixtures for mocking external dependencies
- Test configuration helpers
- Async test utilities
- Mock objects for Polymarket API responses
"""
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from pm4.logging import JsonlLogger
from pm4.types import (
    BotConfig,
    LoggingConfig,
    MarketConfig,
    QuoteConfig,
    RiskConfig,
    WarmupConfig,
)


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests that need file I/O."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config():
    """Sample bot configuration for testing."""
    market = MarketConfig(
        market="test-market",
        asset_id_yes="0x1234567890abcdef",
        asset_id_no="0xfedcba0987654321",
        start_ts_ms=1703123456789,
        resolve_ts_ms=1705731456789,
    )

    warmup = WarmupConfig()
    risk = RiskConfig()
    quote = QuoteConfig()
    logging = LoggingConfig()

    return BotConfig(
        market=market,
        warmup=warmup,
        risk=risk,
        quote=quote,
        logging=logging,
        log_path="./data/test_events.jsonl",
        calib_path="./data/test_calibration.json",
    )


@pytest.fixture
def mock_logger(temp_dir):
    """Mock JsonlLogger for testing."""
    log_path = temp_dir / "test_log.jsonl"
    logger = JsonlLogger(str(log_path))

    # Mock the write method to avoid file I/O in tests
    original_write = logger.write
    logger.write = MagicMock(side_effect=original_write)

    yield logger

    # Cleanup
    if log_path.exists():
        log_path.unlink()


@pytest.fixture
def mock_clob_client():
    """Mock py_clob_client.ClobClient for testing exchange adapter."""
    mock_client = MagicMock()

    # Mock balance responses
    mock_client.get_balance_allowance.side_effect = lambda params: {
        "balance": "1000.0" if params.asset_type.name == "COLLATERAL"
        else "500.0"
    }

    # Mock order responses
    mock_client.get_orders.return_value = [
        {
            "id": "order_123",
            "side": "BUY",
            "asset_id": "0x1234567890abcdef",
            "price": "0.65",
            "size": "100.0",
            "size_matched": "50.0",
        }
    ]

    # Mock trade responses
    mock_client.get_trades.return_value = [
        {
            "timestamp": 1703123456789,
            "side": "BUY",
            "asset_id": "0x1234567890abcdef",
            "price": "0.65",
            "size": "10.0",
            "order_id": "order_123",
        }
    ]

    # Mock order placement
    mock_client.create_and_post_order.return_value = {"orderID": "new_order_456"}

    return mock_client


@pytest.fixture
def mock_exchange_adapter(mock_clob_client, monkeypatch):
    """Mock ExchangeAdapter for testing trading logic without real API calls."""
    from pm4.adapters import PolymarketAdapter

    # Mock the ClobClient import
    mock_adapter = MagicMock(spec=PolymarketAdapter)
    mock_adapter.get_balances = AsyncMock(return_value={
        "USDC": 1000.0,
        "YES": 500.0,
        "NO": 300.0,
    })

    mock_adapter.list_open_orders = AsyncMock(return_value=[
        {
            "order_id": "order_123",
            "side": "BUY",
            "asset_id": "0x1234567890abcdef",
            "price": 0.65,
            "size": 100.0,
            "size_remaining": 50.0,
        }
    ])

    mock_adapter.cancel_order = AsyncMock(return_value=None)
    mock_adapter.place_limit_order = AsyncMock(return_value="new_order_456")

    mock_adapter.get_fills = AsyncMock(return_value=[
        {
            "ts_ms": 1703123456789,
            "side": "BUY",
            "asset_id": "0x1234567890abcdef",
            "price": 0.65,
            "size": 10.0,
            "order_id": "order_123",
        }
    ])

    return mock_adapter


@pytest.fixture
def sample_config_file(temp_dir, sample_config):
    """Create a temporary config file for testing config loading."""
    config_path = temp_dir / "test_config.json"
    config_data = {
        "market": {
            "market": sample_config.market.market,
            "asset_id_yes": sample_config.market.asset_id_yes,
            "asset_id_no": sample_config.market.asset_id_no,
            "start_ts_ms": sample_config.market.start_ts_ms,
            "resolve_ts_ms": sample_config.market.resolve_ts_ms,
        },
        "warmup": {},
        "risk": {},
        "quote": {},
        "logging": {},
        "log_path": str(sample_config.log_path),
        "calib_path": str(sample_config.calib_path),
    }

    with open(config_path, 'w') as f:
        json.dump(config_data, f, indent=2)

    return config_path
