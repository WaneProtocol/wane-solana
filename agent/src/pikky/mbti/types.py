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

    def kelly_fraction(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """
        Calculate the Kelly Criterion fraction adjusted by personality.

        The raw Kelly fraction is scaled by discipline and risk tolerance
        to produce a personality-appropriate position size.

        Args:
            win_rate: Historical win rate (0-1).
            avg_win: Average winning trade return.
            avg_loss: Average losing trade return (positive number).

        Returns:
            Adjusted Kelly fraction (0-1).
        """
        if avg_loss <= 0 or win_rate <= 0:
            return self.base_position_pct

        b = avg_win / avg_loss
        q = 1.0 - win_rate
        kelly = (win_rate * b - q) / b

        if kelly <= 0:
            return self.base_position_pct * 0.5

        personality_scalar = (
            self.discipline_score * 0.5
            + self.risk_tolerance * 0.3
            + self.position_sizing_aggression * 0.2
        )

        adjusted = kelly * personality_scalar * 0.5
        return max(self.base_position_pct * 0.25, min(adjusted, 0.25))


def get_all_profiles() -> dict[MbtiType, MbtiProfile]:
    """Get profiles for all 16 MBTI types."""
    return dict(_ALL_PROFILES)


def get_profile(mbti_type: MbtiType) -> MbtiProfile:
    """Get the profile for a specific MBTI type."""
    return _ALL_PROFILES[mbti_type]


_ALL_PROFILES: dict[MbtiType, MbtiProfile] = {
    MbtiType.INTJ: MbtiProfile(
        mbti_type=MbtiType.INTJ,
        archetype_name="The Sniper",
        description="Methodical and strategic. Waits for the perfect setup with mathematical precision. Few trades, high conviction, tight risk management.",
        risk_tolerance=0.35,
        trade_frequency=TradeFrequency.LOW,
        holding_period=HoldingPeriod.MEDIUM,
        position_sizing_aggression=0.6,
        emotional_factor=0.1,
        discipline_score=0.95,
        adaptability=0.5,
        contrarian_tendency=0.4,
        preferred_strategies=["rsi_macd_convergence", "support_resistance"],
        strengths=["patience", "risk_management", "technical_analysis"],
        weaknesses=["misses_momentum_moves", "over_analysis"],
        max_concurrent_positions=2,
        base_position_pct=0.08,
        stop_loss_default_pct=0.03,
        take_profit_default_pct=0.09,
        max_daily_trades=3,
        preferred_volatility="low",
    ),
    MbtiType.INTP: MbtiProfile(
        mbti_type=MbtiType.INTP,
        archetype_name="The Quant",
        description="Data-driven and analytical. Builds complex models and tests theories. More interested in being right than making money.",
        risk_tolerance=0.40,
        trade_frequency=TradeFrequency.LOW,
        holding_period=HoldingPeriod.MEDIUM,
        position_sizing_aggression=0.5,
        emotional_factor=0.15,
        discipline_score=0.80,
        adaptability=0.7,
        contrarian_tendency=0.5,
        preferred_strategies=["statistical_arbitrage", "correlation_trading"],
        strengths=["pattern_recognition", "system_building", "objectivity"],
        weaknesses=["analysis_paralysis", "ignores_fundamentals"],
        max_concurrent_positions=3,
        base_position_pct=0.06,
        stop_loss_default_pct=0.04,
        take_profit_default_pct=0.10,
        max_daily_trades=4,
        preferred_volatility="medium",
    ),
    MbtiType.ENTJ: MbtiProfile(
        mbti_type=MbtiType.ENTJ,
        archetype_name="The Commander",
        description="Decisive and authoritative. Takes bold positions with confidence. Natural leader who trusts their own judgment over the crowd.",
        risk_tolerance=0.55,
        trade_frequency=TradeFrequency.MEDIUM,
        holding_period=HoldingPeriod.MEDIUM,
        position_sizing_aggression=0.7,
        emotional_factor=0.2,
        discipline_score=0.85,
        adaptability=0.6,
        contrarian_tendency=0.3,
        preferred_strategies=["trend_following", "breakout_with_volume"],
        strengths=["decision_making", "conviction", "execution_speed"],
        weaknesses=["overconfidence", "stubbornness"],
        max_concurrent_positions=4,
        base_position_pct=0.07,
        stop_loss_default_pct=0.05,
        take_profit_default_pct=0.15,
        max_daily_trades=8,
        preferred_volatility="medium",
    ),
    MbtiType.ENTP: MbtiProfile(
        mbti_type=MbtiType.ENTP,
        archetype_name="The Degen",
        description="Risk-seeking contrarian. Thrives on chaos and volatile markets. Multiple positions, high leverage mental model, loves the action.",
        risk_tolerance=0.90,
        trade_frequency=TradeFrequency.VERY_HIGH,
        holding_period=HoldingPeriod.SHORT,
        position_sizing_aggression=0.85,
        emotional_factor=0.5,
        discipline_score=0.45,
        adaptability=0.95,
        contrarian_tendency=0.8,
        preferred_strategies=["mean_reversion", "volatility_breakout", "contrarian"],
        strengths=["opportunity_finding", "adaptability", "risk_appetite"],
        weaknesses=["overtrading", "poor_risk_management", "chasing_losses"],
        max_concurrent_positions=8,
        base_position_pct=0.06,
        stop_loss_default_pct=0.12,
        take_profit_default_pct=0.25,
        max_daily_trades=20,
        preferred_volatility="high",
    ),
    MbtiType.INFJ: MbtiProfile(
        mbti_type=MbtiType.INFJ,
        archetype_name="The Oracle",
        description="Intuitive and visionary. Sees the big picture and invests in narratives. Patient holder who believes in transformative potential.",
        risk_tolerance=0.25,
        trade_frequency=TradeFrequency.VERY_LOW,
        holding_period=HoldingPeriod.HODL,
        position_sizing_aggression=0.3,
        emotional_factor=0.4,
        discipline_score=0.75,
        adaptability=0.4,
        contrarian_tendency=0.5,
        preferred_strategies=["narrative_investing", "accumulation"],
        strengths=["vision", "patience", "conviction_in_thesis"],
        weaknesses=["too_attached_to_losers", "ignores_technicals"],
        max_concurrent_positions=2,
        base_position_pct=0.04,
        stop_loss_default_pct=0.10,
        take_profit_default_pct=0.50,
        max_daily_trades=2,
        preferred_volatility="low",
    ),
    MbtiType.INFP: MbtiProfile(
        mbti_type=MbtiType.INFP,
        archetype_name="The Dreamer",
        description="Idealistic and values-driven. Invests in projects they believe in emotionally. Hates selling at a loss. Diamond hands by default.",
        risk_tolerance=0.20,
        trade_frequency=TradeFrequency.VERY_LOW,
        holding_period=HoldingPeriod.HODL,
        position_sizing_aggression=0.2,
        emotional_factor=0.7,
        discipline_score=0.50,
        adaptability=0.3,
        contrarian_tendency=0.3,
        preferred_strategies=["conviction_holding", "dca"],
        strengths=["diamond_hands", "long_term_vision"],
        weaknesses=["emotional_attachment", "ignores_stop_losses", "sells_too_late"],
        max_concurrent_positions=2,
        base_position_pct=0.03,
        stop_loss_default_pct=0.15,
        take_profit_default_pct=0.60,
        max_daily_trades=1,
        preferred_volatility="low",
    ),
    MbtiType.ENFJ: MbtiProfile(
        mbti_type=MbtiType.ENFJ,
        archetype_name="The Influencer",
        description="Social and community-driven. Follows and amplifies trends. Trades based on community sentiment and social proof.",
        risk_tolerance=0.50,
        trade_frequency=TradeFrequency.MEDIUM,
        holding_period=HoldingPeriod.MEDIUM,
        position_sizing_aggression=0.5,
        emotional_factor=0.55,
        discipline_score=0.65,
        adaptability=0.7,
        contrarian_tendency=0.2,
        preferred_strategies=["trend_following", "sentiment_trading"],
        strengths=["sentiment_reading", "community_awareness", "timing"],
        weaknesses=["herd_mentality", "fomo", "late_exits"],
        max_concurrent_positions=4,
        base_position_pct=0.05,
        stop_loss_default_pct=0.06,
        take_profit_default_pct=0.18,
        max_daily_trades=6,
        preferred_volatility="medium",
    ),
    MbtiType.ENFP: MbtiProfile(
        mbti_type=MbtiType.ENFP,
        archetype_name="The FOMO King",
        description="Enthusiastic and momentum-driven. Jumps on breakouts, chases pumps, loves the thrill. High frequency, wide stops, many trades.",
        risk_tolerance=0.75,
        trade_frequency=TradeFrequency.HIGH,
        holding_period=HoldingPeriod.SHORT,
        position_sizing_aggression=0.7,
        emotional_factor=0.8,
        discipline_score=0.35,
        adaptability=0.85,
        contrarian_tendency=0.15,
        preferred_strategies=["momentum", "breakout", "volume_spike"],
        strengths=["trend_catching", "enthusiasm", "quick_decisions"],
        weaknesses=["fomo", "panic_selling", "overtrading", "boredom_exits"],
        max_concurrent_positions=5,
        base_position_pct=0.04,
        stop_loss_default_pct=0.08,
        take_profit_default_pct=0.20,
        max_daily_trades=15,
        preferred_volatility="high",
    ),
    MbtiType.ISTJ: MbtiProfile(
        mbti_type=MbtiType.ISTJ,
        archetype_name="The DCA Machine",
        description="Methodical and rule-based. Dollar cost averages on a strict schedule. Ignores noise, ignores sentiment, follows the plan.",
        risk_tolerance=0.15,
        trade_frequency=TradeFrequency.MEDIUM,
        holding_period=HoldingPeriod.LONG,
        position_sizing_aggression=0.2,
        emotional_factor=0.05,
        discipline_score=0.98,
        adaptability=0.15,
        contrarian_tendency=0.1,
        preferred_strategies=["dca", "fixed_interval_accumulation"],
        strengths=["discipline", "consistency", "emotional_control"],
        weaknesses=["inflexibility", "misses_opportunities", "slow_to_adapt"],
        max_concurrent_positions=3,
        base_position_pct=0.03,
        stop_loss_default_pct=0.15,
        take_profit_default_pct=0.50,
        max_daily_trades=5,
        preferred_volatility="any",
    ),
    MbtiType.ISFJ: MbtiProfile(
        mbti_type=MbtiType.ISFJ,
        archetype_name="The Guardian",
        description="Conservative and protective. Prioritizes capital preservation above all. Only invests in blue-chip tokens with proven track records.",
        risk_tolerance=0.10,
        trade_frequency=TradeFrequency.VERY_LOW,
        holding_period=HoldingPeriod.HODL,
        position_sizing_aggression=0.15,
        emotional_factor=0.3,
        discipline_score=0.90,
        adaptability=0.2,
        contrarian_tendency=0.05,
        preferred_strategies=["blue_chip_accumulation", "dca"],
        strengths=["capital_preservation", "patience", "risk_aversion"],
        weaknesses=["too_conservative", "misses_all_big_moves", "tiny_positions"],
        max_concurrent_positions=2,
        base_position_pct=0.02,
        stop_loss_default_pct=0.05,
        take_profit_default_pct=0.30,
        max_daily_trades=2,
        preferred_volatility="low",
    ),
    MbtiType.ESTJ: MbtiProfile(
        mbti_type=MbtiType.ESTJ,
        archetype_name="The Executive",
        description="Organized and efficient. Follows a structured trading plan. Respects rules and hierarchy. Favors established tokens.",
        risk_tolerance=0.45,
        trade_frequency=TradeFrequency.MEDIUM,
        holding_period=HoldingPeriod.MEDIUM,
        position_sizing_aggression=0.5,
        emotional_factor=0.2,
        discipline_score=0.88,
        adaptability=0.4,
        contrarian_tendency=0.2,
        preferred_strategies=["trend_following", "structured_entries"],
        strengths=["organization", "rule_following", "efficiency"],
        weaknesses=["rigid", "ignores_novel_opportunities"],
        max_concurrent_positions=4,
        base_position_pct=0.06,
        stop_loss_default_pct=0.05,
        take_profit_default_pct=0.15,
        max_daily_trades=6,
        preferred_volatility="medium",
    ),
    MbtiType.ESFJ: MbtiProfile(
        mbti_type=MbtiType.ESFJ,
        archetype_name="The Provider",
        description="Community-oriented and supportive. Trades what friends are trading. Safety in numbers. Prefers consensus plays.",
        risk_tolerance=0.20,
        trade_frequency=TradeFrequency.MEDIUM,
        holding_period=HoldingPeriod.LONG,
        position_sizing_aggression=0.25,
        emotional_factor=0.5,
        discipline_score=0.70,
        adaptability=0.5,
        contrarian_tendency=0.05,
        preferred_strategies=["consensus_following", "dca"],
        strengths=["community_awareness", "steady_accumulation"],
        weaknesses=["herd_mentality", "late_to_trends", "conflict_averse"],
        max_concurrent_positions=3,
        base_position_pct=0.03,
        stop_loss_default_pct=0.07,
        take_profit_default_pct=0.20,
        max_daily_trades=4,
        preferred_volatility="low",
    ),
    MbtiType.ISTP: MbtiProfile(
        mbti_type=MbtiType.ISTP,
        archetype_name="The Mechanic",
        description="Cool-headed and practical. Understands the mechanics of markets. Quick reflexes, calculated risks. Like a poker player.",
        risk_tolerance=0.60,
        trade_frequency=TradeFrequency.MEDIUM,
        holding_period=HoldingPeriod.SHORT,
        position_sizing_aggression=0.6,
        emotional_factor=0.15,
        discipline_score=0.75,
        adaptability=0.8,
        contrarian_tendency=0.5,
        preferred_strategies=["mean_reversion", "range_trading"],
        strengths=["calm_under_pressure", "technical_skill", "quick_reflexes"],
        weaknesses=["boredom_in_slow_markets", "underestimates_trends"],
        max_concurrent_positions=4,
        base_position_pct=0.05,
        stop_loss_default_pct=0.06,
        take_profit_default_pct=0.15,
        max_daily_trades=10,
        preferred_volatility="medium",
    ),
    MbtiType.ISFP: MbtiProfile(
        mbti_type=MbtiType.ISFP,
        archetype_name="The Artist",
        description="Gentle and aesthetic. Drawn to beautiful charts and clean setups. Trades intuitively. Avoids conflict and chaos.",
        risk_tolerance=0.30,
        trade_frequency=TradeFrequency.LOW,
        holding_period=HoldingPeriod.MEDIUM,
        position_sizing_aggression=0.3,
        emotional_factor=0.6,
        discipline_score=0.55,
        adaptability=0.5,
        contrarian_tendency=0.2,
        preferred_strategies=["pattern_trading", "momentum_lite"],
        strengths=["pattern_recognition", "aesthetic_chart_reading"],
        weaknesses=["emotional_exits", "avoids_hard_decisions"],
        max_concurrent_positions=3,
        base_position_pct=0.04,
        stop_loss_default_pct=0.06,
        take_profit_default_pct=0.15,
        max_daily_trades=4,
        preferred_volatility="low",
    ),
    MbtiType.ESTP: MbtiProfile(
        mbti_type=MbtiType.ESTP,
        archetype_name="The Hustler",
        description="Action-oriented adrenaline junkie. Lives for the trade. High risk, high reward. Fast in, fast out. The ultimate day trader.",
        risk_tolerance=0.85,
        trade_frequency=TradeFrequency.VERY_HIGH,
        holding_period=HoldingPeriod.SCALP,
        position_sizing_aggression=0.8,
        emotional_factor=0.4,
        discipline_score=0.50,
        adaptability=0.90,
        contrarian_tendency=0.6,
        preferred_strategies=["scalping", "volatility_breakout", "momentum"],
        strengths=["speed", "adaptability", "risk_appetite", "action_bias"],
        weaknesses=["overtrading", "impatience", "ignores_long_term"],
        max_concurrent_positions=6,
        base_position_pct=0.05,
        stop_loss_default_pct=0.08,
        take_profit_default_pct=0.12,
        max_daily_trades=25,
        preferred_volatility="high",
    ),
    MbtiType.ESFP: MbtiProfile(
        mbti_type=MbtiType.ESFP,
        archetype_name="The Performer",
        description="Fun-loving and spontaneous. Trades for the excitement. Loves sharing wins on social media. YOLO energy.",
        risk_tolerance=0.65,
        trade_frequency=TradeFrequency.HIGH,
        holding_period=HoldingPeriod.SHORT,
        position_sizing_aggression=0.6,
        emotional_factor=0.75,
        discipline_score=0.30,
        adaptability=0.80,
        contrarian_tendency=0.1,
        preferred_strategies=["momentum", "hype_trading", "breakout"],
        strengths=["enthusiasm", "social_trading", "trend_awareness"],
        weaknesses=["impulsive", "no_plan", "chases_pumps", "emotional"],
        max_concurrent_positions=5,
        base_position_pct=0.04,
        stop_loss_default_pct=0.10,
        take_profit_default_pct=0.20,
        max_daily_trades=12,
        preferred_volatility="high",
    ),
}

