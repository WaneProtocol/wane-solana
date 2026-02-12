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

## Diplomats (NF)

### INFJ -- The Intuitive Visionary

**Personality**: Combines intuition with conviction. Sees the big picture and
trusts gut feeling backed by research. Patient and disciplined.

**Trading Style**: Thematic investing with long hold periods. Identifies macro
narratives (DeFi summer, AI tokens) and builds positions early. Low frequency.

**Parameters**:
```json
{
  "risk_tolerance": 0.50,
  "max_position_pct": 0.25,
  "stop_loss_pct": 0.12,
  "take_profit_pct": 0.40,
  "rebalance_hours": 168,
  "entry_aggression": 0.3,
  "indicator_weights": {
    "tvl_growth": 0.25,
    "developer_activity": 0.25,
    "ema_50": 0.20,
    "narrative_score": 0.20,
    "whale_accumulation": 0.10
  }
}
```

**Entry Signal**: Rising developer activity and TVL growth in a sector, price
above 50 EMA, whale wallets accumulating. Enters gradually over days.

**Exit Signal**: Narrative exhaustion (declining developer activity) or fundamental
thesis breaks.

**Example Trade**:
- AI token sector TVL up 40%, dev commits up 3x, price above 50 EMA
- Entry: DCA over 5 days
- Position: 25% of portfolio
- Stop-loss: -12% from average entry
- Take-profit: +40% from average entry

---

### INFP -- The Idealistic Holder

**Personality**: Values-driven, drawn to projects with a mission. Emotional
attachment to holdings. Loyal to convictions but can hold losers too long.

**Trading Style**: Buy-and-hold with conviction-based entries. Researches project
fundamentals deeply. Rarely sells. Adds on dips for projects they believe in.

**Parameters**:
```json
{
  "risk_tolerance": 0.35,
  "max_position_pct": 0.20,
  "stop_loss_pct": 0.15,
  "take_profit_pct": 0.50,
  "rebalance_hours": 168,
  "entry_aggression": 0.2,
  "indicator_weights": {
    "fundamental_score": 0.35,
    "community_health": 0.25,
    "ema_200": 0.15,
    "token_distribution": 0.15,
    "rsi_weekly": 0.10
  }
}
```

**Entry Signal**: Strong fundamentals with healthy community metrics. Price near
200 EMA support. Weekly RSI not overbought. Enters slowly.

**Exit Signal**: Fundamental deterioration (team departure, security incident) or
extreme overvaluation. Wide stop-loss reflects conviction-based holding.

**Example Trade**:
- Project with 95/100 fundamental score, active community, price at 200 EMA
- Entry: DCA over 2 weeks
- Position: 20% of portfolio
- Stop-loss: -15% from average entry
- Take-profit: +50% from average entry

---

### ENFJ -- The Charismatic Leader

**Personality**: Reads market sentiment naturally. Understands crowd psychology.
Confident in trending markets, cautious at extremes. Inspires others.

**Trading Style**: Sentiment-driven trend following. Rides waves of enthusiasm
but exits before the crowd. Uses social metrics as primary indicators.

**Parameters**:
```json
{
  "risk_tolerance": 0.60,
  "max_position_pct": 0.25,
  "stop_loss_pct": 0.07,
  "take_profit_pct": 0.20,
  "rebalance_hours": 48,
  "entry_aggression": 0.6,
  "indicator_weights": {
    "social_sentiment": 0.30,
    "trending_score": 0.25,
    "volume_momentum": 0.20,
    "ema_20": 0.15,
    "whale_tracking": 0.10
  }
}
```

**Entry Signal**: Rising social sentiment with price above 20 EMA. Volume
momentum increasing. Whale wallets adding positions.

**Exit Signal**: Social sentiment peaks (leading indicator), volume declining,
or smart money exiting.

**Example Trade**:
- Token trending on social with sentiment +0.7, price above 20 EMA
- Entry: 42.00 (enter with trend)
- Position: 25% of portfolio
- Stop-loss: 39.06 (-7%)
- Take-profit: 50.40 (+20%)

---

### ENFP -- The Enthusiastic Explorer

**Personality**: Energetic and opportunity-driven. Jumps on new ideas with
enthusiasm. Can spread too thin across many positions. Optimistic bias.

**Trading Style**: Momentum breakout with narrative chasing. Enters fast on
momentum signals, diversifies across many small bets. Accepts high failure
rate for occasional big wins.

**Parameters**:
```json
{
  "risk_tolerance": 0.75,
  "max_position_pct": 0.08,
  "stop_loss_pct": 0.06,
  "take_profit_pct": 0.20,
  "rebalance_hours": 12,
  "entry_aggression": 0.9,
  "indicator_weights": {
    "momentum": 0.30,
    "new_listing_score": 0.25,
    "social_buzz": 0.20,
    "volume_spike": 0.15,
    "rsi": 0.10
  }
}
```

**Entry Signal**: Momentum breakout with social buzz. New narratives or listings.
Volume spike above 3x average. Enters almost immediately.

**Exit Signal**: Momentum fades (RSI divergence) or stop-loss hit. Quick to move
to next opportunity.

**Example Trade**:
- New listing with 5x volume, social buzz score 0.9
- Entry: Immediate on signal
- Position: 8% of portfolio (many small bets)
- Stop-loss: -6%
- Take-profit: +20%

---

## Sentinels (SJ)

### ISTJ -- The Disciplined Guardian

**Personality**: Methodical, reliable, and risk-averse. Follows rules without
exception. Prefers proven strategies over innovation. Extremely consistent.

**Trading Style**: Systematic trend following with strict rules. Uses only
well-tested indicators. Never deviates from the plan. Low drawdown focus.

**Parameters**:
```json
{
  "risk_tolerance": 0.25,
  "max_position_pct": 0.15,
  "stop_loss_pct": 0.03,
  "take_profit_pct": 0.08,
  "rebalance_hours": 24,
  "entry_aggression": 0.1,
  "indicator_weights": {
    "ema_cross": 0.30,
    "macd": 0.25,
    "rsi": 0.20,
    "atr": 0.15,
    "volume": 0.10
  }
}
```

**Entry Signal**: 20/50 EMA golden cross with MACD confirmation and RSI between
40-60. All three must confirm. No exceptions.

**Exit Signal**: 20/50 EMA death cross or stop-loss. Never holds through a
death cross regardless of other signals.

**Example Trade**:
- SOL 20 EMA crosses above 50 EMA, MACD bullish, RSI at 52
- Entry: 100.00 (after all confirmations)
- Position: 15% of portfolio
- Stop-loss: 97.00 (-3%)
- Take-profit: 108.00 (+8%)

---

### ISFJ -- The Protective Conservator

**Personality**: Cautious and protective of capital. Prioritizes preservation
over growth. Thorough researcher who needs high confidence before acting.

**Trading Style**: Ultra-conservative with focus on capital preservation. Only
trades blue-chip assets. Uses wide time frames. Minimal trading frequency.

**Parameters**:
```json
{
  "risk_tolerance": 0.15,
  "max_position_pct": 0.10,
  "stop_loss_pct": 0.02,
  "take_profit_pct": 0.05,
  "rebalance_hours": 168,
  "entry_aggression": 0.05,
  "indicator_weights": {
    "ema_200": 0.30,
    "rsi_weekly": 0.25,
    "support_level": 0.20,
    "volume_trend": 0.15,
    "volatility_low": 0.10
  }
}
```

**Entry Signal**: Price at strong support with weekly RSI oversold, above 200 EMA
on monthly. Volatility must be below average. Maximum confirmation required.

**Exit Signal**: Any sign of weakness -- price below 200 EMA weekly, or stop-loss.
Exits early and asks questions later.

**Example Trade**:
- SOL at major support 90, weekly RSI 25, monthly above 200 EMA, low vol
- Entry: 90.50 (maximum confirmation)
- Position: 10% of portfolio
- Stop-loss: 88.69 (-2%)
- Take-profit: 95.03 (+5%)

---

### ESTJ -- The Efficient Manager

**Personality**: Organized and decisive. Values efficiency and measurable results.
Sets clear targets and executes methodically. Respects hierarchy and structure.

**Trading Style**: Rule-based swing trading. Clear entry/exit rules with no
discretion. Measures performance rigorously. Optimizes for risk-adjusted returns.

**Parameters**:
```json
{
  "risk_tolerance": 0.45,
  "max_position_pct": 0.20,
  "stop_loss_pct": 0.04,
  "take_profit_pct": 0.10,
  "rebalance_hours": 48,
  "entry_aggression": 0.4,
  "indicator_weights": {
    "pivot_points": 0.25,
    "macd": 0.25,
    "volume": 0.20,
    "ema_50": 0.15,
    "atr": 0.15
  }
}
```

**Entry Signal**: Price bounces off pivot support with MACD turning bullish.
Volume above average. Price above 50 EMA.

**Exit Signal**: Pivot resistance reached (take-profit) or stop-loss hit.
Strict time-based exit if neither hit within 5 days.

**Example Trade**:
- SOL bounces off S1 pivot at 96, MACD turns up, volume 1.5x avg
- Entry: 96.50
- Position: 20% of portfolio
- Stop-loss: 92.64 (-4%)
- Take-profit: 106.15 (+10%)

---

### ESFJ -- The Community Trader

**Personality**: Socially aware and consensus-driven. Pays attention to what
others are doing. Harmonious approach to risk. Follows trusted leaders.

**Trading Style**: Social copy-trading with safety filters. Follows whale
wallets and influencer trades but applies conservative risk management.
Consensus-based entry decisions.

**Parameters**:
```json
{
  "risk_tolerance": 0.35,
  "max_position_pct": 0.12,
  "stop_loss_pct": 0.05,
  "take_profit_pct": 0.10,
  "rebalance_hours": 24,
  "entry_aggression": 0.5,
  "indicator_weights": {
    "whale_activity": 0.30,
    "social_consensus": 0.25,
    "ema_20": 0.20,
    "rsi": 0.15,
    "volume": 0.10
  }
}
```

**Entry Signal**: Multiple whale wallets buying the same asset. Social consensus
is bullish. Price above 20 EMA with RSI not overbought.

**Exit Signal**: Whales start selling, or social consensus shifts bearish.

**Example Trade**:
- 5+ whale wallets accumulating token, bullish social consensus
- Entry: Follow whale average entry price
- Position: 12% of portfolio
- Stop-loss: -5%
- Take-profit: +10%

---

## Explorers (SP)

### ISTP -- The Tactical Mechanic

**Personality**: Cool under pressure. Analytical and hands-on. Reacts quickly to
changing conditions. Independent thinker who trusts their own analysis.

**Trading Style**: Scalping and short-term technical trading. Reads price action
and order flow. Rapid entries and exits. Thrives in volatile markets.

**Parameters**:
```json
{
  "risk_tolerance": 0.55,
  "max_position_pct": 0.20,
  "stop_loss_pct": 0.02,
  "take_profit_pct": 0.04,
  "rebalance_hours": 4,
  "entry_aggression": 0.7,
  "indicator_weights": {
    "order_flow": 0.30,
    "price_action": 0.25,
    "vwap": 0.20,
    "rsi_5min": 0.15,
    "spread": 0.10
  }
}
```

**Entry Signal**: Order flow imbalance with price at VWAP support/resistance.
5-minute RSI at extremes. Tight spread indicating liquidity.

**Exit Signal**: Quick take-profit at 2R or stop-loss. No holding overnight.

**Example Trade**:
- SOL bid/ask imbalance 3:1 at VWAP 100.00, 5m RSI at 22
- Entry: 100.10
- Position: 20% of portfolio
- Stop-loss: 98.10 (-2%)
- Take-profit: 104.10 (+4%)

---

### ISFP -- The Artistic Trader

**Personality**: Quietly observant with strong aesthetic sense. Sees patterns
others miss. Flexible and adaptable but avoids conflict and high stress.

**Trading Style**: Pattern recognition on charts. Identifies harmonic patterns,
head-and-shoulders, wedges. Prefers clean setups with clear invalidation levels.

**Parameters**:
```json
{
  "risk_tolerance": 0.30,
  "max_position_pct": 0.12,
  "stop_loss_pct": 0.03,
  "take_profit_pct": 0.09,
  "rebalance_hours": 24,
  "entry_aggression": 0.3,
  "indicator_weights": {
    "chart_pattern": 0.35,
    "fibonacci": 0.25,
    "rsi": 0.15,
    "volume_confirm": 0.15,
    "support_resistance": 0.10
  }
}
```

**Entry Signal**: Clean chart pattern completion (e.g., bull flag breakout) at
Fibonacci level with volume confirmation.

**Exit Signal**: Pattern target reached (measured move) or pattern invalidation.

**Example Trade**:
- SOL forms bull flag at 61.8% Fibonacci retracement, breakout with volume
- Entry: At breakout with volume confirmation
- Position: 12% of portfolio
- Stop-loss: Below flag low (-3%)
- Take-profit: Measured move target (+9%)

---

### ESTP -- The Bold Opportunist

**Personality**: Action-first, thinks-later. Thrives on excitement and risk.
Quick decision maker. Comfortable with large positions and volatility.

**Trading Style**: Aggressive momentum trading. Largest position sizes, fastest
entries. Accepts high drawdowns for high returns. Trades the most volatile assets.

**Parameters**:
```json
{
  "risk_tolerance": 0.90,
  "max_position_pct": 0.40,
  "stop_loss_pct": 0.06,
  "take_profit_pct": 0.15,
  "rebalance_hours": 6,
  "entry_aggression": 0.95,
  "indicator_weights": {
    "momentum": 0.30,
    "volume_spike": 0.25,
    "volatility_high": 0.20,
    "rsi": 0.15,
    "price_velocity": 0.10
  }
}
```

**Entry Signal**: Extreme momentum with volume explosion. Does not wait for
confirmation. Enters on first sign of breakout.

**Exit Signal**: Trailing stop at 2x ATR or momentum exhaustion. Takes profits
aggressively.

**Example Trade**:
- SOL gaps up 5% with 10x volume at market open
- Entry: Immediate (within seconds)
- Position: 40% of portfolio
- Stop-loss: -6%
- Take-profit: +15%

---

### ESFP -- The Energetic Performer

**Personality**: Lives in the moment. Social and fun-loving. Follows trends and
hype. Short attention span but great at riding waves while they last.

**Trading Style**: Hype-driven trading with quick rotations. Follows social
trends, enters meme coins and trending tokens. Short holding periods.
Diversifies across many trending assets.

**Parameters**:
```json
{
  "risk_tolerance": 0.70,
  "max_position_pct": 0.06,
  "stop_loss_pct": 0.08,
  "take_profit_pct": 0.25,
  "rebalance_hours": 6,
  "entry_aggression": 0.85,
  "indicator_weights": {
    "trending_score": 0.35,
    "social_volume": 0.25,
    "price_momentum": 0.20,
    "new_pairs": 0.10,
    "volume": 0.10
  }
}
```

**Entry Signal**: Token is trending on social platforms with rising volume. New
pair with strong initial momentum. Enters fast, exits faster.

**Exit Signal**: Trend fading (social volume declining) or next shiny opportunity
appears. Very short holding period (hours to days).

**Example Trade**:
- New trending token with 100x social volume increase
- Entry: Immediate on trend detection
- Position: 6% of portfolio (many small bets)
- Stop-loss: -8%
- Take-profit: +25%

---

## Strategy Comparison Matrix

| Type | Risk | Max Pos | Stop | Target | Rebal (h) | Style |
|------|------|---------|------|--------|-----------|-------|
| INTJ | 0.65 | 30% | 8% | 25% | 72 | Trend following |
| INTP | 0.40 | 10% | 4% | 6% | 12 | Mean reversion |
| ENTJ | 0.80 | 35% | 5% | 15% | 24 | Breakout |
| ENTP | 0.70 | 15% | 10% | 30% | 48 | Contrarian |
| INFJ | 0.50 | 25% | 12% | 40% | 168 | Thematic |
| INFP | 0.35 | 20% | 15% | 50% | 168 | Buy and hold |
| ENFJ | 0.60 | 25% | 7% | 20% | 48 | Sentiment trend |
| ENFP | 0.75 | 8% | 6% | 20% | 12 | Momentum |
| ISTJ | 0.25 | 15% | 3% | 8% | 24 | Systematic |
| ISFJ | 0.15 | 10% | 2% | 5% | 168 | Conservative |
| ESTJ | 0.45 | 20% | 4% | 10% | 48 | Swing trading |
| ESFJ | 0.35 | 12% | 5% | 10% | 24 | Social copy |
| ISTP | 0.55 | 20% | 2% | 4% | 4 | Scalping |
| ISFP | 0.30 | 12% | 3% | 9% | 24 | Pattern trading |
| ESTP | 0.90 | 40% | 6% | 15% | 6 | Aggressive momentum |
| ESFP | 0.70 | 6% | 8% | 25% | 6 | Hype trading |

## Risk-Return Profiles

Sorted by risk tolerance (low to high):

1. **ISFJ** (0.15) -- Capital preservation, minimal trading
2. **ISTJ** (0.25) -- Disciplined rules, low drawdown
3. **ISFP** (0.30) -- Pattern-based, moderate caution
4. **INFP** (0.35) -- Conviction holding, wide stops
5. **ESFJ** (0.35) -- Social consensus, safety filters
6. **INTP** (0.40) -- Statistical edge, small positions
7. **ESTJ** (0.45) -- Efficient rules, measured risk
8. **INFJ** (0.50) -- Thematic conviction, patient
9. **ISTP** (0.55) -- Tactical precision, tight stops
10. **ENFJ** (0.60) -- Sentiment reading, crowd-aware
11. **INTJ** (0.65) -- Strategic vision, large positions
12. **ENTP** (0.70) -- Contrarian bets, diversified
13. **ESFP** (0.70) -- Hype riding, many small bets
14. **ENFP** (0.75) -- Momentum chasing, scattered
15. **ENTJ** (0.80) -- Decisive breakouts, aggressive
16. **ESTP** (0.90) -- Maximum aggression, highest risk
