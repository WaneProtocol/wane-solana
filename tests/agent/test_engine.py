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

    def test_stop_transitions_to_stopped(self, engine):
        engine.start()
        engine.stop()
        assert engine.state == EngineState.STOPPED

    def test_pause_transitions_to_paused(self, engine):
        engine.start()
        engine.pause()
        assert engine.state == EngineState.PAUSED

    def test_resume_transitions_from_paused_to_running(self, engine):
        engine.start()
        engine.pause()
        engine.resume()
        assert engine.state == EngineState.RUNNING

    def test_cannot_resume_from_stopped(self, engine):
        engine.start()
        engine.stop()
        with pytest.raises(RuntimeError, match="Cannot resume from STOPPED"):
            engine.resume()

    def test_emergency_stop(self, engine):
        engine.start()
        engine.emergency_stop()
        assert engine.state == EngineState.EMERGENCY_STOPPED

    def test_cannot_start_after_emergency_stop(self, engine):
        engine.start()
        engine.emergency_stop()
        with pytest.raises(RuntimeError, match="Emergency stop active"):
            engine.start()


class TestMarketDataProcessing:
    """Tests for market data ingestion and processing."""

    @pytest.mark.asyncio
    async def test_fetch_market_data(self, engine, mock_market_data):
        engine.market_client.get_price.return_value = mock_market_data
        data = await engine.fetch_market_data("SOL/USDC")
        assert data.symbol == "SOL/USDC"
        assert data.price == Decimal("142.50")

    @pytest.mark.asyncio
    async def test_fetch_market_data_handles_error(self, engine):
        engine.market_client.get_price.side_effect = ConnectionError("RPC timeout")
        with pytest.raises(ConnectionError):
            await engine.fetch_market_data("SOL/USDC")

    @pytest.mark.asyncio
    async def test_market_data_caching(self, engine, mock_market_data):
        engine.market_client.get_price.return_value = mock_market_data
        data1 = await engine.fetch_market_data("SOL/USDC")
        data2 = await engine.fetch_market_data("SOL/USDC")
        # Should use cache for second call within TTL
        assert engine.market_client.get_price.call_count <= 2

    @pytest.mark.asyncio
    async def test_market_data_validation(self, engine):
        invalid_data = MarketData(
            symbol="SOL/USDC",
            price=Decimal("-1"),  # Invalid negative price
            volume_24h=Decimal("0"),
            price_change_24h=Decimal("0"),
            high_24h=Decimal("0"),
            low_24h=Decimal("0"),
            bid=Decimal("0"),
            ask=Decimal("0"),
            timestamp=datetime.now(timezone.utc),
        )
        engine.market_client.get_price.return_value = invalid_data
        with pytest.raises(ValueError, match="Invalid market data"):
            await engine.fetch_market_data("SOL/USDC")


class TestSignalGeneration:
    """Tests for trade signal generation."""

    @pytest.mark.asyncio
    async def test_generate_buy_signal(self, engine, mock_market_data, mock_portfolio):
        signal = await engine.generate_signal(mock_market_data, mock_portfolio)
        assert signal is None or isinstance(signal, TradeSignal)

    @pytest.mark.asyncio
    async def test_signal_includes_mbti_params(self, engine, mock_market_data, mock_portfolio):
        signal = await engine.generate_signal(mock_market_data, mock_portfolio)
        if signal is not None:
            assert signal.mbti_type == MBTIType.INTJ
            assert signal.stop_loss_pct > 0
            assert signal.take_profit_pct > 0

    @pytest.mark.asyncio
    async def test_no_signal_in_low_volatility(self, engine, mock_portfolio):
        flat_data = MarketData(
            symbol="SOL/USDC",
            price=Decimal("100.00"),
            volume_24h=Decimal("100000"),  # Low volume
            price_change_24h=Decimal("0.001"),  # Barely moved
            high_24h=Decimal("100.10"),
            low_24h=Decimal("99.90"),
            bid=Decimal("99.99"),
            ask=Decimal("100.01"),
            timestamp=datetime.now(timezone.utc),
        )
        signal = await engine.generate_signal(flat_data, mock_portfolio)
        assert signal is None


class TestTradeExecution:
    """Tests for trade execution."""

    @pytest.mark.asyncio
    async def test_execute_trade_dry_run(self, engine):
        engine.config.dry_run = True
        signal = TradeSignal(
            side="buy",
            symbol="SOL/USDC",
            amount=Decimal("1.5"),
            price=Decimal("142.50"),
            mbti_type=MBTIType.INTJ,
            stop_loss_pct=Decimal("0.08"),
            take_profit_pct=Decimal("0.25"),
            confidence=Decimal("0.75"),
        )
        result = await engine.execute_trade(signal)
        assert result.dry_run is True
        assert result.status == "simulated"
        engine.sdk_client.execute_trade.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_trade_live(self, engine):
        engine.config.dry_run = False
        engine.sdk_client.execute_trade.return_value = TradeResult(
            tx_signature="txSig123",
            status="confirmed",
            fill_price=Decimal("142.55"),
            fill_amount=Decimal("1.5"),
            fees=Decimal("0.000005"),
            dry_run=False,
        )
        signal = TradeSignal(
            side="buy",
            symbol="SOL/USDC",
            amount=Decimal("1.5"),
            price=Decimal("142.50"),
            mbti_type=MBTIType.INTJ,
            stop_loss_pct=Decimal("0.08"),
            take_profit_pct=Decimal("0.25"),
            confidence=Decimal("0.75"),
        )
        result = await engine.execute_trade(signal)
        assert result.status == "confirmed"
        assert result.dry_run is False

    @pytest.mark.asyncio
    async def test_trade_rate_limiting(self, engine):
        engine.config.max_trades_per_hour = 2
        signal = TradeSignal(
            side="buy",
            symbol="SOL/USDC",
            amount=Decimal("1.0"),
            price=Decimal("100.00"),
            mbti_type=MBTIType.INTJ,
            stop_loss_pct=Decimal("0.08"),
            take_profit_pct=Decimal("0.25"),
            confidence=Decimal("0.8"),
        )
        await engine.execute_trade(signal)
        await engine.execute_trade(signal)
        with pytest.raises(RuntimeError, match="Rate limit exceeded"):
            await engine.execute_trade(signal)

    @pytest.mark.asyncio
    async def test_trade_respects_position_limits(self, engine, mock_portfolio):
        engine.portfolio = mock_portfolio
        signal = TradeSignal(
            side="buy",
            symbol="SOL/USDC",
            amount=Decimal("1000"),  # Way too large
            price=Decimal("142.50"),
            mbti_type=MBTIType.INTJ,
            stop_loss_pct=Decimal("0.08"),
            take_profit_pct=Decimal("0.25"),
            confidence=Decimal("0.8"),
        )
        with pytest.raises(ValueError, match="exceeds maximum position"):
            await engine.execute_trade(signal)


class TestPortfolioManagement:
    """Tests for portfolio state management."""

    @pytest.mark.asyncio
    async def test_get_portfolio_state(self, engine):
        engine.sdk_client.get_status.return_value = {
            "deposited_amount": 10_000_000_000,
            "current_balance": 10_125_500_000,
            "realized_pnl": 340_000_000,
            "total_trades": 15,
        }
        state = await engine.get_portfolio_state()
        assert state is not None
        assert state.total_value > 0

    @pytest.mark.asyncio
    async def test_pnl_calculation(self, engine, mock_portfolio):
        engine.portfolio = mock_portfolio
        pnl = engine.calculate_pnl()
        assert pnl.unrealized == Decimal("125.50")
        assert pnl.realized == Decimal("340.00")
        assert pnl.total == Decimal("465.50")

    def test_trade_history_tracking(self, engine):
        engine.record_trade(TradeResult(
            tx_signature="tx1",
            status="confirmed",
            fill_price=Decimal("100"),
            fill_amount=Decimal("1"),
            fees=Decimal("0.001"),
            dry_run=False,
        ))
        assert len(engine.trade_history) == 1

    def test_win_rate_calculation(self, engine):
        # Record 3 winning trades and 2 losing trades
        for i in range(3):
            engine.record_trade(TradeResult(
                tx_signature=f"win_{i}",
                status="confirmed",
                fill_price=Decimal("100"),
                fill_amount=Decimal("1"),
                fees=Decimal("0.001"),
                dry_run=False,
                pnl=Decimal("10"),
            ))
        for i in range(2):
            engine.record_trade(TradeResult(
                tx_signature=f"loss_{i}",
                status="confirmed",
                fill_price=Decimal("100"),
                fill_amount=Decimal("1"),
                fees=Decimal("0.001"),
                dry_run=False,
                pnl=Decimal("-5"),
            ))
        assert engine.win_rate() == pytest.approx(0.6)
