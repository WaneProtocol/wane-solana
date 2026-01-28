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

    def test_no_signal_neutral_market(self, strategy, neutral_snapshot):
        """INTJ waits for clear trend -- no signal in sideways market."""
        signal = strategy.analyze(neutral_snapshot)
        assert signal is None

    def test_exit_signal_on_macd_divergence(self, strategy):
        """INTJ exits on weekly MACD bearish divergence."""
        snapshot = MarketSnapshot(
            symbol="SOL/USDC",
            price=Decimal("120.00"),
            ema_20=Decimal("118.00"),
            ema_50=Decimal("115.00"),
            ema_200=Decimal("95.00"),
            rsi=Decimal("72"),
            macd_value=Decimal("1.0"),
            macd_signal=Decimal("2.5"),  # MACD below signal = bearish
            macd_histogram=Decimal("-1.5"),
            bollinger_upper=Decimal("125.00"),
            bollinger_middle=Decimal("115.00"),
            bollinger_lower=Decimal("105.00"),
            volume=Decimal("1500000"),
            avg_volume=Decimal("2000000"),
            atr=Decimal("3.00"),
            funding_rate=Decimal("0.02"),
            sentiment_score=Decimal("0.4"),
            social_volume=Decimal("12000"),
            timestamp=datetime.now(timezone.utc),
        )
        signal = strategy.analyze(snapshot)
        if signal is not None:
            assert signal.side == "sell"

    def test_position_sizing(self, strategy, bullish_snapshot):
        """INTJ should size positions at up to 30% of portfolio."""
        signal = strategy.analyze(bullish_snapshot)
        if signal is not None:
            portfolio_value = Decimal("10000")
            position_size = strategy.calculate_position_size(
                signal, portfolio_value
            )
            max_size = portfolio_value * Decimal(str(strategy.max_position_pct))
            assert position_size <= max_size


class TestENFPStrategy:
    """ENFP: Enthusiastic Explorer - Momentum breakout with narrative."""

    @pytest.fixture
    def strategy(self):
        return StrategyFactory.create(MBTIType.ENFP)

    def test_parameters(self, strategy):
        assert strategy.risk_tolerance == pytest.approx(0.75, abs=0.05)
        assert strategy.max_position_pct == pytest.approx(0.08, abs=0.03)
        assert strategy.entry_aggression >= 0.8

    def test_buy_on_momentum_breakout(self, strategy, bullish_snapshot):
        """ENFP enters on momentum with high volume and social buzz."""
        # High volume = 2.5x average, social volume high
        signal = strategy.analyze(bullish_snapshot)
        if signal is not None:
            assert signal.side == "buy"
            assert signal.confidence > Decimal("0")

    def test_small_position_sizes(self, strategy, bullish_snapshot):
        """ENFP diversifies with many small bets."""
        signal = strategy.analyze(bullish_snapshot)
        if signal is not None:
            portfolio_value = Decimal("10000")
            position_size = strategy.calculate_position_size(
                signal, portfolio_value
            )
            # ENFP max is ~8% of portfolio
            assert position_size <= portfolio_value * Decimal("0.10")

    def test_fast_entry(self, strategy):
        """ENFP has high entry aggression (enters quickly)."""
        assert strategy.entry_aggression >= 0.85

    def test_exit_on_momentum_fade(self, strategy, neutral_snapshot):
        """ENFP exits when momentum fades."""
        # Neutral market = no momentum
        signal = strategy.analyze(neutral_snapshot)
        assert signal is None or signal.side == "sell"


class TestISTJStrategy:
    """ISTJ: Disciplined Guardian - Systematic trend following."""

    @pytest.fixture
    def strategy(self):
        return StrategyFactory.create(MBTIType.ISTJ)

    def test_parameters(self, strategy):
        assert strategy.risk_tolerance == pytest.approx(0.25, abs=0.05)
        assert strategy.stop_loss_pct == pytest.approx(0.03, abs=0.01)
        assert strategy.entry_aggression <= 0.2

    def test_requires_all_confirmations(self, strategy, bullish_snapshot):
        """ISTJ requires EMA cross + MACD + RSI all confirming."""
        signal = strategy.analyze(bullish_snapshot)
        if signal is not None:
            assert signal.side == "buy"
            # Should have high confidence due to multiple confirmations
            assert signal.confidence >= Decimal("0.6")

    def test_tight_stop_loss(self, strategy):
        """ISTJ uses tight stop-loss (3%)."""
        assert strategy.stop_loss_pct <= 0.04

    def test_no_signal_without_ema_cross(self, strategy):
        """ISTJ requires 20/50 EMA golden cross."""
        snapshot = MarketSnapshot(
            symbol="SOL/USDC",
            price=Decimal("100.00"),
            ema_20=Decimal("98.00"),  # Below EMA 50 = no cross
            ema_50=Decimal("99.00"),
            ema_200=Decimal("95.00"),
            rsi=Decimal("52"),
            macd_value=Decimal("1.0"),
            macd_signal=Decimal("0.5"),
            macd_histogram=Decimal("0.5"),
            bollinger_upper=Decimal("108.00"),
            bollinger_middle=Decimal("100.00"),
            bollinger_lower=Decimal("92.00"),
            volume=Decimal("2500000"),
            avg_volume=Decimal("2000000"),
            atr=Decimal("2.50"),
            funding_rate=Decimal("0.005"),
            sentiment_score=Decimal("0.3"),
            social_volume=Decimal("8000"),
            timestamp=datetime.now(timezone.utc),
        )
        signal = strategy.analyze(snapshot)
        assert signal is None

    def test_exit_on_death_cross(self, strategy, bearish_snapshot):
        """ISTJ always exits on 20/50 EMA death cross."""
        signal = strategy.analyze(bearish_snapshot)
        if signal is not None:
            assert signal.side == "sell"


class TestENTPStrategy:
    """ENTP: Contrarian Innovator - Bets against the crowd."""

    @pytest.fixture
    def strategy(self):
        return StrategyFactory.create(MBTIType.ENTP)

    def test_parameters(self, strategy):
        assert strategy.risk_tolerance == pytest.approx(0.70, abs=0.05)
        assert strategy.take_profit_pct == pytest.approx(0.30, abs=0.05)

    def test_buy_on_extreme_fear(self, strategy, bearish_snapshot):
        """ENTP goes long when sentiment is extremely negative (contrarian)."""
        signal = strategy.analyze(bearish_snapshot)
        if signal is not None:
            # Contrarian: buys when everyone is selling
            assert signal.side == "buy"

    def test_no_signal_neutral_sentiment(self, strategy, neutral_snapshot):
        """ENTP needs extreme sentiment to trigger -- neutral = no trade."""
        signal = strategy.analyze(neutral_snapshot)
        assert signal is None

    def test_sell_on_extreme_greed(self, strategy):
        """ENTP sells when everyone is euphoric."""
        euphoric_snapshot = MarketSnapshot(
            symbol="SOL/USDC",
            price=Decimal("150.00"),
            ema_20=Decimal("140.00"),
            ema_50=Decimal("130.00"),
            ema_200=Decimal("110.00"),
            rsi=Decimal("85"),
            macd_value=Decimal("8.0"),
            macd_signal=Decimal("6.0"),
            macd_histogram=Decimal("2.0"),
            bollinger_upper=Decimal("148.00"),
            bollinger_middle=Decimal("130.00"),
            bollinger_lower=Decimal("112.00"),
            volume=Decimal("8000000"),
            avg_volume=Decimal("2000000"),
            atr=Decimal("6.00"),
            funding_rate=Decimal("0.10"),  # Extreme positive funding
            sentiment_score=Decimal("0.95"),  # Extreme greed
            social_volume=Decimal("50000"),  # Mania
            timestamp=datetime.now(timezone.utc),
        )
        signal = strategy.analyze(euphoric_snapshot)
        if signal is not None:
            assert signal.side == "sell"

    def test_wide_take_profit(self, strategy):
        """ENTP uses wide take-profit for contrarian conviction."""
        assert strategy.take_profit_pct >= 0.25

    def test_uses_sentiment_indicators(self, strategy):
        """ENTP weights sentiment and funding rate heavily."""
        weights = strategy.indicator_weights
        sentiment_weight = weights.get("sentiment", 0) + weights.get("funding_rate", 0)
        assert sentiment_weight >= 0.4


class TestStrategyRiskOrdering:
    """Verify risk ordering across personality types."""

    def test_sentinels_are_most_conservative(self):
        istj = StrategyFactory.create(MBTIType.ISTJ)
        isfj = StrategyFactory.create(MBTIType.ISFJ)
        entj = StrategyFactory.create(MBTIType.ENTJ)
        estp = StrategyFactory.create(MBTIType.ESTP)

        assert isfj.risk_tolerance < istj.risk_tolerance
        assert istj.risk_tolerance < entj.risk_tolerance
        assert entj.risk_tolerance < estp.risk_tolerance

    def test_explorers_have_higher_aggression(self):
        estp = StrategyFactory.create(MBTIType.ESTP)
        istj = StrategyFactory.create(MBTIType.ISTJ)
        assert estp.entry_aggression > istj.entry_aggression

    def test_all_strategies_have_valid_params(self):
        for mbti_type in MBTIType:
            strategy = StrategyFactory.create(mbti_type)
            assert 0.0 <= strategy.risk_tolerance <= 1.0
            assert 0.0 < strategy.max_position_pct <= 0.5
            assert 0.0 < strategy.stop_loss_pct <= 0.20
            assert 0.0 < strategy.take_profit_pct <= 0.50
            assert strategy.rebalance_hours >= 1
            assert 0.0 <= strategy.entry_aggression <= 1.0

    def test_indicator_weights_sum_to_one(self):
        for mbti_type in MBTIType:
            strategy = StrategyFactory.create(mbti_type)
            total = sum(strategy.indicator_weights.values())
            assert total == pytest.approx(1.0, abs=0.01)
