"""
ENTP "The Degen" trading strategy.

Leveraged positions, contrarian plays, high risk tolerance,
multiple concurrent positions. Implements mean reversion combined
with volatility breakout detection. Thrives in chaos and actively
seeks out volatile, high-risk setups.
"""

from __future__ import annotations

import math
import time
from typing import Any

import structlog

from pikky.strategies.base import BaseStrategy

logger = structlog.get_logger(__name__)


class EntpStrategy(BaseStrategy):
    """
    ENTP - The Degen.

    Trading philosophy:
    - High risk, high reward. Fortune favors the bold.
    - Contrarian: buy the blood, short the euphoria.
    - Mean reversion on oversold tokens with catalyst potential.
    - Volatility breakout: ride explosive moves.
    - Multiple concurrent positions to diversify degen risk.
    - Size up on highest-conviction setups.
    - Embraces drawdowns as "part of the game."
    """

    def __init__(self) -> None:
        super().__init__(
            name="The Degen",
            mbti_type="ENTP",
            risk_tolerance=0.90,
            trade_frequency="high",
            holding_period="short",
            max_positions=8,
            base_position_pct=0.06,
        )
        self._mean_reversion_threshold = 2.0
        self._volatility_breakout_threshold = 1.5
        self._rsi_extreme_low = 20.0
        self._rsi_extreme_high = 85.0
        self._min_conviction = 0.40
        self._contrarian_bonus = 0.3
        self._max_loss_tolerance = -12.0
        self._quick_profit_target = 8.0
        self._last_trade_times: dict[str, float] = {}
        self._min_trade_interval = 60

    def analyze(self, market_data: Any) -> dict[str, Any]:
        """
        Look for mean reversion setups and volatility breakouts.

        The Degen scans for:
        1. Oversold tokens with volume returning (mean reversion)
        2. Volatile tokens breaking out of Bollinger Bands
        3. RSI extremes for contrarian entries
        4. Momentum divergence (price falling, momentum stabilizing)
        """
        prices = getattr(market_data, "prices_history", [])
        volumes = getattr(market_data, "volumes_history", [])

        indicators = self._compute_common_indicators(prices, volumes)

        signals: list[tuple[str, float, float]] = []
        degen_score = 0.0

        mean_rev = self._detect_mean_reversion(prices, indicators)
        if mean_rev["is_oversold"]:
            signals.append(("mean_rev_oversold", 0.9, 3.0))
            degen_score += 3.0
        if mean_rev["is_overbought"]:
            signals.append(("mean_rev_overbought_contrarian", 0.4, 1.0))
            degen_score += 0.5
        if mean_rev["z_score"] is not None:
            z = mean_rev["z_score"]
            if z < -self._mean_reversion_threshold:
                signals.append(("extreme_z_score", 0.8, 2.5))
                degen_score += 2.0

        vol_break = self._detect_volatility_breakout(prices, indicators)
        if vol_break["breakout_up"]:
            signals.append(("vol_breakout_up", 0.85, 2.5))
            degen_score += 2.5
        if vol_break["breakout_down"]:
            signals.append(("vol_breakout_down_contrarian", 0.6, 2.0))
            degen_score += 1.5
        if vol_break["squeeze_release"]:
            signals.append(("squeeze_release", 0.7, 2.0))
            degen_score += 1.5

        rsi = indicators.get("rsi_14")
        if rsi is not None:
            if rsi < self._rsi_extreme_low:
                signals.append(("rsi_extreme_oversold", 0.9, 2.0))
                degen_score += 2.0
            elif rsi < 30:
                signals.append(("rsi_oversold", 0.6, 1.5))
                degen_score += 1.0
            elif rsi > self._rsi_extreme_high:
                signals.append(("rsi_contrarian_short_idea", -0.3, 1.0))
            elif rsi > 70:
                signals.append(("rsi_overbought", -0.2, 0.5))

        divergence = self._detect_momentum_divergence(prices, indicators)
        if divergence["bullish_divergence"]:
            signals.append(("bullish_divergence", 0.85, 2.5))
            degen_score += 2.0
        if divergence["bearish_divergence"]:
            signals.append(("bearish_divergence", -0.4, 1.0))

        volume_spike = indicators.get("volume_spike")
        if volume_spike is not None:
            if volume_spike > 3.0:
                signals.append(("massive_volume", 0.7, 2.0))
                degen_score += 1.5
            elif volume_spike > 2.0:
                signals.append(("high_volume", 0.5, 1.5))
                degen_score += 0.5

        volatility = indicators.get("volatility", 0.5)
        if volatility > 1.0:
            signals.append(("high_vol_opportunity", 0.4, 1.0))
            degen_score += 0.5

        conviction = self._calculate_conviction(signals)

        max_degen = 12.0
        degen_normalized = max(0, min(degen_score / max_degen, 1.0))
        blended = conviction * 0.5 + degen_normalized * 0.5

        analysis = {
            **indicators,
            "signals": signals,
            "conviction": blended,
            "degen_score": degen_score,
            "degen_normalized": degen_normalized,
            "mean_reversion": mean_rev,
            "volatility_breakout": vol_break,
            "divergence": divergence,
            "is_contrarian_setup": mean_rev["is_oversold"] or (
                rsi is not None and rsi < self._rsi_extreme_low
            ),
            "is_volatility_play": vol_break["breakout_up"] or vol_break["squeeze_release"],
            "strategy": "ENTP_Degen",
        }

        if blended > 0.6:
            logger.info(
                "entp_degen_signal",
                conviction=f"{blended:.2f}",
                degen_score=f"{degen_score:.1f}",
                token=getattr(market_data, "symbol", "?"),
                contrarian=analysis["is_contrarian_setup"],
                vol_play=analysis["is_volatility_play"],
            )

        return analysis
