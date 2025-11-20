import { MbtiType, TradingStrategy } from "./types";

const HOUR = 3_600_000;
const DAY = 86_400_000;

function createStrategy(
  mbtiType: MbtiType,
  overrides: Partial<TradingStrategy>
): TradingStrategy {
  const base: TradingStrategy = {
    mbtiType,
    riskTolerance: 0.5,
    maxPositionSizePct: 0.1,
    maxLeverage: 5,
    defaultLeverage: 2,
    entryThreshold: 0.02,
    exitThreshold: 0.015,
    stopLossPercentage: 0.05,
    takeProfitPercentage: 0.1,
    maxHoldingPeriodMs: 7 * DAY,
    minHoldingPeriodMs: HOUR,
    maxConcurrentPositions: 3,
    trailingStopEnabled: false,
    trailingStopPercentage: 0.03,
    dcaEnabled: false,
    dcaIntervalMs: DAY,
    sentimentWeight: 0.33,
    technicalWeight: 0.34,
    fundamentalWeight: 0.33,
    rebalanceIntervalMs: DAY,
    description: "",
  };
  return { ...base, ...overrides };
}

export const MBTI_STRATEGIES: Record<MbtiType, TradingStrategy> = {
  [MbtiType.INTJ]: createStrategy(MbtiType.INTJ, {
    riskTolerance: 0.65,
    maxPositionSizePct: 0.15,
    maxLeverage: 10,
    defaultLeverage: 3,
    entryThreshold: 0.03,
    exitThreshold: 0.02,
    stopLossPercentage: 0.04,
    takeProfitPercentage: 0.15,
    maxHoldingPeriodMs: 30 * DAY,
    minHoldingPeriodMs: 4 * HOUR,
    maxConcurrentPositions: 5,
    trailingStopEnabled: true,
    trailingStopPercentage: 0.025,
    sentimentWeight: 0.15,
    technicalWeight: 0.55,
    fundamentalWeight: 0.30,
    rebalanceIntervalMs: 3 * DAY,
    description:
      "The Architect: Systematic, data-driven strategies with long-term vision. Favors complex technical analysis and fundamental research. High conviction positions with calculated risk.",
  }),

  [MbtiType.INTP]: createStrategy(MbtiType.INTP, {
    riskTolerance: 0.55,
    maxPositionSizePct: 0.08,
    maxLeverage: 8,
    defaultLeverage: 2,
    entryThreshold: 0.035,
    exitThreshold: 0.025,
    stopLossPercentage: 0.06,
    takeProfitPercentage: 0.20,
    maxHoldingPeriodMs: 14 * DAY,
    minHoldingPeriodMs: 2 * HOUR,
    maxConcurrentPositions: 8,
    trailingStopEnabled: true,
    trailingStopPercentage: 0.04,
    sentimentWeight: 0.10,
    technicalWeight: 0.50,
    fundamentalWeight: 0.40,
    rebalanceIntervalMs: 2 * DAY,
    description:
      "The Logician: Experimental and analytical. Tests multiple hypotheses simultaneously with smaller positions. Seeks undervalued gems through deep research.",
  }),

  [MbtiType.ENTJ]: createStrategy(MbtiType.ENTJ, {
    riskTolerance: 0.80,
    maxPositionSizePct: 0.20,
    maxLeverage: 15,
    defaultLeverage: 5,
    entryThreshold: 0.015,
    exitThreshold: 0.01,
    stopLossPercentage: 0.03,
    takeProfitPercentage: 0.12,
    maxHoldingPeriodMs: 7 * DAY,
    minHoldingPeriodMs: HOUR,
    maxConcurrentPositions: 6,
    trailingStopEnabled: true,
    trailingStopPercentage: 0.02,
    sentimentWeight: 0.25,
    technicalWeight: 0.50,
    fundamentalWeight: 0.25,
    rebalanceIntervalMs: DAY,
    description:
      "The Commander: Aggressive, decisive trader. Takes large positions with high leverage. Quick to enter and exit. Dominates trending markets with momentum strategies.",
  }),

  [MbtiType.ENTP]: createStrategy(MbtiType.ENTP, {
    riskTolerance: 0.70,
    maxPositionSizePct: 0.12,
    maxLeverage: 10,
    defaultLeverage: 3,
    entryThreshold: 0.02,
    exitThreshold: 0.015,
    stopLossPercentage: 0.05,
    takeProfitPercentage: 0.25,
    maxHoldingPeriodMs: 5 * DAY,
    minHoldingPeriodMs: 30 * 60_000,
    maxConcurrentPositions: 10,
    trailingStopEnabled: false,
    trailingStopPercentage: 0.03,
    dcaEnabled: true,
    dcaIntervalMs: 6 * HOUR,
    sentimentWeight: 0.35,
    technicalWeight: 0.40,
    fundamentalWeight: 0.25,
    rebalanceIntervalMs: 12 * HOUR,
    description:
      "The Debater: Contrarian and opportunistic. Loves finding asymmetric bets. Many small positions looking for outsized returns. Quick to pivot strategies.",
  }),

  [MbtiType.INFJ]: createStrategy(MbtiType.INFJ, {
    riskTolerance: 0.40,
    maxPositionSizePct: 0.08,
    maxLeverage: 3,
    defaultLeverage: 1,
    entryThreshold: 0.04,
    exitThreshold: 0.03,
    stopLossPercentage: 0.07,
    takeProfitPercentage: 0.15,
    maxHoldingPeriodMs: 60 * DAY,
    minHoldingPeriodMs: DAY,
    maxConcurrentPositions: 3,
    trailingStopEnabled: true,
    trailingStopPercentage: 0.05,
    sentimentWeight: 0.40,
    technicalWeight: 0.25,
    fundamentalWeight: 0.35,
    rebalanceIntervalMs: 7 * DAY,
    description:
      "The Advocate: Intuitive, values-aligned investing. Patient holder with strong conviction in chosen projects. Relies on narrative analysis and community sentiment.",
  }),

  [MbtiType.INFP]: createStrategy(MbtiType.INFP, {
    riskTolerance: 0.35,
    maxPositionSizePct: 0.06,
    maxLeverage: 2,
    defaultLeverage: 1,
    entryThreshold: 0.05,
    exitThreshold: 0.035,
    stopLossPercentage: 0.08,
    takeProfitPercentage: 0.30,
    maxHoldingPeriodMs: 90 * DAY,
    minHoldingPeriodMs: 3 * DAY,
    maxConcurrentPositions: 4,
    trailingStopEnabled: true,
    trailingStopPercentage: 0.06,
    sentimentWeight: 0.45,
    technicalWeight: 0.20,
    fundamentalWeight: 0.35,
    rebalanceIntervalMs: 14 * DAY,
    description:
      "The Mediator: Idealistic long-term holder. Invests in projects aligned with personal values. Low risk, high patience. Prefers community-driven tokens.",
  }),

  [MbtiType.ENFJ]: createStrategy(MbtiType.ENFJ, {
    riskTolerance: 0.55,
    maxPositionSizePct: 0.10,
    maxLeverage: 5,
    defaultLeverage: 2,
    entryThreshold: 0.025,
    exitThreshold: 0.02,
    stopLossPercentage: 0.05,
    takeProfitPercentage: 0.12,
    maxHoldingPeriodMs: 14 * DAY,
    minHoldingPeriodMs: 2 * HOUR,
    maxConcurrentPositions: 5,
    trailingStopEnabled: true,
    trailingStopPercentage: 0.03,
    sentimentWeight: 0.45,
    technicalWeight: 0.30,
    fundamentalWeight: 0.25,
    rebalanceIntervalMs: 3 * DAY,
    description:
      "The Protagonist: Social-signal driven trader. Follows community trends and influencer sentiment. Moderate risk with focus on popular, well-adopted tokens.",
  }),

  [MbtiType.ENFP]: createStrategy(MbtiType.ENFP, {
    riskTolerance: 0.65,
    maxPositionSizePct: 0.10,
    maxLeverage: 8,
    defaultLeverage: 3,
    entryThreshold: 0.02,
    exitThreshold: 0.015,
    stopLossPercentage: 0.06,
    takeProfitPercentage: 0.20,
    maxHoldingPeriodMs: 3 * DAY,
    minHoldingPeriodMs: HOUR,
    maxConcurrentPositions: 12,
    trailingStopEnabled: false,
    trailingStopPercentage: 0.04,
    dcaEnabled: true,
    dcaIntervalMs: 4 * HOUR,
    sentimentWeight: 0.50,
    technicalWeight: 0.25,
    fundamentalWeight: 0.25,
    rebalanceIntervalMs: 12 * HOUR,
    description:
      "The Campaigner: Enthusiastic trend chaser. Many concurrent positions across new narratives. FOMO-aware with built-in position limits. High energy, frequent trades.",
  }),

  [MbtiType.ISTJ]: createStrategy(MbtiType.ISTJ, {
    riskTolerance: 0.25,
    maxPositionSizePct: 0.05,
    maxLeverage: 2,
    defaultLeverage: 1,
    entryThreshold: 0.05,
    exitThreshold: 0.04,
    stopLossPercentage: 0.03,
    takeProfitPercentage: 0.08,
    maxHoldingPeriodMs: 90 * DAY,
    minHoldingPeriodMs: 7 * DAY,
    maxConcurrentPositions: 3,
    trailingStopEnabled: false,
    trailingStopPercentage: 0.02,
    dcaEnabled: true,
    dcaIntervalMs: 7 * DAY,
    sentimentWeight: 0.05,
    technicalWeight: 0.35,
    fundamentalWeight: 0.60,
    rebalanceIntervalMs: 30 * DAY,
    description:
      "The Logistician: Conservative, rule-based trader. Strict risk management. DCA into blue-chip tokens. Never chases. Fundamentals-first approach.",
  }),

  [MbtiType.ISFJ]: createStrategy(MbtiType.ISFJ, {
    riskTolerance: 0.20,
    maxPositionSizePct: 0.04,
    maxLeverage: 1,
    defaultLeverage: 1,
    entryThreshold: 0.06,
    exitThreshold: 0.05,
    stopLossPercentage: 0.03,
    takeProfitPercentage: 0.06,
    maxHoldingPeriodMs: 180 * DAY,
    minHoldingPeriodMs: 14 * DAY,
    maxConcurrentPositions: 2,
    trailingStopEnabled: false,
    trailingStopPercentage: 0.02,
    dcaEnabled: true,
    dcaIntervalMs: 14 * DAY,
    sentimentWeight: 0.10,
    technicalWeight: 0.25,
    fundamentalWeight: 0.65,
    rebalanceIntervalMs: 60 * DAY,
    description:
      "The Defender: Ultra-conservative capital preservation. Only top-tier tokens. Slow DCA strategy. Maximum safety with minimal drawdown tolerance.",
  }),

  [MbtiType.ESTJ]: createStrategy(MbtiType.ESTJ, {
    riskTolerance: 0.50,
    maxPositionSizePct: 0.12,
    maxLeverage: 5,
    defaultLeverage: 2,
    entryThreshold: 0.025,
    exitThreshold: 0.02,
    stopLossPercentage: 0.04,
    takeProfitPercentage: 0.10,
    maxHoldingPeriodMs: 14 * DAY,
    minHoldingPeriodMs: DAY,
    maxConcurrentPositions: 4,
    trailingStopEnabled: true,
    trailingStopPercentage: 0.025,
    sentimentWeight: 0.15,
    technicalWeight: 0.45,
    fundamentalWeight: 0.40,
    rebalanceIntervalMs: 3 * DAY,
    description:
      "The Executive: Structured, disciplined trader. Follows proven technical patterns. Moderate leverage with strict stop-losses. Well-organized portfolio management.",
  }),

  [MbtiType.ESFJ]: createStrategy(MbtiType.ESFJ, {
    riskTolerance: 0.35,
    maxPositionSizePct: 0.07,
    maxLeverage: 3,
    defaultLeverage: 1,
    entryThreshold: 0.03,
    exitThreshold: 0.025,
    stopLossPercentage: 0.04,
    takeProfitPercentage: 0.08,
    maxHoldingPeriodMs: 30 * DAY,
    minHoldingPeriodMs: 3 * DAY,
    maxConcurrentPositions: 4,
    trailingStopEnabled: true,
    trailingStopPercentage: 0.03,
    dcaEnabled: true,
    dcaIntervalMs: 3 * DAY,
    sentimentWeight: 0.50,
    technicalWeight: 0.25,
    fundamentalWeight: 0.25,
    rebalanceIntervalMs: 7 * DAY,
    description:
      "The Consul: Community-consensus trader. Follows popular picks with moderate risk. Consistent, steady returns over flashy gains. Social proof driven.",
  }),

  [MbtiType.ISTP]: createStrategy(MbtiType.ISTP, {
    riskTolerance: 0.60,
    maxPositionSizePct: 0.15,
    maxLeverage: 10,
    defaultLeverage: 4,
    entryThreshold: 0.015,
    exitThreshold: 0.01,
    stopLossPercentage: 0.03,
    takeProfitPercentage: 0.08,
    maxHoldingPeriodMs: DAY,
    minHoldingPeriodMs: 15 * 60_000,
    maxConcurrentPositions: 3,
    trailingStopEnabled: true,
    trailingStopPercentage: 0.015,
    sentimentWeight: 0.10,
    technicalWeight: 0.70,
    fundamentalWeight: 0.20,
    rebalanceIntervalMs: 6 * HOUR,
    description:
      "The Virtuoso: Precision day-trader. Quick in, quick out. Relies heavily on technical signals. High leverage, tight stops. Mechanical execution.",
  }),

  [MbtiType.ISFP]: createStrategy(MbtiType.ISFP, {
    riskTolerance: 0.30,
    maxPositionSizePct: 0.06,
    maxLeverage: 2,
    defaultLeverage: 1,
    entryThreshold: 0.04,
    exitThreshold: 0.03,
    stopLossPercentage: 0.06,
    takeProfitPercentage: 0.15,
    maxHoldingPeriodMs: 30 * DAY,
    minHoldingPeriodMs: DAY,
    maxConcurrentPositions: 5,
    trailingStopEnabled: true,
    trailingStopPercentage: 0.05,
    sentimentWeight: 0.35,
    technicalWeight: 0.30,
    fundamentalWeight: 0.35,
    rebalanceIntervalMs: 7 * DAY,
    description:
      "The Adventurer: Aesthetic-driven investor. Drawn to novel, creative projects. Low leverage, patient holding. Values unique tokenomics and design.",
  }),

  [MbtiType.ESTP]: createStrategy(MbtiType.ESTP, {
    riskTolerance: 0.85,
    maxPositionSizePct: 0.25,
    maxLeverage: 20,
    defaultLeverage: 7,
    entryThreshold: 0.01,
    exitThreshold: 0.008,
    stopLossPercentage: 0.02,
    takeProfitPercentage: 0.06,
    maxHoldingPeriodMs: 4 * HOUR,
    minHoldingPeriodMs: 5 * 60_000,
    maxConcurrentPositions: 4,
    trailingStopEnabled: true,
    trailingStopPercentage: 0.01,
    sentimentWeight: 0.30,
    technicalWeight: 0.60,
    fundamentalWeight: 0.10,
    rebalanceIntervalMs: HOUR,
    description:
      "The Entrepreneur: Maximum aggression scalper. Highest leverage, tightest timeframes. Lives for volatility. Quick reflexes with rapid position cycling.",
  }),

  [MbtiType.ESFP]: createStrategy(MbtiType.ESFP, {
    riskTolerance: 0.75,
    maxPositionSizePct: 0.15,
    maxLeverage: 10,
    defaultLeverage: 4,
    entryThreshold: 0.015,
    exitThreshold: 0.01,
    stopLossPercentage: 0.04,
    takeProfitPercentage: 0.10,
    maxHoldingPeriodMs: 2 * DAY,
    minHoldingPeriodMs: 30 * 60_000,
    maxConcurrentPositions: 8,
    trailingStopEnabled: false,
    trailingStopPercentage: 0.025,
    dcaEnabled: false,
    sentimentWeight: 0.55,
    technicalWeight: 0.30,
    fundamentalWeight: 0.15,
    rebalanceIntervalMs: 4 * HOUR,
    description:
      "The Entertainer: Hype-driven momentum trader. Rides social waves and trending tokens. High energy, many positions. Sentiment-first with quick exits.",
  }),
};

export function getStrategy(mbtiType: MbtiType): TradingStrategy {
  const strategy = MBTI_STRATEGIES[mbtiType];
  if (!strategy) {
    throw new Error(`Unknown MBTI type: ${mbtiType}`);
  }
  return strategy;
}

export function getStrategyDescription(mbtiType: MbtiType): string {
  return getStrategy(mbtiType).description;
}

export function getRiskCategory(
  mbtiType: MbtiType
): "conservative" | "moderate" | "aggressive" | "degen" {
  const tolerance = getStrategy(mbtiType).riskTolerance;
  if (tolerance <= 0.3) return "conservative";
  if (tolerance <= 0.55) return "moderate";
  if (tolerance <= 0.75) return "aggressive";
  return "degen";
}

export function calculatePositionSize(
  strategy: TradingStrategy,
  accountBalance: number,
  confidence: number
): number {
  const baseSize = accountBalance * strategy.maxPositionSizePct;
  const confidenceAdjusted = baseSize * Math.min(confidence, 1.0);
  const riskAdjusted = confidenceAdjusted * strategy.riskTolerance;
  return Math.max(riskAdjusted, 0);
}

export function shouldEnterTrade(
  strategy: TradingStrategy,
  signalStrength: number,
  currentPositions: number
): boolean {
  if (currentPositions >= strategy.maxConcurrentPositions) {
    return false;
  }
  return Math.abs(signalStrength) >= strategy.entryThreshold;
}

export function shouldExitTrade(
  strategy: TradingStrategy,
  unrealizedPnlPct: number,
  holdingDurationMs: number
): { shouldExit: boolean; reason: string } {
  if (unrealizedPnlPct <= -strategy.stopLossPercentage) {
    return { shouldExit: true, reason: "stop_loss_hit" };
  }

  if (unrealizedPnlPct >= strategy.takeProfitPercentage) {
    return { shouldExit: true, reason: "take_profit_hit" };
  }

  if (holdingDurationMs >= strategy.maxHoldingPeriodMs) {
    return { shouldExit: true, reason: "max_holding_period_exceeded" };
  }

  if (
    strategy.trailingStopEnabled &&
    unrealizedPnlPct > 0 &&
    unrealizedPnlPct < strategy.trailingStopPercentage
  ) {
    return { shouldExit: true, reason: "trailing_stop_triggered" };
  }

  return { shouldExit: false, reason: "" };
}

export function selectLeverage(
  strategy: TradingStrategy,
  volatility: number,
  confidence: number
): number {
  const baseMultiplier = confidence * (1 - volatility);
  const leverageRange = strategy.maxLeverage - 1;
  const calculatedLeverage = 1 + leverageRange * baseMultiplier;
  return Math.min(
    Math.max(Math.round(calculatedLeverage), 1),
    strategy.maxLeverage
  );
}

export function blendStrategies(
  primary: MbtiType,
  secondary: MbtiType,
  primaryWeight: number = 0.7
): TradingStrategy {
  const p = getStrategy(primary);
  const s = getStrategy(secondary);
  const sw = 1 - primaryWeight;

  return {
    mbtiType: primary,
    riskTolerance: p.riskTolerance * primaryWeight + s.riskTolerance * sw,
    maxPositionSizePct:
      p.maxPositionSizePct * primaryWeight + s.maxPositionSizePct * sw,
    maxLeverage: Math.round(
      p.maxLeverage * primaryWeight + s.maxLeverage * sw
    ),
    defaultLeverage: Math.round(
      p.defaultLeverage * primaryWeight + s.defaultLeverage * sw
    ),
    entryThreshold:
      p.entryThreshold * primaryWeight + s.entryThreshold * sw,
    exitThreshold:
      p.exitThreshold * primaryWeight + s.exitThreshold * sw,
    stopLossPercentage:
      p.stopLossPercentage * primaryWeight + s.stopLossPercentage * sw,
    takeProfitPercentage:
      p.takeProfitPercentage * primaryWeight + s.takeProfitPercentage * sw,
    maxHoldingPeriodMs: Math.round(
      p.maxHoldingPeriodMs * primaryWeight + s.maxHoldingPeriodMs * sw
    ),
    minHoldingPeriodMs: Math.round(
      p.minHoldingPeriodMs * primaryWeight + s.minHoldingPeriodMs * sw
    ),
    maxConcurrentPositions: Math.round(
      p.maxConcurrentPositions * primaryWeight +
        s.maxConcurrentPositions * sw
    ),
    trailingStopEnabled: p.trailingStopEnabled || s.trailingStopEnabled,
    trailingStopPercentage:
      p.trailingStopPercentage * primaryWeight +
      s.trailingStopPercentage * sw,
    dcaEnabled: p.dcaEnabled || s.dcaEnabled,
    dcaIntervalMs: Math.round(
      p.dcaIntervalMs * primaryWeight + s.dcaIntervalMs * sw
    ),
    sentimentWeight:
      p.sentimentWeight * primaryWeight + s.sentimentWeight * sw,
    technicalWeight:
      p.technicalWeight * primaryWeight + s.technicalWeight * sw,
    fundamentalWeight:
      p.fundamentalWeight * primaryWeight + s.fundamentalWeight * sw,
    rebalanceIntervalMs: Math.round(
      p.rebalanceIntervalMs * primaryWeight + s.rebalanceIntervalMs * sw
    ),
    description: `Blended strategy: ${primaryWeight * 100}% ${primary} / ${sw * 100}% ${secondary}`,
  };
}
