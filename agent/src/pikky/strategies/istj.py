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

    def should_enter(self, analysis: dict[str, Any], market_data: Any) -> bool:
        """
        The DCA Machine enters based purely on schedule.
        No technical analysis needed. If it's time, buy.
        """
        if not analysis.get("is_eligible", False):
            return False

        if not analysis.get("is_dca_time", False):
            return False

        mint = getattr(market_data, "mint", "")

        self._last_dca_time[mint] = time.time()
        if mint not in self._dca_count:
            self._dca_count[mint] = 0
        self._dca_count[mint] += 1

        self._trade_count += 1

        logger.info(
            "istj_dca_buy",
            token=getattr(market_data, "symbol", "?"),
            round_num=self._dca_count[mint],
            total_rounds=self._max_dca_rounds,
        )

        return True

    def should_exit(
        self,
        analysis: dict[str, Any],
        market_data: Any,
        position: Any,
    ) -> bool:
        """
        The DCA Machine almost never exits voluntarily.
        Only exits if:
        1. All DCA rounds are completed AND position is profitable
        2. Position has been held for a very long time (session-based exit)
        3. Emergency: extreme loss beyond tolerance
        """
        pnl_pct = getattr(position, "unrealized_pnl_pct", 0)
        mint = getattr(position, "token_mint", "")
        hold_seconds = getattr(position, "holding_duration_seconds", 0)

        rounds_completed = self._dca_count.get(mint, 0)
        if rounds_completed >= self._max_dca_rounds and pnl_pct > 5:
            logger.info(
                "istj_accumulation_complete",
                rounds=rounds_completed,
                pnl_pct=pnl_pct,
            )
            return True

        if pnl_pct < -15:
            logger.warning(
                "istj_emergency_exit",
                pnl_pct=pnl_pct,
                mint=mint[:8],
            )
            return True

        if hold_seconds > 14400 and pnl_pct > 2:
            return True

        return False

    def get_risk_params(self) -> dict[str, Any]:
        """ISTJ uses very conservative risk parameters."""
        return {
            "stop_loss_pct": 0.15,
            "take_profit_pct": 0.50,
            "slippage_bps": 30,
            "max_positions": self.max_positions,
            "trailing_stop": False,
        }

    def calculate_position_size(
        self,
        analysis: dict[str, Any],
        portfolio_balance_sol: float,
        current_exposure_sol: float,
    ) -> float:
        """
        ISTJ uses completely fixed position sizes.
        No conviction scaling, no volatility adjustment.
        Every DCA buy is the same amount.
        """
        available = portfolio_balance_sol - current_exposure_sol
        if available <= 0:
            return 0.0

        fixed_size = self.base_position_pct * portfolio_balance_sol

        max_allowed = available * 0.2
        fixed_size = min(fixed_size, max_allowed)

        return round(max(fixed_size, 0.0), 4)

    def _compute_average_cost(
        self,
        prices: list[float],
        rounds_completed: int,
    ) -> float:
        """
        Estimate average cost basis from price history and DCA rounds.

        Since we don't store actual entry prices per round, we approximate
        by averaging the last N prices where N = rounds_completed.
        """
        if rounds_completed == 0 or not prices:
            return prices[-1] if prices else 0.0

        sample_count = min(rounds_completed, len(prices))
        if sample_count == 0:
            return prices[-1]

        step = max(1, len(prices) // sample_count)
        sampled_prices = [prices[i] for i in range(0, len(prices), step)][:sample_count]

        if not sampled_prices:
            return prices[-1]

        return sum(sampled_prices) / len(sampled_prices)

    def reset_dca_state(self, mint: Optional[str] = None) -> None:
        """
        Reset DCA tracking state.

        Args:
            mint: Specific mint to reset, or None to reset all.
        """
        if mint:
            self._last_dca_time.pop(mint, None)
            self._dca_count.pop(mint, None)
        else:
            self._last_dca_time.clear()
            self._dca_count.clear()

        logger.info("istj_dca_state_reset", mint=mint or "all")

    def get_dca_status(self) -> dict[str, Any]:
        """Get current DCA status for all tokens."""
        status: dict[str, Any] = {}
        for mint, count in self._dca_count.items():
            last_time = self._last_dca_time.get(mint, 0)
            status[mint] = {
                "rounds_completed": count,
                "rounds_remaining": self._max_dca_rounds - count,
                "last_dca_time": last_time,
                "next_dca_in": max(
                    0, self._dca_interval_seconds - (time.time() - last_time)
                ),
                "is_complete": count >= self._max_dca_rounds,
            }
        return status
