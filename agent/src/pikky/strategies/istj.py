"""
ISTJ "The DCA Machine" trading strategy.

Time-weighted Dollar Cost Averaging. Ignores price action entirely.
Buys at fixed intervals with fixed amounts. Never deviates from the plan.
Pure accumulation logic with no emotional component.
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from pikky.strategies.base import BaseStrategy

logger = structlog.get_logger(__name__)


class IstjStrategy(BaseStrategy):
    """
    ISTJ - The DCA Machine.

    Trading philosophy:
    - Time in market > timing the market.
    - Buy on schedule. Period.
    - Ignore noise, ignore sentiment, ignore FOMO.
    - Fixed position sizes. No conviction scaling.
    - Only exit when the full accumulation target is reached
      or the session expires.
    - Prefers large-cap, high-liquidity tokens only.
    """

    def __init__(self) -> None:
        super().__init__(
            name="The DCA Machine",
            mbti_type="ISTJ",
            risk_tolerance=0.15,
            trade_frequency="medium",
            holding_period="long",
            max_positions=3,
            base_position_pct=0.03,
        )
        self._dca_interval_seconds = 300
        self._last_dca_time: dict[str, float] = {}
        self._dca_count: dict[str, int] = {}
        self._max_dca_rounds: int = 20
        self._min_liquidity_usd = 50000.0
        self._preferred_tokens: set[str] = {
            "So11111111111111111111111111111111111111112",
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
            "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        }

    def analyze(self, market_data: Any) -> dict[str, Any]:
        """
        The DCA Machine barely analyzes. It checks:
        1. Is the token liquid enough?
        2. Is it time for the next DCA buy?
        3. Have we exceeded the max DCA rounds?

        Technical indicators are computed but only for reporting,
        not for decision-making.
        """
        prices = getattr(market_data, "prices_history", [])
        volumes = getattr(market_data, "volumes_history", [])
        mint = getattr(market_data, "mint", "")
        liquidity = getattr(market_data, "liquidity_usd", 0)

        indicators = self._compute_common_indicators(prices, volumes)

        now = time.time()
        last_dca = self._last_dca_time.get(mint, 0)
        time_since_last = now - last_dca
        is_dca_time = time_since_last >= self._dca_interval_seconds or last_dca == 0

        rounds_completed = self._dca_count.get(mint, 0)
        rounds_remaining = self._max_dca_rounds - rounds_completed

        is_eligible = (
            liquidity >= self._min_liquidity_usd
            and rounds_remaining > 0
        )

        is_preferred = mint in self._preferred_tokens

        cost_basis = self._compute_average_cost(prices, rounds_completed)

        analysis = {
            **indicators,
            "conviction": 0.5,
            "is_dca_time": is_dca_time,
            "is_eligible": is_eligible,
            "is_preferred": is_preferred,
            "time_since_last_dca": time_since_last,
            "rounds_completed": rounds_completed,
            "rounds_remaining": rounds_remaining,
            "cost_basis": cost_basis,
            "liquidity_usd": liquidity,
            "strategy": "ISTJ_DCAMachine",
        }

        return analysis
