"""
Strategy Registry for PIKKY.

Maps all 16 MBTI types to their trading strategy implementations.
Each type gets a configured strategy instance with personality-appropriate
default parameters.
"""

from __future__ import annotations

from typing import Optional

import structlog

from pikky.mbti.types import MbtiType
from pikky.strategies.base import BaseStrategy
from pikky.strategies.enfp import EnfpStrategy
from pikky.strategies.entp import EntpStrategy
from pikky.strategies.intj import IntjStrategy
from pikky.strategies.istj import IstjStrategy

logger = structlog.get_logger(__name__)


class _AdaptedStrategy(BaseStrategy):
    """
    Adapter strategy for MBTI types that don't have a dedicated implementation.

    Wraps one of the four core strategies and adjusts parameters to match
    the target MBTI type's personality profile.
    """

    def __init__(
        self,
        base_strategy: BaseStrategy,
        target_mbti: str,
        name: str,
        risk_tolerance: float,
        trade_frequency: str,
        holding_period: str,
        max_positions: int,
        base_position_pct: float,
    ) -> None:
        super().__init__(
            name=name,
            mbti_type=target_mbti,
            risk_tolerance=risk_tolerance,
            trade_frequency=trade_frequency,
            holding_period=holding_period,
            max_positions=max_positions,
            base_position_pct=base_position_pct,
        )
        self._base = base_strategy

    def analyze(self, market_data: object) -> dict:
        """Delegate analysis to the base strategy."""
        result = self._base.analyze(market_data)
        result["strategy"] = f"{self.mbti_type}_adapted"
        return result

    def should_enter(self, analysis: dict, market_data: object) -> bool:
        """Apply this type's conviction threshold to the base strategy's logic."""
        conviction = analysis.get("conviction", 0)
        threshold = 0.5 + (1.0 - self.risk_tolerance) * 0.3
        if conviction < threshold:
            return False
        return self._base.should_enter(analysis, market_data)
