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
