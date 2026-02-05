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
