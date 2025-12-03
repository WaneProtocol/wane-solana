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