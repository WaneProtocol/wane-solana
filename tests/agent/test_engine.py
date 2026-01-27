"""Tests for the PIKKY trading engine."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import datetime, timezone

from src.engine import (
    TradingEngine,
    EngineConfig,
    EngineState,
    TradeSignal,
    TradeResult,
    MarketData,
    PortfolioState,
)
from src.strategies import MBTIType


@pytest.fixture
def engine_config():
    return EngineConfig(
        rpc_url="https://api.devnet.solana.com",
        wallet_path="./test-wallet.json",
        mbti_type=MBTIType.INTJ,
        max_trades_per_hour=10,
        dry_run=True,
    )


@pytest.fixture
def mock_market_data():
    return MarketData(
        symbol="SOL/USDC",
        price=Decimal("142.50"),
        volume_24h=Decimal("1500000000"),
        price_change_24h=Decimal("0.035"),
        high_24h=Decimal("145.00"),
        low_24h=Decimal("138.00"),
        bid=Decimal("142.48"),
        ask=Decimal("142.52"),
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_portfolio():
    return PortfolioState(
        total_value=Decimal("10000"),
        sol_balance=Decimal("50"),
        usdc_balance=Decimal("2875"),
        positions={
            "SOL": Decimal("50"),
        },
        unrealized_pnl=Decimal("125.50"),
        realized_pnl=Decimal("340.00"),
    )


@pytest.fixture
def engine(engine_config):
    with patch("src.engine.load_wallet"):
        engine = TradingEngine(engine_config)
        engine.market_client = AsyncMock()
        engine.sdk_client = AsyncMock()
        return engine


class TestEngineInit:
    """Tests for engine initialization."""

    def test_init_with_valid_config(self, engine_config):
        with patch("src.engine.load_wallet"):
            engine = TradingEngine(engine_config)
            assert engine.config == engine_config
            assert engine.state == EngineState.IDLE

    def test_init_sets_mbti_strategy(self, engine_config):
        with patch("src.engine.load_wallet"):
            engine = TradingEngine(engine_config)
            assert engine.strategy is not None
            assert engine.strategy.mbti_type == MBTIType.INTJ

    def test_init_with_dry_run(self, engine_config):
        engine_config.dry_run = True
        with patch("src.engine.load_wallet"):
            engine = TradingEngine(engine_config)
            assert engine.config.dry_run is True

    def test_init_with_invalid_rpc_url(self):
        config = EngineConfig(
            rpc_url="",
            wallet_path="./test.json",
            mbti_type=MBTIType.INTJ,
        )
        with pytest.raises(ValueError, match="RPC URL is required"):
            TradingEngine(config)

    def test_init_with_trade_limit(self, engine_config):
        engine_config.max_trades_per_hour = 5
        with patch("src.engine.load_wallet"):
            engine = TradingEngine(engine_config)
            assert engine.config.max_trades_per_hour == 5


class TestEngineStateManagement:
    """Tests for engine state transitions."""

    def test_start_transitions_to_running(self, engine):
        engine.start()
        assert engine.state == EngineState.RUNNING
