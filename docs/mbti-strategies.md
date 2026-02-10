# MBTI Trading Strategies

## Overview

PIKKY maps each of the 16 MBTI personality types to a distinct trading strategy.
Each strategy defines risk parameters, indicator preferences, entry/exit logic,
and position sizing rules that reflect the cognitive style of that personality.

## Strategy Parameter Reference

| Parameter | Range | Description |
|-----------|-------|-------------|
| `risk_tolerance` | 0.0 - 1.0 | Willingness to accept drawdowns |
| `max_position_pct` | 0.01 - 0.50 | Maximum single position as % of portfolio |
| `stop_loss_pct` | 0.01 - 0.20 | Stop-loss trigger as % below entry |
| `take_profit_pct` | 0.02 - 0.50 | Take-profit trigger as % above entry |
| `rebalance_hours` | 1 - 168 | Hours between portfolio rebalances |
| `entry_aggression` | 0.0 - 1.0 | How early to enter (0 = wait for confirmation, 1 = immediate) |
| `indicator_weights` | object | Weighted preference for technical indicators |

---

## Analysts (NT)

### INTJ -- The Strategic Mastermind

**Personality**: Long-term visionary with a systematic approach. Trusts data
over emotion. Builds complex models and sticks to them with conviction.

**Trading Style**: Trend-following with macro overlay. Identifies major trends
early and holds through volatility. Rarely trades but takes large, high-conviction
positions.

**Parameters**:
```json
{
  "risk_tolerance": 0.65,
  "max_position_pct": 0.30,
  "stop_loss_pct": 0.08,
  "take_profit_pct": 0.25,
  "rebalance_hours": 72,
  "entry_aggression": 0.3,
  "indicator_weights": {
    "ema_200": 0.30,
    "macd": 0.25,
    "rsi": 0.15,
    "volume_profile": 0.20,
    "on_chain_metrics": 0.10
  }
}
```

**Entry Signal**: Price crosses above 200 EMA with MACD bullish crossover
confirmed by rising volume. Minimum 2 out of 3 confirmations required.

**Exit Signal**: MACD bearish divergence on weekly timeframe, or stop-loss hit.
Will not exit on minor pullbacks.

**Example Trade**:
- SOL at 95, 200 EMA at 92, MACD crosses bullish
- Entry: 95.50 (wait for confirmation candle)
- Position: 30% of portfolio
- Stop-loss: 87.86 (-8%)
- Take-profit: 119.38 (+25%)

---

### INTP -- The Analytical Theorist

**Personality**: Fascinated by patterns and systems. Constantly refining models.
Can over-analyze and miss opportunities. Excels at finding inefficiencies.

**Trading Style**: Mean reversion and statistical arbitrage. Looks for price
deviations from fair value models. Trades frequently but with small sizes.

**Parameters**:
```json
{
  "risk_tolerance": 0.40,
  "max_position_pct": 0.10,
  "stop_loss_pct": 0.04,
  "take_profit_pct": 0.06,
  "rebalance_hours": 12,
  "entry_aggression": 0.2,
  "indicator_weights": {
    "bollinger_bands": 0.30,
    "rsi": 0.25,
    "z_score": 0.25,
    "correlation": 0.10,
    "volatility": 0.10
  }
}
```

**Entry Signal**: Price exceeds 2 standard deviations from 20-period mean with
RSI in oversold/overbought territory. Z-score confirmation required.

**Exit Signal**: Price returns to mean (middle Bollinger Band) or time-based
exit after 24 hours if no reversion.

**Example Trade**:
- SOL at 88, Bollinger lower band at 89.50, RSI at 28
- Entry: 88.20 (oversold bounce)
- Position: 10% of portfolio
- Stop-loss: 84.67 (-4%)
- Take-profit: 93.49 (+6%)

---

### ENTJ -- The Commanding Executor

**Personality**: Decisive and action-oriented. Natural leader who trusts their
judgment. Aggressive when confident, disciplined when uncertain.

**Trading Style**: Breakout trading with momentum confirmation. Enters fast on
breakouts, scales into winners, cuts losers quickly. High trade frequency.

**Parameters**:
```json
{
  "risk_tolerance": 0.80,
  "max_position_pct": 0.35,
  "stop_loss_pct": 0.05,
  "take_profit_pct": 0.15,
  "rebalance_hours": 24,
  "entry_aggression": 0.8,
  "indicator_weights": {
    "breakout_level": 0.30,
    "volume": 0.25,
    "momentum": 0.20,
    "atr": 0.15,
    "order_flow": 0.10
  }
}
```

**Entry Signal**: Price breaks above resistance with volume spike (2x average).
Enters immediately on breakout candle close.

**Exit Signal**: Trailing stop at 1.5x ATR, or momentum divergence on 4h timeframe.

**Example Trade**:
- SOL breaks above 105 resistance with 3x volume
- Entry: 105.80 (immediate)
- Position: 35% of portfolio
- Stop-loss: 100.51 (-5%)
- Take-profit: 121.67 (+15%)

---

### ENTP -- The Contrarian Innovator

**Personality**: Loves to challenge consensus. Sees possibilities others miss.
Can be scattered across too many ideas. Thrives on intellectual debate.

**Trading Style**: Contrarian plays and narrative trading. Bets against crowded
trades, enters emerging narratives early. Manages a diversified set of
speculative positions.

**Parameters**:
```json
{
  "risk_tolerance": 0.70,
  "max_position_pct": 0.15,
  "stop_loss_pct": 0.10,
  "take_profit_pct": 0.30,
  "rebalance_hours": 48,
  "entry_aggression": 0.7,
  "indicator_weights": {
    "sentiment": 0.30,
    "funding_rate": 0.25,
    "open_interest": 0.20,
    "social_volume": 0.15,
    "price_action": 0.10
  }
}
```

**Entry Signal**: Extreme negative sentiment with funding rate deeply negative.
Social volume declining (crowd has given up). Enters against the crowd.

**Exit Signal**: Sentiment flips to positive (crowd agrees), or take-profit hit.

**Example Trade**:
- SOL sentiment at -0.8, funding rate -0.05%, social mentions down 60%
- Entry: 78.00 (contrarian long)
- Position: 15% of portfolio
- Stop-loss: 70.20 (-10%)
- Take-profit: 101.40 (+30%)

---
