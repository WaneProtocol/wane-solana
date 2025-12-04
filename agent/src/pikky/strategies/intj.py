"""
INTJ "The Sniper" trading strategy.

High conviction, few trades, tight entries, mathematical stop-losses, no emotion.
Implements technical analysis with RSI + MACD convergence. Waits for multiple
confirmations before entering. Uses precise risk/reward ratios and never
chases trades.
"""

from __future__ import annotations

from typing import Any

import structlog

from pikky.strategies.base import BaseStrategy

logger = structlog.get_logger(__name__)


class IntjStrategy(BaseStrategy):
    """
    INTJ - The Sniper.

    Trading philosophy:
    - Patience over frequency. Wait for the perfect setup.
    - Require RSI + MACD + trend alignment before entry.
    - Tight stop-losses with at least 3:1 reward/risk.
    - Never average down. Cut losses immediately.
    - Position size inversely proportional to volatility.
    """

    def __init__(self) -> None:
        super().__init__(
            name="The Sniper",
            mbti_type="INTJ",
            risk_tolerance=0.35,
            trade_frequency="low",
            holding_period="medium",
            max_positions=2,
            base_position_pct=0.08,
        )
        self._rsi_oversold = 30.0
        self._rsi_overbought = 70.0
        self._min_conviction = 0.70
        self._required_confirmations = 3
        self._reward_risk_ratio = 3.0
