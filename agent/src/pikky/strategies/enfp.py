"""
ENFP "The FOMO King" trading strategy.

Momentum-based, buys breakouts aggressively, wide stops, high frequency.
Implements volume spike detection combined with social sentiment scoring.
Gets excited about big moves and jumps in fast. Uses wide stops to
ride the momentum wave but can also panic-sell on reversals.
"""

from __future__ import annotations

import math
import time
from typing import Any

import structlog

from pikky.strategies.base import BaseStrategy

logger = structlog.get_logger(__name__)


class EnfpStrategy(BaseStrategy):
    """
    ENFP - The FOMO King.

    Trading philosophy:
    - If it's moving, get on board NOW.
    - Volume spikes = opportunity. Don't miss the pump.
    - Wide stops to give trades room to breathe.
    - High frequency: many small bets, ride the winners.
    - Emotional: gets euphoric on winners, panics on losers.
    - Loves breakouts, hates slow bleeds.
    """

    def __init__(self) -> None:
        super().__init__(
            name="The FOMO King",
            mbti_type="ENFP",
            risk_tolerance=0.75,
            trade_frequency="high",
            holding_period="short",
            max_positions=5,
            base_position_pct=0.04,
        )
        self._volume_spike_threshold = 2.0
        self._breakout_threshold_pct = 3.0
        self._momentum_threshold = 5.0
        self._min_conviction = 0.45
        self._panic_sell_threshold = -5.0
        self._euphoria_take_profit = 15.0
        self._fomo_cooldown_seconds = 120
        self._last_fomo_time: float = 0.0

    def analyze(self, market_data: Any) -> dict[str, Any]:
        """
        Analyze market for momentum and volume breakouts.

        The FOMO King is looking for explosive moves with volume confirmation.
        Computes momentum scores, volume spike ratios, breakout signals,
        and a simulated "sentiment" score based on price action patterns.
        """
        prices = getattr(market_data, "prices_history", [])
        volumes = getattr(market_data, "volumes_history", [])

        indicators = self._compute_common_indicators(prices, volumes)

        signals: list[tuple[str, float, float]] = []
        fomo_score = 0.0

        volume_spike = indicators.get("volume_spike")
        if volume_spike is not None:
            if volume_spike > self._volume_spike_threshold * 2:
                signals.append(("mega_volume_spike", 1.0, 3.0))
                fomo_score += 3.0
            elif volume_spike > self._volume_spike_threshold:
                signals.append(("volume_spike", 0.8, 2.5))
                fomo_score += 2.0
            elif volume_spike > 1.5:
                signals.append(("volume_above_avg", 0.4, 1.5))
                fomo_score += 0.5
            elif volume_spike < 0.5:
                signals.append(("volume_dead", -0.3, 1.0))
                fomo_score -= 1.0

        momentum = indicators.get("momentum_10")
        if momentum is not None:
            if momentum > self._momentum_threshold * 2:
                signals.append(("mega_momentum", 1.0, 2.5))
                fomo_score += 2.5
            elif momentum > self._momentum_threshold:
                signals.append(("strong_momentum", 0.7, 2.0))
                fomo_score += 1.5
            elif momentum > 2:
                signals.append(("mild_momentum", 0.3, 1.0))
                fomo_score += 0.5
            elif momentum < -self._momentum_threshold:
                signals.append(("momentum_dump", -0.8, 2.0))
                fomo_score -= 2.0

        bb = indicators.get("bollinger")
        if bb is not None:
            current = indicators["price_current"]
            if current > bb["upper"]:
                breakout_strength = (current - bb["upper"]) / bb["std_dev"] if bb["std_dev"] > 0 else 0
                if breakout_strength > 1.0:
                    signals.append(("strong_breakout", 0.9, 2.5))
                    fomo_score += 2.0
                else:
                    signals.append(("breakout", 0.6, 2.0))
                    fomo_score += 1.0
            elif current < bb["lower"]:
                signals.append(("breakdown", -0.5, 1.5))
                fomo_score -= 0.5

            if bb["bandwidth"] > 0.1:
                signals.append(("high_bandwidth", 0.3, 0.5))

        rsi = indicators.get("rsi_14")
        if rsi is not None:
            if rsi > 70:
                signals.append(("rsi_fomo_zone", 0.4, 1.0))
                fomo_score += 0.5
            elif rsi > 80:
                signals.append(("rsi_euphoria", 0.2, 0.5))
            elif rsi < 30:
                signals.append(("rsi_fear", -0.3, 1.0))
                fomo_score -= 0.5

        sentiment_score = self._calculate_sentiment_proxy(prices)
        if sentiment_score > 0.5:
            signals.append(("sentiment_bullish", sentiment_score, 1.5))
            fomo_score += sentiment_score
        elif sentiment_score < -0.5:
            signals.append(("sentiment_bearish", sentiment_score, 1.5))
            fomo_score += sentiment_score

        ema_12 = indicators.get("ema_12")
        ema_26 = indicators.get("ema_26")
        if ema_12 is not None and ema_26 is not None:
            if ema_12 > ema_26:
                spread = (ema_12 - ema_26) / ema_26 if ema_26 > 0 else 0
                if spread > 0.02:
                    signals.append(("strong_trend", 0.7, 1.5))
                    fomo_score += 1.0
                else:
                    signals.append(("mild_uptrend", 0.3, 1.0))
            else:
                signals.append(("downtrend", -0.4, 1.0))

        conviction = self._calculate_conviction(signals)

        max_fomo = 10.0
        fomo_normalized = max(0, min(fomo_score / max_fomo, 1.0))

        blended_conviction = conviction * 0.6 + fomo_normalized * 0.4

        analysis = {
            **indicators,
            "signals": signals,
            "conviction": blended_conviction,
            "fomo_score": fomo_score,
            "fomo_normalized": fomo_normalized,
            "sentiment": sentiment_score,
            "is_breakout": any(s[0] in ("breakout", "strong_breakout") for s in signals),
            "is_volume_spike": (volume_spike or 0) > self._volume_spike_threshold,
            "strategy": "ENFP_FOMOKing",
        }

        if blended_conviction > 0.6:
            logger.info(
                "enfp_fomo_triggered",
                conviction=f"{blended_conviction:.2f}",
                fomo_score=f"{fomo_score:.1f}",
                token=getattr(market_data, "symbol", "?"),
            )

        return analysis

    def should_enter(self, analysis: dict[str, Any], market_data: Any) -> bool:
        """
        The FOMO King enters when momentum and volume align.
        Lower conviction threshold than other strategies -- ENFP doesn't
        wait for perfect setups.
        """
        conviction = analysis.get("conviction", 0)
        if conviction < self._min_conviction:
            return False

        now = time.time()
        if now - self._last_fomo_time < self._fomo_cooldown_seconds:
            return False

        is_breakout = analysis.get("is_breakout", False)
        is_volume = analysis.get("is_volume_spike", False)
        fomo_score = analysis.get("fomo_score", 0)

        if is_breakout and is_volume:
            self._last_fomo_time = now
            self._trade_count += 1
            logger.info(
                "enfp_full_fomo_entry",
                conviction=conviction,
                fomo=fomo_score,
            )
            return True

        if fomo_score > 4.0 and conviction > 0.55:
            self._last_fomo_time = now
            self._trade_count += 1
            return True

        if is_breakout and conviction > 0.6:
            self._last_fomo_time = now
            self._trade_count += 1
            return True

        if is_volume and conviction > 0.6:
            self._last_fomo_time = now
            self._trade_count += 1
            return True

        return False

    def should_exit(
        self,
        analysis: dict[str, Any],
        market_data: Any,
        position: Any,
    ) -> bool:
        """
        ENFP exits emotionally:
        - Panic sells on sharp drops
        - Takes euphoric profits on big pumps
        - Gets bored if nothing is happening
        """
        pnl_pct = getattr(position, "unrealized_pnl_pct", 0)

        if pnl_pct < self._panic_sell_threshold:
            logger.info("enfp_panic_sell", pnl_pct=pnl_pct)
            return True

        if pnl_pct > self._euphoria_take_profit:
            logger.info("enfp_euphoria_exit", pnl_pct=pnl_pct)
            return True

        momentum = analysis.get("momentum_10")
        if momentum is not None and momentum < -8 and pnl_pct < 0:
            return True

        if pnl_pct > 5:
            conviction = analysis.get("conviction", 0.5)
            if conviction < 0.3:
                return True

        hold_seconds = getattr(position, "holding_duration_seconds", 0)
        if hold_seconds > 3600 and abs(pnl_pct) < 2:
            logger.info("enfp_bored_exit", hold_time=hold_seconds, pnl_pct=pnl_pct)
            return True

        fomo_score = analysis.get("fomo_score", 0)
        if fomo_score < -3 and pnl_pct < 0:
            return True

        return False

    def get_risk_params(self) -> dict[str, Any]:
        """ENFP uses wide stops to let momentum play out."""
        return {
            "stop_loss_pct": 0.08,
            "take_profit_pct": 0.20,
            "slippage_bps": 100,
            "max_positions": self.max_positions,
            "trailing_stop": True,
        }

    def calculate_position_size(
        self,
        analysis: dict[str, Any],
        portfolio_balance_sol: float,
        current_exposure_sol: float,
    ) -> float:
        """
        ENFP sizes based on FOMO intensity.
        Bigger FOMO = bigger position (within limits).
        """
        available = portfolio_balance_sol - current_exposure_sol
        if available <= 0:
            return 0.0

        fomo_normalized = analysis.get("fomo_normalized", 0.5)
        conviction = analysis.get("conviction", 0.5)

        excitement_factor = 0.5 + fomo_normalized * 0.5
        size = self.base_position_pct * portfolio_balance_sol * conviction * excitement_factor

        max_allowed = available * 0.3
        size = min(size, max_allowed)

        return round(max(size, 0.0), 4)

    def _calculate_sentiment_proxy(self, prices: list[float]) -> float:
        """
        Calculate a sentiment proxy from price action patterns.

        Looks at the distribution of up vs down candles, acceleration
        of price movement, and consecutive direction streaks.

        Returns a score from -1 (extreme fear) to 1 (extreme greed).
        """
        if len(prices) < 10:
            return 0.0

        recent = prices[-20:] if len(prices) >= 20 else prices
        changes = [recent[i] - recent[i - 1] for i in range(1, len(recent))]

        if not changes:
            return 0.0

        up_count = sum(1 for c in changes if c > 0)
        down_count = sum(1 for c in changes if c < 0)
        total = up_count + down_count
        if total == 0:
            return 0.0
        ratio_score = (up_count - down_count) / total

        streak = 0
        direction = 1 if changes[-1] > 0 else -1
        for c in reversed(changes):
            if (c > 0 and direction > 0) or (c < 0 and direction < 0):
                streak += 1
            else:
                break
        streak_score = min(streak / 5, 1.0) * direction

        if len(changes) >= 5:
            recent_avg = sum(abs(c) for c in changes[-3:]) / 3
            older_avg = sum(abs(c) for c in changes[-6:-3]) / 3 if len(changes) >= 6 else recent_avg
            if older_avg > 0:
                acceleration = (recent_avg - older_avg) / older_avg
                accel_score = max(-1, min(1, acceleration))
            else:
                accel_score = 0.0
        else:
            accel_score = 0.0

        sentiment = ratio_score * 0.4 + streak_score * 0.35 + accel_score * 0.25
        return max(-1.0, min(1.0, sentiment))
