"""
Base strategy class for PIKKY trading strategies.

Provides the abstract interface and common implementations for all
MBTI-based trading strategies. Includes technical indicator calculations,
position sizing formulas, and shared risk management logic.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


class TechnicalIndicators:
    """
    Technical indicator calculator.

    Computes common indicators from price and volume history arrays.
    All methods are static and operate on plain lists of floats.
    """

    @staticmethod
    def sma(prices: list[float], period: int) -> Optional[float]:
        """
        Calculate Simple Moving Average.

        Args:
            prices: Price history (oldest first).
            period: Number of periods for the average.

        Returns:
            SMA value or None if insufficient data.
        """
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period

    @staticmethod
    def ema(prices: list[float], period: int) -> Optional[float]:
        """
        Calculate Exponential Moving Average.

        Uses the standard smoothing factor 2/(period+1).

        Args:
            prices: Price history (oldest first).
            period: Number of periods.

        Returns:
            EMA value or None if insufficient data.
        """
        if len(prices) < period:
            return None
        multiplier = 2.0 / (period + 1)
        ema_val = sum(prices[:period]) / period
        for price in prices[period:]:
            ema_val = (price - ema_val) * multiplier + ema_val
        return ema_val

    @staticmethod
    def rsi(prices: list[float], period: int = 14) -> Optional[float]:
        """
        Calculate Relative Strength Index.

        Uses the Wilder smoothing method.

        Args:
            prices: Price history (oldest first).
            period: RSI period (default 14).

        Returns:
            RSI value (0-100) or None if insufficient data.
        """
        if len(prices) < period + 1:
            return None

        deltas = [prices[i + 1] - prices[i] for i in range(len(prices) - 1)]

        gains = [d if d > 0 else 0.0 for d in deltas[:period]]
        losses = [-d if d < 0 else 0.0 for d in deltas[:period]]

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        for d in deltas[period:]:
            gain = d if d > 0 else 0.0
            loss = -d if d < 0 else 0.0
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def macd(
        prices: list[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> Optional[dict[str, float]]:
        """
        Calculate MACD (Moving Average Convergence Divergence).

        Args:
            prices: Price history (oldest first).
            fast_period: Fast EMA period.
            slow_period: Slow EMA period.
            signal_period: Signal line EMA period.

        Returns:
            Dict with 'macd', 'signal', and 'histogram' values, or None.
        """
        if len(prices) < slow_period + signal_period:
            return None

        fast_ema = TechnicalIndicators.ema(prices, fast_period)
        slow_ema = TechnicalIndicators.ema(prices, slow_period)

        if fast_ema is None or slow_ema is None:
            return None

        macd_line_values: list[float] = []
        fast_mult = 2.0 / (fast_period + 1)
        slow_mult = 2.0 / (slow_period + 1)

        fast_val = sum(prices[:fast_period]) / fast_period
        slow_val = sum(prices[:slow_period]) / slow_period

        for i in range(slow_period, len(prices)):
            if i >= fast_period:
                fast_val = (prices[i] - fast_val) * fast_mult + fast_val
            slow_val = (prices[i] - slow_val) * slow_mult + slow_val
            macd_line_values.append(fast_val - slow_val)

        if len(macd_line_values) < signal_period:
            return None

        signal_mult = 2.0 / (signal_period + 1)
        signal_val = sum(macd_line_values[:signal_period]) / signal_period
        for val in macd_line_values[signal_period:]:
            signal_val = (val - signal_val) * signal_mult + signal_val

        macd_val = macd_line_values[-1]
        histogram = macd_val - signal_val

        return {
            "macd": macd_val,
            "signal": signal_val,
            "histogram": histogram,
        }

    @staticmethod
    def bollinger_bands(
        prices: list[float],
        period: int = 20,
        num_std: float = 2.0,
    ) -> Optional[dict[str, float]]:
        """
        Calculate Bollinger Bands.

        Args:
            prices: Price history.
            period: SMA period.
            num_std: Number of standard deviations for bands.

        Returns:
            Dict with 'upper', 'middle', 'lower', and 'bandwidth' values.
        """
        if len(prices) < period:
            return None

        window = prices[-period:]
        middle = sum(window) / period
        variance = sum((p - middle) ** 2 for p in window) / period
        std_dev = math.sqrt(variance)

        upper = middle + num_std * std_dev
        lower = middle - num_std * std_dev
        bandwidth = (upper - lower) / middle if middle != 0 else 0

        return {
            "upper": upper,
            "middle": middle,
            "lower": lower,
            "std_dev": std_dev,
            "bandwidth": bandwidth,
        }

    @staticmethod
    def atr(
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int = 14,
    ) -> Optional[float]:
        """
        Calculate Average True Range.

        For price-only data, estimates highs/lows from close prices.

        Args:
            highs: High prices.
            lows: Low prices.
            closes: Close prices.
            period: ATR period.

        Returns:
            ATR value or None.
        """
        n = min(len(highs), len(lows), len(closes))
        if n < period + 1:
            return None

        true_ranges: list[float] = []
        for i in range(1, n):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            true_ranges.append(tr)

        if len(true_ranges) < period:
            return None

        atr_val = sum(true_ranges[:period]) / period
        for tr in true_ranges[period:]:
            atr_val = (atr_val * (period - 1) + tr) / period

        return atr_val

    @staticmethod
    def volume_sma(volumes: list[float], period: int) -> Optional[float]:
        """Calculate volume simple moving average."""
        if len(volumes) < period:
            return None
        return sum(volumes[-period:]) / period

    @staticmethod
    def volume_spike_ratio(volumes: list[float], period: int = 20) -> Optional[float]:
        """
        Calculate the ratio of current volume to its moving average.

        Returns:
            Ratio > 1 means volume is above average. None if insufficient data.
        """
        if len(volumes) < period + 1:
            return None
        avg = sum(volumes[-period - 1:-1]) / period
        if avg == 0:
            return None
        return volumes[-1] / avg

    @staticmethod
    def momentum(prices: list[float], period: int = 10) -> Optional[float]:
        """
        Calculate price momentum (rate of change).

        Returns:
            Percentage change over the period.
        """
        if len(prices) < period + 1:
            return None
        old_price = prices[-period - 1]
        if old_price == 0:
            return None
        return ((prices[-1] - old_price) / old_price) * 100

    @staticmethod
    def stochastic(
        prices: list[float],
        k_period: int = 14,
        d_period: int = 3,
    ) -> Optional[dict[str, float]]:
        """
        Calculate Stochastic Oscillator (%K and %D).

        Args:
            prices: Price history.
            k_period: Lookback for %K.
            d_period: Smoothing for %D.

        Returns:
            Dict with 'k' and 'd' values (0-100).
        """
        if len(prices) < k_period + d_period:
            return None

        k_values: list[float] = []
        for i in range(k_period, len(prices) + 1):
            window = prices[i - k_period:i]
            high = max(window)
            low = min(window)
            if high == low:
                k_values.append(50.0)
            else:
                k_values.append(((prices[i - 1] - low) / (high - low)) * 100)

        if len(k_values) < d_period:
            return None

        d_val = sum(k_values[-d_period:]) / d_period
        return {"k": k_values[-1], "d": d_val}

    @staticmethod
    def estimate_volatility(prices: list[float], period: int = 20) -> Optional[float]:
        """
        Estimate annualized volatility from price history.

        Uses log returns and assumes ~365 periods per year (crypto).

        Returns:
            Annualized volatility as a decimal (e.g., 0.8 = 80%).
        """
        if len(prices) < period + 1:
            return None

        log_returns: list[float] = []
        for i in range(len(prices) - period, len(prices)):
            if prices[i - 1] > 0 and prices[i] > 0:
                log_returns.append(math.log(prices[i] / prices[i - 1]))

        if len(log_returns) < 2:
            return None

        mean_return = sum(log_returns) / len(log_returns)
        variance = sum((r - mean_return) ** 2 for r in log_returns) / (len(log_returns) - 1)
        daily_vol = math.sqrt(variance)

        return daily_vol * math.sqrt(365)


class BaseStrategy(ABC):
    """
    Abstract base class for MBTI trading strategies.

    Subclasses implement the specific trading logic for each personality type.
    The base class provides common technical analysis utilities, position sizing
    formulas, and risk parameter management.
    """

    def __init__(
        self,
        name: str,
        mbti_type: str,
        risk_tolerance: float = 0.5,
        trade_frequency: str = "medium",
        holding_period: str = "medium",
        max_positions: int = 3,
        base_position_pct: float = 0.05,
    ) -> None:
        """
        Initialize the strategy.

        Args:
            name: Human-readable strategy name.
            mbti_type: The MBTI type this strategy represents.
            risk_tolerance: Risk tolerance from 0 (very conservative) to 1 (very aggressive).
            trade_frequency: "low", "medium", or "high".
            holding_period: "short", "medium", or "long".
            max_positions: Maximum concurrent positions.
            base_position_pct: Base position size as percentage of portfolio.
        """
        self.name = name
        self.mbti_type = mbti_type
        self.risk_tolerance = risk_tolerance
        self.trade_frequency = trade_frequency
        self.holding_period = holding_period
        self.max_positions = max_positions
        self.base_position_pct = base_position_pct
        self.indicators = TechnicalIndicators()

        self._trade_count: int = 0
        self._signal_count: int = 0

        logger.info(
            "strategy_initialized",
            name=name,
            mbti=mbti_type,
            risk=risk_tolerance,
            frequency=trade_frequency,
        )

    @abstractmethod
    def analyze(self, market_data: Any) -> dict[str, Any]:
        """
        Analyze market data and produce trading signals.

        Args:
            market_data: MarketData object with price/volume history.

        Returns:
            Dict of analysis results including indicators and signals.
        """
        ...

    @abstractmethod
    def should_enter(self, analysis: dict[str, Any], market_data: Any) -> bool:
        """
        Determine if a new position should be opened.

        Args:
            analysis: Results from analyze().
            market_data: Current market data.

        Returns:
            True if a position should be opened.
        """
        ...

    @abstractmethod
    def should_exit(
        self,
        analysis: dict[str, Any],
        market_data: Any,
        position: Any,
    ) -> bool:
        """
        Determine if an existing position should be closed.

        Args:
            analysis: Results from analyze().
            market_data: Current market data.
            position: The current Position object.

        Returns:
            True if the position should be closed.
        """
        ...

    def calculate_position_size(
        self,
        analysis: dict[str, Any],
        portfolio_balance_sol: float,
        current_exposure_sol: float,
    ) -> float:
        """
        Calculate the position size in SOL.

        Uses a conviction-weighted Kelly-inspired formula:
        size = base_pct * portfolio * conviction * risk_factor

        Args:
            analysis: Strategy analysis results (should include 'conviction').
            portfolio_balance_sol: Total portfolio balance in SOL.
            current_exposure_sol: Current total exposure in SOL.

        Returns:
            Position size in SOL.
        """
        available = portfolio_balance_sol - current_exposure_sol
        if available <= 0:
            return 0.0

        conviction = analysis.get("conviction", 0.5)
        conviction = max(0.1, min(1.0, conviction))

        volatility = analysis.get("volatility", 0.5)
        vol_adjustment = 1.0 / (1.0 + volatility) if volatility > 0 else 1.0

        risk_factor = 0.5 + (self.risk_tolerance * 0.5)

        raw_size = (
            self.base_position_pct
            * portfolio_balance_sol
            * conviction
            * vol_adjustment
            * risk_factor
        )

        max_size = available * 0.5
        position_size = min(raw_size, max_size)
        position_size = max(position_size, 0.0)

        return round(position_size, 4)

    def get_risk_params(self) -> dict[str, Any]:
        """
        Get risk parameters calibrated to this strategy's personality.

        Returns:
            Dict with stop_loss_pct, take_profit_pct, slippage_bps, etc.
        """
        base_stop = 0.05 + (1.0 - self.risk_tolerance) * 0.10
        base_tp = 0.10 + self.risk_tolerance * 0.40
        slippage = int(30 + self.risk_tolerance * 100)

        return {
            "stop_loss_pct": round(base_stop, 3),
            "take_profit_pct": round(base_tp, 3),
            "slippage_bps": slippage,
            "max_positions": self.max_positions,
            "trailing_stop": self.risk_tolerance > 0.3,
        }

    def _compute_common_indicators(
        self,
        prices: list[float],
        volumes: Optional[list[float]] = None,
    ) -> dict[str, Any]:
        """
        Compute a standard set of technical indicators.

        Returns a dict with all computed indicator values. Missing indicators
        (due to insufficient data) are set to None.
        """
        result: dict[str, Any] = {
            "price_current": prices[-1] if prices else 0.0,
            "price_count": len(prices),
        }

        result["sma_10"] = self.indicators.sma(prices, 10)
        result["sma_20"] = self.indicators.sma(prices, 20)
        result["sma_50"] = self.indicators.sma(prices, 50)
        result["ema_12"] = self.indicators.ema(prices, 12)
        result["ema_26"] = self.indicators.ema(prices, 26)
        result["rsi_14"] = self.indicators.rsi(prices, 14)
        result["macd"] = self.indicators.macd(prices)
        result["bollinger"] = self.indicators.bollinger_bands(prices)
        result["momentum_10"] = self.indicators.momentum(prices, 10)
        result["stochastic"] = self.indicators.stochastic(prices)
        result["volatility"] = self.indicators.estimate_volatility(prices) or 0.5

        if volumes:
            result["volume_sma_20"] = self.indicators.volume_sma(volumes, 20)
            result["volume_spike"] = self.indicators.volume_spike_ratio(volumes, 20)
        else:
            result["volume_sma_20"] = None
            result["volume_spike"] = None

        current = prices[-1] if prices else 0
        sma_20 = result.get("sma_20")
        if sma_20 and sma_20 > 0:
            result["price_vs_sma20"] = (current - sma_20) / sma_20
        else:
            result["price_vs_sma20"] = 0.0

        return result

    def _calculate_conviction(
        self,
        signals: list[tuple[str, float, float]],
    ) -> float:
        """
        Calculate overall conviction from weighted signals.

        Args:
            signals: List of (name, value, weight) tuples.
                value should be -1 to 1 (bearish to bullish).
                weight is the importance factor.

        Returns:
            Conviction score from 0 to 1.
        """
        if not signals:
            return 0.0

        total_weight = sum(abs(w) for _, _, w in signals)
        if total_weight == 0:
            return 0.0

        weighted_sum = sum(v * w for _, v, w in signals)
        raw_conviction = weighted_sum / total_weight

        conviction = (raw_conviction + 1) / 2
        return max(0.0, min(1.0, conviction))
