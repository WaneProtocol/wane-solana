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

    def analyze(self, market_data: Any) -> dict[str, Any]:
        """
        Run deep technical analysis looking for high-probability setups.

        The Sniper requires convergence of multiple indicators before
        considering a trade. Computes RSI, MACD, Bollinger Bands,
        trend direction, and momentum alignment.
        """
        prices = getattr(market_data, "prices_history", [])
        volumes = getattr(market_data, "volumes_history", [])

        indicators = self._compute_common_indicators(prices, volumes)

        signals: list[tuple[str, float, float]] = []
        confirmations = 0

        rsi = indicators.get("rsi_14")
        if rsi is not None:
            if rsi < self._rsi_oversold:
                signals.append(("rsi_oversold", 0.8, 2.0))
                confirmations += 1
            elif rsi < 40:
                signals.append(("rsi_low", 0.4, 1.5))
            elif rsi > self._rsi_overbought:
                signals.append(("rsi_overbought", -0.8, 2.0))
            elif rsi > 60:
                signals.append(("rsi_high", -0.3, 1.0))
            else:
                signals.append(("rsi_neutral", 0.0, 0.5))

        macd = indicators.get("macd")
        if macd is not None:
            histogram = macd["histogram"]
            macd_val = macd["macd"]

            if histogram > 0 and macd_val < 0:
                signals.append(("macd_bullish_cross", 0.9, 2.5))
                confirmations += 1
            elif histogram > 0:
                signals.append(("macd_bullish", 0.5, 1.5))
            elif histogram < 0 and macd_val > 0:
                signals.append(("macd_bearish_cross", -0.9, 2.5))
            elif histogram < 0:
                signals.append(("macd_bearish", -0.5, 1.5))

        bb = indicators.get("bollinger")
        if bb is not None:
            current_price = indicators["price_current"]
            if current_price <= bb["lower"]:
                signals.append(("bb_lower_touch", 0.7, 1.8))
                confirmations += 1
            elif current_price >= bb["upper"]:
                signals.append(("bb_upper_touch", -0.7, 1.8))
            else:
                position_in_band = (current_price - bb["lower"]) / (
                    bb["upper"] - bb["lower"]
                ) if bb["upper"] != bb["lower"] else 0.5
                if position_in_band < 0.3:
                    signals.append(("bb_lower_zone", 0.4, 1.0))
                elif position_in_band > 0.7:
                    signals.append(("bb_upper_zone", -0.4, 1.0))

        sma_20 = indicators.get("sma_20")
        sma_50 = indicators.get("sma_50")
        if sma_20 is not None and sma_50 is not None:
            if sma_20 > sma_50:
                signals.append(("trend_bullish", 0.6, 1.5))
                confirmations += 1
            else:
                signals.append(("trend_bearish", -0.6, 1.5))

        momentum = indicators.get("momentum_10")
        if momentum is not None:
            if momentum < -5:
                signals.append(("momentum_reversal_candidate", 0.3, 1.0))
            elif momentum > 10:
                signals.append(("momentum_extended", -0.3, 1.0))

        stoch = indicators.get("stochastic")
        if stoch is not None:
            if stoch["k"] < 20 and stoch["d"] < 20:
                signals.append(("stoch_oversold", 0.6, 1.2))
                confirmations += 1
            elif stoch["k"] > 80 and stoch["d"] > 80:
                signals.append(("stoch_overbought", -0.6, 1.2))

        conviction = self._calculate_conviction(signals)
        volatility = indicators.get("volatility", 0.5)

        analysis = {
            **indicators,
            "signals": signals,
            "conviction": conviction,
            "confirmations": confirmations,
            "entry_quality": "sniper" if confirmations >= self._required_confirmations else "wait",
            "volatility": volatility,
            "strategy": "INTJ_Sniper",
        }

        if conviction > self._min_conviction and confirmations >= self._required_confirmations:
            logger.info(
                "intj_high_conviction_signal",
                conviction=f"{conviction:.2f}",
                confirmations=confirmations,
                rsi=rsi,
                token=getattr(market_data, "symbol", "?"),
            )

        return analysis

    def should_enter(self, analysis: dict[str, Any], market_data: Any) -> bool:
        """
        The Sniper only enters when conviction is extremely high
        and multiple indicators confirm the setup.
        """
        conviction = analysis.get("conviction", 0)
        confirmations = analysis.get("confirmations", 0)

        if conviction < self._min_conviction:
            return False

        if confirmations < self._required_confirmations:
            return False

        rsi = analysis.get("rsi_14")
        if rsi is not None and rsi > 65:
            return False

        volatility = analysis.get("volatility", 0.5)
        if volatility > 1.5:
            return False

        self._signal_count += 1
        logger.info(
            "intj_entry_signal",
            conviction=conviction,
            confirmations=confirmations,
            signal_num=self._signal_count,
        )
        return True

    def should_exit(
        self,
        analysis: dict[str, Any],
        market_data: Any,
        position: Any,
    ) -> bool:
        """
        Exit when technical indicators show the trade thesis is invalidated.
        The Sniper doesn't hope -- if the math says exit, exit immediately.
        """
        pnl_pct = getattr(position, "unrealized_pnl_pct", 0)

        if pnl_pct < -3.0:
            return True

        rsi = analysis.get("rsi_14")
        if rsi is not None and rsi > 80 and pnl_pct > 5:
            logger.info("intj_exit_overbought", rsi=rsi, pnl_pct=pnl_pct)
            return True

        macd = analysis.get("macd")
        if macd is not None and pnl_pct > 0:
            if macd["histogram"] < 0 and macd["macd"] > 0:
                logger.info("intj_exit_macd_cross", pnl_pct=pnl_pct)
                return True

        hold_seconds = getattr(position, "holding_duration_seconds", 0)
        if hold_seconds > 7200 and pnl_pct < 2:
            return True

        conviction = analysis.get("conviction", 0.5)
        if conviction < 0.3 and pnl_pct > 0:
            return True

        return False

    def get_risk_params(self) -> dict[str, Any]:
        """INTJ uses tight stops and high reward/risk ratio."""
        return {
            "stop_loss_pct": 0.03,
            "take_profit_pct": 0.03 * self._reward_risk_ratio,
            "slippage_bps": 30,
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
        The Sniper sizes positions inversely to volatility.
        Higher conviction = larger position, but always capped.
        """
        available = portfolio_balance_sol - current_exposure_sol
        if available <= 0:
            return 0.0

        conviction = analysis.get("conviction", 0.5)
        volatility = analysis.get("volatility", 0.5)

        vol_scalar = 0.3 / max(volatility, 0.1)
        vol_scalar = min(vol_scalar, 2.0)

        size = self.base_position_pct * portfolio_balance_sol * conviction * vol_scalar

        max_allowed = available * 0.4
        size = min(size, max_allowed)

        return round(max(size, 0.0), 4)
