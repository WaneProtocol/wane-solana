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
