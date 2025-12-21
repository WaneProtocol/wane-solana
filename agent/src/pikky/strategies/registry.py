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

    def should_exit(self, analysis: dict, market_data: object, position: object) -> bool:
        """Delegate exit logic with adjusted loss tolerance."""
        pnl_pct = getattr(position, "unrealized_pnl_pct", 0)
        max_loss = -3.0 - (self.risk_tolerance * 10.0)
        if pnl_pct < max_loss:
            return True
        return self._base.should_exit(analysis, market_data, position)


# Default parameters for all 16 MBTI types
_MBTI_PROFILES: dict[str, dict] = {
    "INTJ": {
        "base": "intj",
        "name": "The Sniper",
        "risk_tolerance": 0.35,
        "trade_frequency": "low",
        "holding_period": "medium",
        "max_positions": 2,
        "base_position_pct": 0.08,
    },
    "INTP": {
        "base": "intj",
        "name": "The Quant",
        "risk_tolerance": 0.40,
        "trade_frequency": "low",
        "holding_period": "medium",
        "max_positions": 3,
        "base_position_pct": 0.06,
    },
    "ENTJ": {
        "base": "intj",
        "name": "The Commander",
        "risk_tolerance": 0.55,
        "trade_frequency": "medium",
        "holding_period": "medium",
        "max_positions": 4,
        "base_position_pct": 0.07,
    },
    "ENTP": {
        "base": "entp",
        "name": "The Degen",
        "risk_tolerance": 0.90,
        "trade_frequency": "high",
        "holding_period": "short",
        "max_positions": 8,
        "base_position_pct": 0.06,
    },
    "INFJ": {
        "base": "istj",
        "name": "The Oracle",
        "risk_tolerance": 0.25,
        "trade_frequency": "low",
        "holding_period": "long",
        "max_positions": 2,
        "base_position_pct": 0.04,
    },
    "INFP": {
        "base": "istj",
        "name": "The Dreamer",
        "risk_tolerance": 0.20,
        "trade_frequency": "low",
        "holding_period": "long",
        "max_positions": 2,
        "base_position_pct": 0.03,
    },
    "ENFJ": {
        "base": "enfp",
        "name": "The Influencer",
        "risk_tolerance": 0.50,
        "trade_frequency": "medium",
        "holding_period": "medium",
        "max_positions": 4,
        "base_position_pct": 0.05,
    },
    "ENFP": {
        "base": "enfp",
        "name": "The FOMO King",
        "risk_tolerance": 0.75,
        "trade_frequency": "high",
        "holding_period": "short",
        "max_positions": 5,
        "base_position_pct": 0.04,
    },
    "ISTJ": {
        "base": "istj",
        "name": "The DCA Machine",
        "risk_tolerance": 0.15,
        "trade_frequency": "medium",
        "holding_period": "long",
        "max_positions": 3,
        "base_position_pct": 0.03,
    },
    "ISFJ": {
        "base": "istj",
        "name": "The Guardian",
        "risk_tolerance": 0.10,
        "trade_frequency": "low",
        "holding_period": "long",
        "max_positions": 2,
        "base_position_pct": 0.02,
    },
    "ESTJ": {
        "base": "intj",
        "name": "The Executive",
        "risk_tolerance": 0.45,
        "trade_frequency": "medium",
        "holding_period": "medium",
        "max_positions": 4,
        "base_position_pct": 0.06,
    },
    "ESFJ": {
        "base": "istj",
        "name": "The Provider",
        "risk_tolerance": 0.20,
        "trade_frequency": "medium",
        "holding_period": "long",
        "max_positions": 3,
        "base_position_pct": 0.03,
    },
    "ISTP": {
        "base": "entp",
        "name": "The Mechanic",
        "risk_tolerance": 0.60,
        "trade_frequency": "medium",
        "holding_period": "short",
        "max_positions": 4,
        "base_position_pct": 0.05,
    },
    "ISFP": {
        "base": "enfp",
        "name": "The Artist",
        "risk_tolerance": 0.30,
        "trade_frequency": "low",
        "holding_period": "medium",
        "max_positions": 3,
        "base_position_pct": 0.04,
    },
    "ESTP": {
        "base": "entp",
        "name": "The Hustler",
        "risk_tolerance": 0.85,
        "trade_frequency": "high",
        "holding_period": "short",
        "max_positions": 6,
        "base_position_pct": 0.05,
    },
    "ESFP": {
        "base": "enfp",
        "name": "The Performer",
        "risk_tolerance": 0.65,
        "trade_frequency": "high",
        "holding_period": "short",
        "max_positions": 5,
        "base_position_pct": 0.04,
    },
}


class StrategyRegistry:
    """
    Registry mapping MBTI types to configured strategy instances.

    Maintains a cache of instantiated strategies. The four core strategies
    (INTJ, ENFP, ISTJ, ENTP) are used directly. All other types get an
    adapted version of the closest core strategy with adjusted parameters.
    """

    def __init__(self) -> None:
        self._strategies: dict[str, BaseStrategy] = {}
        self._core_strategies: dict[str, BaseStrategy] = {
            "intj": IntjStrategy(),
            "enfp": EnfpStrategy(),
            "istj": IstjStrategy(),
            "entp": EntpStrategy(),
        }
        self._build_all_strategies()
        logger.info("strategy_registry_initialized", count=len(self._strategies))

    def _build_all_strategies(self) -> None:
        """Pre-build strategy instances for all 16 MBTI types."""
        for mbti_str, profile in _MBTI_PROFILES.items():
            base_key = profile["base"]

            if mbti_str == "INTJ":
                self._strategies[mbti_str] = self._core_strategies["intj"]
            elif mbti_str == "ENFP":
                self._strategies[mbti_str] = self._core_strategies["enfp"]
            elif mbti_str == "ISTJ":
                self._strategies[mbti_str] = self._core_strategies["istj"]
            elif mbti_str == "ENTP":
                self._strategies[mbti_str] = self._core_strategies["entp"]
            else:
                base_strategy = self._core_strategies[base_key]
                adapted = _AdaptedStrategy(
                    base_strategy=base_strategy,
                    target_mbti=mbti_str,
                    name=profile["name"],
                    risk_tolerance=profile["risk_tolerance"],
                    trade_frequency=profile["trade_frequency"],
                    holding_period=profile["holding_period"],
                    max_positions=profile["max_positions"],
                    base_position_pct=profile["base_position_pct"],
                )
                self._strategies[mbti_str] = adapted

    def get_strategy(self, mbti_type: MbtiType) -> Optional[BaseStrategy]:
        """
        Get the strategy instance for an MBTI type.

        Args:
            mbti_type: The MbtiType enum value.

        Returns:
            Configured BaseStrategy instance or None if type is unknown.
        """
        return self._strategies.get(mbti_type.value)

    def get_strategy_by_name(self, mbti_str: str) -> Optional[BaseStrategy]:
        """
        Get strategy by MBTI type string.

        Args:
            mbti_str: Four-letter MBTI code (e.g., "INTJ").

        Returns:
            Configured BaseStrategy instance or None.
        """
        return self._strategies.get(mbti_str.upper())

    def list_strategies(self) -> list[dict]:
        """List all registered strategies with their parameters."""
        result = []
        for mbti_str, strategy in sorted(self._strategies.items()):
            profile = _MBTI_PROFILES.get(mbti_str, {})
            result.append({
                "mbti_type": mbti_str,
                "name": strategy.name,
                "risk_tolerance": strategy.risk_tolerance,
                "trade_frequency": strategy.trade_frequency,
                "holding_period": strategy.holding_period,
                "max_positions": strategy.max_positions,
                "base_position_pct": strategy.base_position_pct,
                "base_strategy": profile.get("base", mbti_str.lower()),
                "risk_params": strategy.get_risk_params(),
            })
        return result

    def get_strategy_info(self, mbti_type: str) -> Optional[dict]:
        """Get detailed information about a specific strategy."""
        strategy = self._strategies.get(mbti_type.upper())
        if strategy is None:
            return None

        profile = _MBTI_PROFILES.get(mbti_type.upper(), {})
        return {
            "mbti_type": mbti_type.upper(),
            "name": strategy.name,
            "class": strategy.__class__.__name__,
            "risk_tolerance": strategy.risk_tolerance,
            "trade_frequency": strategy.trade_frequency,
            "holding_period": strategy.holding_period,
            "max_positions": strategy.max_positions,
            "base_position_pct": strategy.base_position_pct,
            "base_strategy": profile.get("base", mbti_type.lower()),
            "risk_params": strategy.get_risk_params(),
            "trade_count": strategy._trade_count,
            "signal_count": strategy._signal_count,
        }
