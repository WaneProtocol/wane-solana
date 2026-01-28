"""Tests for MBTI-based trading strategies."""

import pytest
from decimal import Decimal
from datetime import datetime, timezone

from src.strategies import (
    MBTIType,
    StrategyFactory,
    INTJStrategy,
    ENFPStrategy,
    ISTJStrategy,
    ENTPStrategy,
    BaseStrategy,
    TradeSignal,
    MarketSnapshot,
    IndicatorSet,
)


@pytest.fixture
def bullish_snapshot():
    return MarketSnapshot(
        symbol="SOL/USDC",
        price=Decimal("105.00"),
        ema_20=Decimal("100.00"),
        ema_50=Decimal("97.00"),
        ema_200=Decimal("92.00"),
        rsi=Decimal("58"),
        macd_value=Decimal("2.5"),
        macd_signal=Decimal("1.8"),
        macd_histogram=Decimal("0.7"),
        bollinger_upper=Decimal("112.00"),
        bollinger_middle=Decimal("100.00"),
        bollinger_lower=Decimal("88.00"),
        volume=Decimal("5000000"),
        avg_volume=Decimal("2000000"),
        atr=Decimal("3.50"),
        funding_rate=Decimal("0.01"),
        sentiment_score=Decimal("0.6"),
        social_volume=Decimal("15000"),
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def bearish_snapshot():
    return MarketSnapshot(
        symbol="SOL/USDC",
        price=Decimal("85.00"),
        ema_20=Decimal("90.00"),
        ema_50=Decimal("95.00"),
        ema_200=Decimal("100.00"),
        rsi=Decimal("28"),
        macd_value=Decimal("-3.0"),
        macd_signal=Decimal("-1.5"),
        macd_histogram=Decimal("-1.5"),
        bollinger_upper=Decimal("98.00"),
        bollinger_middle=Decimal("90.00"),
        bollinger_lower=Decimal("82.00"),
        volume=Decimal("3000000"),
        avg_volume=Decimal("2000000"),
        atr=Decimal("4.20"),
        funding_rate=Decimal("-0.05"),
        sentiment_score=Decimal("-0.7"),
        social_volume=Decimal("5000"),
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def neutral_snapshot():
    return MarketSnapshot(
        symbol="SOL/USDC",
        price=Decimal("100.00"),
        ema_20=Decimal("100.00"),
        ema_50=Decimal("100.00"),
        ema_200=Decimal("99.50"),
        rsi=Decimal("50"),
        macd_value=Decimal("0.1"),
        macd_signal=Decimal("0.0"),
        macd_histogram=Decimal("0.1"),
        bollinger_upper=Decimal("104.00"),
        bollinger_middle=Decimal("100.00"),
        bollinger_lower=Decimal("96.00"),
        volume=Decimal("2000000"),
        avg_volume=Decimal("2000000"),
        atr=Decimal("2.00"),
        funding_rate=Decimal("0.001"),
        sentiment_score=Decimal("0.0"),
        social_volume=Decimal("10000"),
        timestamp=datetime.now(timezone.utc),
    )


class TestStrategyFactory:
    """Tests for strategy factory pattern."""

    def test_create_all_16_strategies(self):
        for mbti_type in MBTIType:
            strategy = StrategyFactory.create(mbti_type)
            assert strategy is not None
            assert isinstance(strategy, BaseStrategy)

    def test_intj_creates_correct_class(self):
        strategy = StrategyFactory.create(MBTIType.INTJ)
        assert isinstance(strategy, INTJStrategy)

    def test_enfp_creates_correct_class(self):
        strategy = StrategyFactory.create(MBTIType.ENFP)
        assert isinstance(strategy, ENFPStrategy)

    def test_istj_creates_correct_class(self):
        strategy = StrategyFactory.create(MBTIType.ISTJ)
        assert isinstance(strategy, ISTJStrategy)

    def test_entp_creates_correct_class(self):
        strategy = StrategyFactory.create(MBTIType.ENTP)
        assert isinstance(strategy, ENTPStrategy)

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Unknown MBTI type"):
            StrategyFactory.create("XXXX")


class TestINTJStrategy:
    """INTJ: Strategic Mastermind - Trend following with macro overlay."""

    @pytest.fixture
    def strategy(self):
        return StrategyFactory.create(MBTIType.INTJ)

    def test_parameters(self, strategy):
        assert strategy.risk_tolerance == pytest.approx(0.65, abs=0.05)
        assert strategy.max_position_pct == pytest.approx(0.30, abs=0.05)
        assert strategy.stop_loss_pct == pytest.approx(0.08, abs=0.02)
        assert strategy.take_profit_pct == pytest.approx(0.25, abs=0.05)

    def test_buy_signal_bullish_trend(self, strategy, bullish_snapshot):
        """INTJ should generate buy when price above 200 EMA with MACD confirmation."""
        signal = strategy.analyze(bullish_snapshot)
        assert signal is not None
        assert signal.side == "buy"
        assert signal.confidence >= Decimal("0.5")

    def test_no_signal_below_200_ema(self, strategy, bearish_snapshot):
        """INTJ requires price above 200 EMA -- no entry in downtrend."""
        signal = strategy.analyze(bearish_snapshot)
        assert signal is None or signal.side == "sell"
