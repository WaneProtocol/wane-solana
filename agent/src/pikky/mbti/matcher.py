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

    def match_from_preferences(self, prefs: PreferenceInput) -> MatchResult:
        """
        Match MBTI type from user-provided preferences.

        Args:
            prefs: User preference inputs.

        Returns:
            MatchResult with the best-fit type and confidence.
        """
        reasoning: list[str] = []

        ei_score, ei_conf = self._score_ei_from_preferences(prefs, reasoning)
        sn_score, sn_conf = self._score_sn_from_preferences(prefs, reasoning)
        tf_score, tf_conf = self._score_tf_from_preferences(prefs, reasoning)
        jp_score, jp_conf = self._score_jp_from_preferences(prefs, reasoning)

        axes = [
            AxisScore("EI", "Introversion", "Extraversion", ei_score, ei_conf),
            AxisScore("SN", "Sensing", "Intuition", sn_score, sn_conf),
            AxisScore("TF", "Feeling", "Thinking", tf_score, tf_conf),
            AxisScore("JP", "Perceiving", "Judging", jp_score, jp_conf),
        ]

        return self._resolve_type(axes, reasoning)

    def match_from_behavior(self, metrics: BehaviorMetrics) -> MatchResult:
        """
        Match MBTI type from on-chain trading behavior analysis.

        Args:
            metrics: Quantified trading behavior metrics.

        Returns:
            MatchResult with the best-fit type and confidence.
        """
        reasoning: list[str] = []

        ei_score, ei_conf = self._score_ei_from_behavior(metrics, reasoning)
        sn_score, sn_conf = self._score_sn_from_behavior(metrics, reasoning)
        tf_score, tf_conf = self._score_tf_from_behavior(metrics, reasoning)
        jp_score, jp_conf = self._score_jp_from_behavior(metrics, reasoning)

        axes = [
            AxisScore("EI", "Introversion", "Extraversion", ei_score, ei_conf),
            AxisScore("SN", "Sensing", "Intuition", sn_score, sn_conf),
            AxisScore("TF", "Feeling", "Thinking", tf_score, tf_conf),
            AxisScore("JP", "Perceiving", "Judging", jp_score, jp_conf),
        ]

        return self._resolve_type(axes, reasoning)

    def match_hybrid(
        self,
        prefs: Optional[PreferenceInput],
        metrics: Optional[BehaviorMetrics],
        behavior_weight: float = 0.6,
    ) -> MatchResult:
        """
        Match using both preferences and behavior, weighted.

        Args:
            prefs: Optional user preferences.
            metrics: Optional behavior metrics.
            behavior_weight: Weight given to behavior (0-1). Preferences get 1-weight.

        Returns:
            MatchResult from the blended analysis.
        """
        if prefs is None and metrics is None:
            return self._default_result()

        if prefs is None:
            return self.match_from_behavior(metrics)  # type: ignore
        if metrics is None:
            return self.match_from_preferences(prefs)

        pref_result = self.match_from_preferences(prefs)
        behavior_result = self.match_from_behavior(metrics)

        reasoning: list[str] = ["Hybrid matching with behavior and preferences"]
        blended_axes: list[AxisScore] = []

        pref_weight = 1.0 - behavior_weight

        for p_ax, b_ax in zip(pref_result.axis_scores, behavior_result.axis_scores):
            blended_score = p_ax.score * pref_weight + b_ax.score * behavior_weight
            blended_conf = p_ax.confidence * pref_weight + b_ax.confidence * behavior_weight

            blended_axes.append(AxisScore(
                axis=p_ax.axis,
                left_label=p_ax.left_label,
                right_label=p_ax.right_label,
                score=blended_score,
                confidence=blended_conf,
            ))

        reasoning.extend(pref_result.reasoning[:3])
        reasoning.extend(behavior_result.reasoning[:3])

        return self._resolve_type(blended_axes, reasoning)

    def score_type_fit(
        self,
        mbti_type: MbtiType,
        metrics: BehaviorMetrics,
    ) -> float:
        """
        Score how well a user's behavior fits a specific MBTI type.

        Args:
            mbti_type: The type to score against.
            metrics: The user's trading behavior.

        Returns:
            Fit score from 0 (poor fit) to 1 (perfect fit).
        """
        profile = self._profiles[mbti_type]
        dimensions: list[float] = []

        risk_diff = abs(profile.risk_tolerance - self._estimate_risk_tolerance(metrics))
        dimensions.append(1.0 - min(risk_diff, 1.0))

        freq_map = {"very_low": 0.5, "low": 2, "medium": 5, "high": 10, "very_high": 20}
        expected_freq = freq_map.get(profile.trade_frequency.value, 5)
        actual_freq = metrics.trade_frequency_per_day
        freq_diff = abs(expected_freq - actual_freq) / max(expected_freq, 1)
        dimensions.append(1.0 - min(freq_diff, 1.0))

        hold_map = {"scalp": 300, "short": 1800, "medium": 7200, "long": 28800, "hodl": 86400}
        expected_hold = hold_map.get(profile.holding_period.value, 7200)
        hold_diff = abs(expected_hold - metrics.avg_hold_duration_seconds) / max(expected_hold, 1)
        dimensions.append(1.0 - min(hold_diff, 1.0))

        emotion_diff = abs(profile.emotional_factor - self._estimate_emotional_factor(metrics))
        dimensions.append(1.0 - min(emotion_diff, 1.0))

        discipline_diff = abs(profile.discipline_score - self._estimate_discipline(metrics))
        dimensions.append(1.0 - min(discipline_diff, 1.0))

        weights = [0.3, 0.2, 0.2, 0.15, 0.15]
        weighted_sum = sum(d * w for d, w in zip(dimensions, weights))

        return max(0.0, min(1.0, weighted_sum))

    def _score_ei_from_preferences(
        self,
        prefs: PreferenceInput,
        reasoning: list[str],
    ) -> tuple[float, float]:
        """Score E/I axis from preferences. Positive = Extravert."""
        score = 0.0
        confidence = 0.3

        if prefs.social_trading is not None:
            if prefs.social_trading:
                score += 0.5
                reasoning.append("Prefers social trading (E)")
            else:
                score -= 0.5
                reasoning.append("Prefers solo trading (I)")
            confidence += 0.2

        if prefs.trade_frequency_preference:
            freq = prefs.trade_frequency_preference.lower()
            if freq in ("high", "very_high"):
                score += 0.3
                reasoning.append("High trade frequency preference (E)")
            elif freq in ("low", "very_low"):
                score -= 0.3
                reasoning.append("Low trade frequency preference (I)")
            confidence += 0.15

        if prefs.market_chaos_reaction:
            reaction = prefs.market_chaos_reaction.lower()
            if reaction in ("excited", "opportunity"):
                score += 0.3
            elif reaction in ("anxious", "wait"):
                score -= 0.3
            confidence += 0.1

        return max(-1, min(1, score)), min(confidence, 1.0)

    def _score_sn_from_preferences(
        self,
        prefs: PreferenceInput,
        reasoning: list[str],
    ) -> tuple[float, float]:
        """Score S/N axis. Positive = Intuition (N)."""
        score = 0.0
        confidence = 0.3

        if prefs.analysis_depth:
            depth = prefs.analysis_depth.lower()
            if depth in ("deep", "thorough", "research"):
                score -= 0.4
                reasoning.append("Thorough analysis preference (S)")
            elif depth in ("quick", "intuitive", "gut"):
                score += 0.4
                reasoning.append("Intuitive analysis preference (N)")
            confidence += 0.2

        if prefs.decision_style:
            style = prefs.decision_style.lower()
            if style in ("data", "numbers", "charts"):
                score -= 0.3
                reasoning.append("Data-driven decisions (S)")
            elif style in ("narrative", "vision", "feeling"):
                score += 0.3
                reasoning.append("Narrative-driven decisions (N)")
            confidence += 0.15

        return max(-1, min(1, score)), min(confidence, 1.0)

    def _score_tf_from_preferences(
        self,
        prefs: PreferenceInput,
        reasoning: list[str],
    ) -> tuple[float, float]:
        """Score T/F axis. Positive = Thinking (T)."""
        score = 0.0
        confidence = 0.3

        if prefs.loss_reaction:
            reaction = prefs.loss_reaction.lower()
            if reaction in ("cut_immediately", "accept", "systematic"):
                score += 0.5
                reasoning.append("Systematic loss handling (T)")
            elif reaction in ("hold_hope", "emotional", "denial"):
                score -= 0.5
                reasoning.append("Emotional loss handling (F)")
            confidence += 0.25

        if prefs.win_reaction:
            reaction = prefs.win_reaction.lower()
            if reaction in ("take_profit", "rebalance", "systematic"):
                score += 0.3
                reasoning.append("Systematic profit taking (T)")
            elif reaction in ("celebrate", "share", "euphoric"):
                score -= 0.3
                reasoning.append("Emotional profit response (F)")
            confidence += 0.15

        if prefs.risk_appetite is not None:
            if prefs.risk_appetite <= 3:
                score += 0.2
            elif prefs.risk_appetite >= 8:
                score -= 0.1
            confidence += 0.1

        return max(-1, min(1, score)), min(confidence, 1.0)

    def _score_jp_from_preferences(
        self,
        prefs: PreferenceInput,
        reasoning: list[str],
    ) -> tuple[float, float]:
        """Score J/P axis. Positive = Judging (J)."""
        score = 0.0
        confidence = 0.3

        if prefs.position_sizing_style:
            style = prefs.position_sizing_style.lower()
            if style in ("fixed", "systematic", "rules"):
                score += 0.5
                reasoning.append("Fixed position sizing (J)")
            elif style in ("variable", "feel", "dynamic"):
                score -= 0.5
                reasoning.append("Variable position sizing (P)")
            confidence += 0.2

        if prefs.preferred_holding_time:
            hold = prefs.preferred_holding_time.lower()
            if hold in ("long", "hodl", "weeks"):
                score += 0.3
                reasoning.append("Long holding preference (J)")
            elif hold in ("short", "scalp", "minutes"):
                score -= 0.3
                reasoning.append("Short holding preference (P)")
            confidence += 0.15

        return max(-1, min(1, score)), min(confidence, 1.0)

    def _score_ei_from_behavior(
        self,
        metrics: BehaviorMetrics,
        reasoning: list[str],
    ) -> tuple[float, float]:
        """Score E/I from trading behavior."""
        score = 0.0
        confidence = 0.4

        if metrics.trade_frequency_per_day > 8:
            score += 0.5
            reasoning.append(f"High trade frequency ({metrics.trade_frequency_per_day:.1f}/day) suggests E")
        elif metrics.trade_frequency_per_day < 2:
            score -= 0.5
            reasoning.append(f"Low trade frequency ({metrics.trade_frequency_per_day:.1f}/day) suggests I")

        if metrics.unique_tokens_traded > 10:
            score += 0.3
            reasoning.append(f"Diverse token portfolio ({metrics.unique_tokens_traded} tokens) suggests E")
        elif metrics.unique_tokens_traded <= 3:
            score -= 0.3

        if metrics.total_trades > 5:
            confidence += 0.2

        return max(-1, min(1, score)), min(confidence, 1.0)

    def _score_sn_from_behavior(
        self,
        metrics: BehaviorMetrics,
        reasoning: list[str],
    ) -> tuple[float, float]:
        """Score S/N from behavior. High volatility trading = N."""
        score = 0.0
        confidence = 0.35

        total_vol_trades = metrics.trades_during_high_volatility + metrics.trades_during_low_volatility
        if total_vol_trades > 0:
            high_vol_ratio = metrics.trades_during_high_volatility / total_vol_trades
            if high_vol_ratio > 0.6:
                score += 0.4
                reasoning.append("Trades during high volatility suggests N")
            elif high_vol_ratio < 0.3:
                score -= 0.4
                reasoning.append("Prefers low volatility suggests S")
            confidence += 0.2

        if metrics.dca_pattern_detected:
            score -= 0.3
            reasoning.append("DCA pattern detected suggests S")
            confidence += 0.15

        if metrics.contrarian_trade_pct > 0.3:
            score += 0.3
            confidence += 0.1

        return max(-1, min(1, score)), min(confidence, 1.0)

    def _score_tf_from_behavior(
        self,
        metrics: BehaviorMetrics,
        reasoning: list[str],
    ) -> tuple[float, float]:
        """Score T/F from behavior. Disciplined = T, Emotional = F."""
        score = 0.0
        confidence = 0.35

        if metrics.uses_stop_loss:
            score += 0.4
            reasoning.append("Uses stop losses suggests T")
            confidence += 0.15
        else:
            score -= 0.2

        if metrics.panic_sell_count > 2:
            score -= 0.4
            reasoning.append(f"{metrics.panic_sell_count} panic sells suggests F")
            confidence += 0.15

        if metrics.fomo_buy_count > 3:
            score -= 0.3
            reasoning.append(f"{metrics.fomo_buy_count} FOMO buys suggests F")
            confidence += 0.1

        if metrics.consecutive_loss_max > 5 and metrics.total_trades > 20:
            score -= 0.2

        return max(-1, min(1, score)), min(confidence, 1.0)

    def _score_jp_from_behavior(
        self,
        metrics: BehaviorMetrics,
        reasoning: list[str],
    ) -> tuple[float, float]:
        """Score J/P from behavior. Structured = J, Flexible = P."""
        score = 0.0
        confidence = 0.35

        if metrics.dca_pattern_detected:
            score += 0.5
            reasoning.append("Systematic DCA pattern suggests J")
            confidence += 0.2

        size_variance = metrics.max_trade_size_pct - metrics.avg_trade_size_pct
        if metrics.avg_trade_size_pct > 0:
            cv = size_variance / metrics.avg_trade_size_pct
            if cv < 0.3:
                score += 0.3
                reasoning.append("Consistent position sizing suggests J")
            elif cv > 1.0:
                score -= 0.3
                reasoning.append("Highly variable position sizing suggests P")
            confidence += 0.15

        if metrics.avg_hold_duration_seconds > 14400:
            score += 0.2
        elif metrics.avg_hold_duration_seconds < 600:
            score -= 0.2

        return max(-1, min(1, score)), min(confidence, 1.0)

    def _resolve_type(
        self,
        axes: list[AxisScore],
        reasoning: list[str],
    ) -> MatchResult:
        """Resolve axis scores into a final MBTI type."""
        type_str = ""
        for ax in axes:
            type_str += ax.result

        try:
            primary = MbtiType(type_str)
        except ValueError:
            primary = MbtiType.ISTJ
            reasoning.append(f"Could not resolve type '{type_str}', defaulting to ISTJ")

        avg_confidence = sum(ax.confidence for ax in axes) / len(axes)

        alternatives = self._compute_alternatives(axes, primary)

        return MatchResult(
            primary_type=primary,
            confidence=avg_confidence,
            axis_scores=axes,
            alternative_types=alternatives,
            reasoning=reasoning,
        )

    def _compute_alternatives(
        self,
        axes: list[AxisScore],
        primary: MbtiType,
    ) -> list[tuple[MbtiType, float]]:
        """
        Compute alternative types ranked by proximity.

        For each axis near the boundary (low confidence), flip it to produce
        alternative types.
        """
        alternatives: list[tuple[MbtiType, float]] = []

        weak_axes = sorted(axes, key=lambda a: abs(a.score))

        for i, weak_ax in enumerate(weak_axes[:2]):
            flipped_str = ""
            for ax in axes:
                if ax.axis == weak_ax.axis:
                    flipped_score = -ax.score
                    temp = AxisScore(ax.axis, ax.left_label, ax.right_label, flipped_score, ax.confidence)
                    flipped_str += temp.result
                else:
                    flipped_str += ax.result

            try:
                alt_type = MbtiType(flipped_str)
                if alt_type != primary:
                    score = 1.0 - abs(weak_ax.score)
                    alternatives.append((alt_type, score))
            except ValueError:
                continue

        alternatives.sort(key=lambda x: x[1], reverse=True)
        return alternatives[:3]

    def _estimate_risk_tolerance(self, metrics: BehaviorMetrics) -> float:
        """Estimate risk tolerance from behavior metrics."""
        factors = []

        if metrics.max_trade_size_pct > 0:
            factors.append(min(metrics.max_trade_size_pct / 0.20, 1.0))

        if metrics.max_drawdown_pct > 0:
            factors.append(min(metrics.max_drawdown_pct / 0.30, 1.0))

        factors.append(min(metrics.trade_frequency_per_day / 15, 1.0))

        if metrics.avg_slippage_tolerance_bps > 0:
            factors.append(min(metrics.avg_slippage_tolerance_bps / 200, 1.0))

        if not factors:
            return 0.5
        return sum(factors) / len(factors)

    def _estimate_emotional_factor(self, metrics: BehaviorMetrics) -> float:
        """Estimate emotional trading factor from behavior."""
        indicators = []

        if metrics.total_trades > 0:
            panic_rate = metrics.panic_sell_count / metrics.total_trades
            indicators.append(min(panic_rate * 10, 1.0))

            fomo_rate = metrics.fomo_buy_count / metrics.total_trades
            indicators.append(min(fomo_rate * 10, 1.0))

        if not indicators:
            return 0.5
        return sum(indicators) / len(indicators)

    def _estimate_discipline(self, metrics: BehaviorMetrics) -> float:
        """Estimate trading discipline from behavior."""
        scores = []

        if metrics.uses_stop_loss:
            scores.append(0.8)
        else:
            scores.append(0.3)

        if metrics.dca_pattern_detected:
            scores.append(0.9)
        else:
            scores.append(0.5)

        if metrics.avg_trade_size_pct > 0 and metrics.max_trade_size_pct > 0:
            consistency = 1.0 - min(
                (metrics.max_trade_size_pct - metrics.avg_trade_size_pct)
                / metrics.avg_trade_size_pct,
                1.0,
            )
            scores.append(consistency)

        if not scores:
            return 0.5
        return sum(scores) / len(scores)

    def _default_result(self) -> MatchResult:
        """Return the default ISTJ result when no data is available."""
        axes = [
            AxisScore("EI", "Introversion", "Extraversion", -0.3, 0.2),
            AxisScore("SN", "Sensing", "Intuition", -0.3, 0.2),
            AxisScore("TF", "Feeling", "Thinking", 0.2, 0.2),
            AxisScore("JP", "Perceiving", "Judging", 0.3, 0.2),
        ]
        return MatchResult(
            primary_type=MbtiType.ISTJ,
            confidence=0.2,
            axis_scores=axes,
            alternative_types=[],
            reasoning=["No data available, defaulting to ISTJ (The DCA Machine)"],
        )
