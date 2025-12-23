"""
MBTI type definitions and trading profiles.

Defines the MbtiType enum for all 16 personality types and the MbtiProfile
dataclass that encodes each type's trading characteristics including risk
tolerance, trade frequency, holding period, position sizing, and emotional
factors.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MbtiType(str, Enum):
    """All 16 MBTI personality types."""

    INTJ = "INTJ"
    INTP = "INTP"
    ENTJ = "ENTJ"
    ENTP = "ENTP"
    INFJ = "INFJ"
    INFP = "INFP"
    ENFJ = "ENFJ"
    ENFP = "ENFP"
    ISTJ = "ISTJ"
    ISFJ = "ISFJ"
    ESTJ = "ESTJ"
    ESFJ = "ESFJ"
    ISTP = "ISTP"
    ISFP = "ISFP"
    ESTP = "ESTP"
    ESFP = "ESFP"


class TradeFrequency(str, Enum):
    """How often a type tends to trade."""

    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class HoldingPeriod(str, Enum):
    """Typical holding duration for a type."""

    SCALP = "scalp"
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    HODL = "hodl"


@dataclass(frozen=True)
class MbtiProfile:
    """
    Trading personality profile for an MBTI type.

    Encodes all the behavioral characteristics that influence how a
    particular personality type approaches trading decisions.
    """

    mbti_type: MbtiType
    archetype_name: str
    description: str

    risk_tolerance: float
    trade_frequency: TradeFrequency
    holding_period: HoldingPeriod
    position_sizing_aggression: float
    emotional_factor: float
    discipline_score: float
    adaptability: float
    contrarian_tendency: float

    preferred_strategies: list[str]
    strengths: list[str]
    weaknesses: list[str]

    max_concurrent_positions: int
    base_position_pct: float
    stop_loss_default_pct: float
    take_profit_default_pct: float
    max_daily_trades: int
    preferred_volatility: str

    def effective_risk_score(self) -> float:
        """
        Compute an effective risk score combining multiple factors.

        Higher values mean more risk-seeking behavior.
        """
        raw = (
            self.risk_tolerance * 0.4
            + self.position_sizing_aggression * 0.2
            + self.emotional_factor * 0.15
            + (1.0 - self.discipline_score) * 0.15
            + self.contrarian_tendency * 0.1
        )
        return max(0.0, min(1.0, raw))
