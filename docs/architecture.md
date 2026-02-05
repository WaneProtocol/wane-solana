# PIKKY System Architecture

## Overview

PIKKY is an x402-based Solana auto-trading AI agent that uses MBTI personality
types to drive trading strategies. The system consists of three primary layers:

1. **On-Chain Program** -- Solana program managing funds, trade execution, and x402 payment verification
2. **TypeScript SDK** -- Client library for interacting with the on-chain program
3. **Python Agent** -- AI-powered trading engine implementing MBTI-based strategies

## High-Level Architecture

```mermaid
graph TB
    subgraph Client Layer
        CLI[CLI Tool]
        SDK[TypeScript SDK]
        API[REST API]
    end

    subgraph Agent Layer
        ENGINE[Trading Engine]
        MBTI[MBTI Strategy Selector]
        MARKET[Market Data Feed]
        SIGNALS[Signal Generator]
        RISK[Risk Manager]
    end

    subgraph Protocol Layer
        X402[x402 Payment Handler]
        TX[Transaction Builder]
        VERIFY[Payment Verifier]
    end

    subgraph Solana
        PROGRAM[PIKKY Program]
        VAULT[Token Vault PDA]
        STATE[User State PDA]
        CONFIG[Config PDA]
        DEX[Jupiter / Raydium]
    end

    CLI --> SDK
    API --> SDK
    SDK --> X402
    SDK --> TX
    X402 --> VERIFY
    TX --> PROGRAM
    VERIFY --> PROGRAM
    PROGRAM --> VAULT
    PROGRAM --> STATE
    PROGRAM --> CONFIG
    PROGRAM --> DEX

    ENGINE --> MBTI
    ENGINE --> MARKET
    ENGINE --> SIGNALS
    ENGINE --> RISK
    ENGINE --> SDK
    MBTI --> SIGNALS
    MARKET --> SIGNALS
```

## x402 Payment Flow

The x402 protocol enables HTTP 402 Payment Required flows for accessing
premium trading features and AI agent services.

```mermaid
sequenceDiagram
    participant C as Client
    participant S as PIKKY Server
    participant P as PIKKY Program
    participant SOL as Solana Network

    C->>S: GET /api/agent/trade
    S-->>C: 402 Payment Required<br/>X-Payment-Amount: 0.01 SOL<br/>X-Payment-Address: {vault}<br/>X-Payment-Token: {nonce}

    C->>SOL: Transfer 0.01 SOL to vault<br/>with nonce in memo
    SOL-->>C: Transaction signature

    C->>S: GET /api/agent/trade<br/>X-Payment-Signature: {tx_sig}<br/>X-Payment-Token: {nonce}

    S->>P: verify_payment(tx_sig, nonce)
    P->>SOL: Verify transaction
    SOL-->>P: Confirmed
    P-->>S: Payment valid

    S->>S: Execute trade logic
    S-->>C: 200 OK<br/>{trade_result}
```

### Payment Header Specification

| Header | Direction | Description |
|--------|-----------|-------------|
| `X-Payment-Amount` | Response | Required payment amount in lamports |
| `X-Payment-Address` | Response | Destination vault address |
| `X-Payment-Token` | Both | Unique nonce for replay protection |
| `X-Payment-Signature` | Request | Solana transaction signature |
| `X-Payment-Network` | Response | Solana network (mainnet-beta, devnet) |

## MBTI Strategy Selection Pipeline

```mermaid
flowchart LR
    subgraph Input
        USER[User Config]
        MBTI_TYPE[MBTI Type]
        MARKET_DATA[Market Data]
    end

    subgraph Strategy Selection
        SELECTOR[Strategy Selector]
        PARAMS[Parameter Generator]
    end

    subgraph Strategy Execution
        ANALYZE[Market Analysis]
        SIGNAL[Signal Generation]
        RISK_CHECK[Risk Check]
        EXECUTE[Trade Execution]
    end

    subgraph Output
        TRADE[Trade Result]
        PNL[PnL Update]
    end

    USER --> SELECTOR
    MBTI_TYPE --> SELECTOR
    SELECTOR --> PARAMS
    MARKET_DATA --> ANALYZE
    PARAMS --> ANALYZE
    ANALYZE --> SIGNAL
    SIGNAL --> RISK_CHECK
    RISK_CHECK --> EXECUTE
    EXECUTE --> TRADE
    TRADE --> PNL
```

Each MBTI type maps to a distinct set of trading parameters:

- **Risk tolerance** (0.0 - 1.0)
- **Position sizing** (percentage of portfolio)
- **Entry aggressiveness** (how early to enter)
- **Exit strategy** (stop-loss and take-profit ratios)
- **Rebalance frequency**
- **Indicator weights** (which technical indicators to prioritize)

## Trade Execution Pipeline

```mermaid
sequenceDiagram
    participant E as Trading Engine
    participant S as Strategy
    participant R as Risk Manager
    participant SDK as TypeScript SDK
    participant P as PIKKY Program
    participant DEX as Jupiter Aggregator

    E->>E: Fetch market data (price, volume, orderbook)
    E->>S: analyze(market_data, mbti_params)
    S-->>E: TradeSignal(BUY, SOL/USDC, size=0.5)

    E->>R: validate(signal, portfolio_state)
    R-->>E: Approved (within risk limits)

    E->>SDK: execute_trade(signal)
    SDK->>P: execute_swap instruction
    P->>DEX: CPI: swap(input_mint, output_mint, amount)
    DEX-->>P: Swap result
    P->>P: Update user state PDA
    P-->>SDK: Transaction confirmed
    SDK-->>E: TradeResult(success, fill_price, fees)

    E->>E: Update PnL tracking
    E->>E: Log trade to history
```

## Account Structure (PDAs)

```mermaid
classDiagram
    class GlobalConfig {
        +Pubkey authority
        +u64 protocol_fee_bps
        +u64 total_users
        +u64 total_volume
        +bool paused
    }

    class UserState {
        +Pubkey owner
        +u8 mbti_type
        +u64 deposited_amount
        +u64 current_balance
        +i64 realized_pnl
        +i64 unrealized_pnl
        +u64 total_trades
        +u64 winning_trades
        +i64 last_trade_timestamp
        +bool auto_trade_enabled
    }

    class TradeHistory {
        +Pubkey user
        +u8 trade_type
        +Pubkey input_mint
        +Pubkey output_mint
        +u64 input_amount
        +u64 output_amount
        +u64 fee_amount
        +i64 timestamp
        +u8 mbti_type_at_trade
    }

    class PaymentRecord {
        +Pubkey payer
        +u64 amount
        +[u8; 32] nonce
        +i64 timestamp
        +bool consumed
    }

    GlobalConfig "1" --> "*" UserState : has many
    UserState "1" --> "*" TradeHistory : has many
    UserState "1" --> "*" PaymentRecord : has many
```

### PDA Seeds

| Account | Seeds | Bump |
|---------|-------|------|
| GlobalConfig | `["config"]` | canonical |
| UserState | `["user", owner.key()]` | canonical |
| TradeHistory | `["trade", user.key(), trade_index.to_le_bytes()]` | canonical |
| PaymentRecord | `["payment", payer.key(), nonce]` | canonical |
| TokenVault | `["vault", mint.key()]` | canonical |

## Component Interactions

```mermaid
graph LR
    subgraph programs/
        LIB[lib.rs]
        INST[instructions/]
        STATE_MOD[state/]
        X402_MOD[x402.rs]
        ERR[errors.rs]
    end

    subgraph sdk/
        CLIENT[client.ts]
        X402_TS[x402.ts]
        MBTI_TS[mbti.ts]
        TYPES[types.ts]
    end

    subgraph agent/
        ENGINE_PY[engine.py]
        STRAT[strategies.py]
        X402_PY[x402_handler.py]
        MKT[market.py]
    end

    CLIENT --> LIB
    X402_TS --> X402_MOD
    ENGINE_PY --> CLIENT
    STRAT --> MBTI_TS
    X402_PY --> X402_TS
    MKT --> ENGINE_PY
```

## Network Topology

```
                    Internet
                       |
            +----------+----------+
            |                     |
      Solana RPC             PIKKY API
      (mainnet/devnet)       (REST + WS)
            |                     |
            |              +------+------+
            |              |             |
            |         Agent Engine   x402 Handler
            |              |             |
            +--------------+-------------+
                           |
                     PIKKY Program
                     (on-chain)
                           |
                  +--------+--------+
                  |        |        |
               Vault    States   History
```

## Data Flow Summary

1. User deposits SOL/tokens via SDK into on-chain vault.
2. User sets MBTI personality type on their UserState PDA.
3. User enables auto-trading via SDK or CLI.
4. Agent engine polls market data continuously.
5. MBTI strategy generates signals based on personality parameters.
6. Risk manager validates signals against portfolio constraints.
7. Approved trades execute via CPI to Jupiter/Raydium.
8. Trade results update UserState PDA with new balances and PnL.
9. Premium features require x402 payment before access.
10. All trades are recorded in TradeHistory PDAs for auditability.
