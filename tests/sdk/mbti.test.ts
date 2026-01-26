import { describe, it, expect } from '@jest/globals';
import {
  MBTIType,
  MBTIStrategy,
  getStrategyParams,
  getAllStrategies,
  validateParams,
  MBTI_TYPES,
} from '../../sdk/src/mbti';

describe('MBTI Strategy Parameters', () => {
  describe('MBTI_TYPES constant', () => {
    it('should contain exactly 16 types', () => {
      expect(MBTI_TYPES.length).toBe(16);
    });

    it('should include all analyst types', () => {
      expect(MBTI_TYPES).toContain(MBTIType.INTJ);
      expect(MBTI_TYPES).toContain(MBTIType.INTP);
      expect(MBTI_TYPES).toContain(MBTIType.ENTJ);
      expect(MBTI_TYPES).toContain(MBTIType.ENTP);
    });

    it('should include all diplomat types', () => {
      expect(MBTI_TYPES).toContain(MBTIType.INFJ);
      expect(MBTI_TYPES).toContain(MBTIType.INFP);
      expect(MBTI_TYPES).toContain(MBTIType.ENFJ);
      expect(MBTI_TYPES).toContain(MBTIType.ENFP);
    });

    it('should include all sentinel types', () => {
      expect(MBTI_TYPES).toContain(MBTIType.ISTJ);
      expect(MBTI_TYPES).toContain(MBTIType.ISFJ);
      expect(MBTI_TYPES).toContain(MBTIType.ESTJ);
      expect(MBTI_TYPES).toContain(MBTIType.ESFJ);
    });

    it('should include all explorer types', () => {
      expect(MBTI_TYPES).toContain(MBTIType.ISTP);
      expect(MBTI_TYPES).toContain(MBTIType.ISFP);
      expect(MBTI_TYPES).toContain(MBTIType.ESTP);
      expect(MBTI_TYPES).toContain(MBTIType.ESFP);
    });
  });

  describe('getStrategyParams', () => {
    it('should return valid params for every MBTI type', () => {
      for (const mbtiType of MBTI_TYPES) {
        const params = getStrategyParams(mbtiType);
        expect(params).toBeDefined();
        expect(params.riskTolerance).toBeGreaterThanOrEqual(0);
        expect(params.riskTolerance).toBeLessThanOrEqual(1);
        expect(params.maxPositionPct).toBeGreaterThan(0);
        expect(params.maxPositionPct).toBeLessThanOrEqual(0.5);
        expect(params.stopLossPct).toBeGreaterThan(0);
        expect(params.takeProfitPct).toBeGreaterThan(0);
        expect(params.rebalanceHours).toBeGreaterThanOrEqual(1);
        expect(params.entryAggression).toBeGreaterThanOrEqual(0);
        expect(params.entryAggression).toBeLessThanOrEqual(1);
      }
    });

    it('should throw for invalid MBTI type', () => {
      expect(() => getStrategyParams('XXXX' as MBTIType)).toThrow('Invalid MBTI type');
    });

    it('should return distinct params for each type', () => {
      const paramSets = MBTI_TYPES.map((t) => JSON.stringify(getStrategyParams(t)));
      const uniqueParams = new Set(paramSets);
      expect(uniqueParams.size).toBe(16);
    });
  });

  describe('INTJ strategy', () => {
    let params: MBTIStrategy;

    beforeAll(() => {
      params = getStrategyParams(MBTIType.INTJ);
    });

    it('should have high risk tolerance for strategic conviction', () => {
      expect(params.riskTolerance).toBeGreaterThanOrEqual(0.6);
      expect(params.riskTolerance).toBeLessThanOrEqual(0.7);
    });

    it('should have large max position for high conviction', () => {
      expect(params.maxPositionPct).toBeGreaterThanOrEqual(0.25);
    });

    it('should have long rebalance period', () => {
      expect(params.rebalanceHours).toBeGreaterThanOrEqual(48);
    });

    it('should have low entry aggression (waits for confirmation)', () => {
      expect(params.entryAggression).toBeLessThanOrEqual(0.4);
    });

    it('should weight trend indicators heavily', () => {
      expect(params.indicatorWeights.ema_200).toBeGreaterThanOrEqual(0.2);
      expect(params.indicatorWeights.macd).toBeGreaterThanOrEqual(0.2);
    });

    it('should have take-profit significantly higher than stop-loss', () => {
      expect(params.takeProfitPct / params.stopLossPct).toBeGreaterThan(2);
    });
  });

  describe('ISTJ strategy', () => {
    let params: MBTIStrategy;

    beforeAll(() => {
      params = getStrategyParams(MBTIType.ISTJ);
    });

    it('should have low risk tolerance for disciplined approach', () => {
      expect(params.riskTolerance).toBeLessThanOrEqual(0.3);
    });

    it('should have tight stop-loss', () => {
      expect(params.stopLossPct).toBeLessThanOrEqual(0.04);
    });

    it('should have very low entry aggression (maximum confirmation)', () => {
      expect(params.entryAggression).toBeLessThanOrEqual(0.2);
    });

    it('should weight classic indicators (EMA, MACD, RSI)', () => {
      const classicWeight =
        (params.indicatorWeights.ema_cross || 0) +
        (params.indicatorWeights.macd || 0) +
        (params.indicatorWeights.rsi || 0);
      expect(classicWeight).toBeGreaterThanOrEqual(0.5);
    });
  });

  describe('ESTP strategy', () => {
    let params: MBTIStrategy;

    beforeAll(() => {
      params = getStrategyParams(MBTIType.ESTP);
    });

    it('should have highest risk tolerance', () => {
      expect(params.riskTolerance).toBeGreaterThanOrEqual(0.85);
    });

    it('should have largest max position size', () => {
      expect(params.maxPositionPct).toBeGreaterThanOrEqual(0.35);
    });

    it('should have highest entry aggression', () => {
      expect(params.entryAggression).toBeGreaterThanOrEqual(0.9);
    });

    it('should have short rebalance period', () => {
      expect(params.rebalanceHours).toBeLessThanOrEqual(8);
    });

    it('should weight momentum and volume heavily', () => {
      expect(params.indicatorWeights.momentum).toBeGreaterThanOrEqual(0.2);
      expect(params.indicatorWeights.volume_spike).toBeGreaterThanOrEqual(0.2);
    });
  });

  describe('ISFJ strategy', () => {
    let params: MBTIStrategy;

    beforeAll(() => {
      params = getStrategyParams(MBTIType.ISFJ);
    });

    it('should have lowest risk tolerance', () => {
      expect(params.riskTolerance).toBeLessThanOrEqual(0.2);
    });

    it('should have tightest stop-loss', () => {
      expect(params.stopLossPct).toBeLessThanOrEqual(0.03);
    });

    it('should have smallest max position', () => {
      expect(params.maxPositionPct).toBeLessThanOrEqual(0.12);
    });

    it('should have lowest entry aggression', () => {
      expect(params.entryAggression).toBeLessThanOrEqual(0.1);
    });
  });

  describe('validateParams', () => {
    it('should accept valid parameters', () => {
      const params: MBTIStrategy = {
        riskTolerance: 0.5,
        maxPositionPct: 0.2,
        stopLossPct: 0.05,
        takeProfitPct: 0.15,
        rebalanceHours: 24,
        entryAggression: 0.5,
        indicatorWeights: { rsi: 0.5, macd: 0.5 },
      };
      expect(validateParams(params)).toBe(true);
    });

    it('should reject risk tolerance out of range', () => {
      const params: MBTIStrategy = {
        riskTolerance: 1.5,
        maxPositionPct: 0.2,
        stopLossPct: 0.05,
        takeProfitPct: 0.15,
        rebalanceHours: 24,
        entryAggression: 0.5,
        indicatorWeights: { rsi: 1.0 },
      };
      expect(validateParams(params)).toBe(false);
    });

    it('should reject indicator weights that do not sum to 1.0', () => {
      const params: MBTIStrategy = {
        riskTolerance: 0.5,
        maxPositionPct: 0.2,
        stopLossPct: 0.05,
        takeProfitPct: 0.15,
        rebalanceHours: 24,
        entryAggression: 0.5,
        indicatorWeights: { rsi: 0.3, macd: 0.3 }, // sums to 0.6
      };
      expect(validateParams(params)).toBe(false);
    });

    it('should reject negative stop-loss', () => {
      const params: MBTIStrategy = {
        riskTolerance: 0.5,
        maxPositionPct: 0.2,
        stopLossPct: -0.05,
        takeProfitPct: 0.15,
        rebalanceHours: 24,
        entryAggression: 0.5,
        indicatorWeights: { rsi: 1.0 },
      };
      expect(validateParams(params)).toBe(false);
    });

    it('should reject zero rebalance hours', () => {
      const params: MBTIStrategy = {
        riskTolerance: 0.5,
        maxPositionPct: 0.2,
        stopLossPct: 0.05,
        takeProfitPct: 0.15,
        rebalanceHours: 0,
        entryAggression: 0.5,
        indicatorWeights: { rsi: 1.0 },
      };
      expect(validateParams(params)).toBe(false);
    });
  });

  describe('getAllStrategies', () => {
    it('should return all 16 strategies', () => {
      const strategies = getAllStrategies();
      expect(Object.keys(strategies).length).toBe(16);
    });

    it('should have valid params for every strategy', () => {
      const strategies = getAllStrategies();
      for (const [type, params] of Object.entries(strategies)) {
        expect(validateParams(params)).toBe(true);
      }
    });
  });

  describe('risk ordering', () => {
    it('should order ISFJ < ISTJ < INTP < INTJ < ENTJ < ESTP by risk', () => {
      const isfj = getStrategyParams(MBTIType.ISFJ);
      const istj = getStrategyParams(MBTIType.ISTJ);
      const intp = getStrategyParams(MBTIType.INTP);
      const intj = getStrategyParams(MBTIType.INTJ);
      const entj = getStrategyParams(MBTIType.ENTJ);
      const estp = getStrategyParams(MBTIType.ESTP);

      expect(isfj.riskTolerance).toBeLessThan(istj.riskTolerance);
      expect(istj.riskTolerance).toBeLessThan(intp.riskTolerance);
      expect(intp.riskTolerance).toBeLessThan(intj.riskTolerance);
      expect(intj.riskTolerance).toBeLessThan(entj.riskTolerance);
      expect(entj.riskTolerance).toBeLessThan(estp.riskTolerance);
    });
  });
});
