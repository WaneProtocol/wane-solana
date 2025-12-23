"""
MBTI Matcher for PIKKY.

Analyzes user preferences or on-chain trading behavior history to
suggest or assign an MBTI trading personality type. Uses a multi-dimensional
scoring algorithm across the four MBTI axes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

from pikky.mbti.types import MbtiProfile, MbtiType, get_all_profiles

logger = structlog.get_logger(__name__)


@dataclass
class BehaviorMetrics:
    """Quantified trading behavior metrics from on-chain history."""

    total_trades: int = 0
    avg_hold_duration_seconds: float = 0.0
    avg_trade_size_pct: float = 0.0
    max_trade_size_pct: float = 0.0
    win_rate: float = 0.0
    avg_pnl_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    trade_frequency_per_day: float = 0.0
    unique_tokens_traded: int = 0
    avg_slippage_tolerance_bps: int = 50
    uses_stop_loss: bool = False
    avg_stop_loss_distance_pct: float = 0.0
    consecutive_loss_max: int = 0
    trades_during_high_volatility: int = 0
    trades_during_low_volatility: int = 0
    contrarian_trade_pct: float = 0.0
    dca_pattern_detected: bool = False
    panic_sell_count: int = 0
    fomo_buy_count: int = 0


@dataclass
class PreferenceInput:
    """User-provided preference inputs for MBTI matching."""

    risk_appetite: Optional[int] = None
    preferred_holding_time: Optional[str] = None
    trade_frequency_preference: Optional[str] = None
    loss_reaction: Optional[str] = None
    win_reaction: Optional[str] = None
    decision_style: Optional[str] = None
    social_trading: Optional[bool] = None
    analysis_depth: Optional[str] = None
    market_chaos_reaction: Optional[str] = None
    position_sizing_style: Optional[str] = None


@dataclass
class AxisScore:
    """Score on a single MBTI axis."""

    axis: str
    left_label: str
    right_label: str
    score: float  # -1 to 1, negative = left, positive = right
    confidence: float  # 0 to 1

    @property
    def result(self) -> str:
        """Get the winning side letter."""
        if self.axis == "EI":
            return "E" if self.score > 0 else "I"
        elif self.axis == "SN":
            return "N" if self.score > 0 else "S"
        elif self.axis == "TF":
            return "T" if self.score > 0 else "F"
        elif self.axis == "JP":
            return "J" if self.score > 0 else "P"
        return "?"


@dataclass
class MatchResult:
    """Result of MBTI matching."""

    primary_type: MbtiType
    confidence: float
    axis_scores: list[AxisScore]
    alternative_types: list[tuple[MbtiType, float]]
    reasoning: list[str]

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "primary_type": self.primary_type.value,
            "confidence": round(self.confidence, 3),
            "axes": {
                ax.axis: {
                    "score": round(ax.score, 3),
                    "confidence": round(ax.confidence, 3),
                    "result": ax.result,
                }
                for ax in self.axis_scores
            },
            "alternatives": [
                {"type": t.value, "score": round(s, 3)}
                for t, s in self.alternative_types
            ],
            "reasoning": self.reasoning,
        }


class MbtiMatcher:
    """
    Determines a user's MBTI trading personality type.

    Can match based on:
    1. Explicit user preferences (questionnaire-style)
    2. On-chain behavior analysis (trade history)
    3. Hybrid approach combining both

    The matcher scores each of the four MBTI axes independently:
    - E/I: Extraversion vs Introversion (social vs solo trading)
    - S/N: Sensing vs Intuition (data-driven vs narrative-driven)
    - T/F: Thinking vs Feeling (logical vs emotional decisions)
    - J/P: Judging vs Perceiving (structured vs flexible approach)
    """

    def __init__(self) -> None:
        self._profiles = get_all_profiles()
        logger.info("mbti_matcher_initialized")
