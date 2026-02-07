# x402 Protocol Specification

## Overview

x402 is an HTTP-native payment protocol that leverages the HTTP 402 Payment
Required status code to enable machine-to-machine payments on Solana. PIKKY
uses x402 to gate access to premium AI trading features behind verifiable
on-chain payments.

## Protocol Version

Current version: **x402/1.0**

## Motivation

Traditional API monetization relies on API keys, subscriptions, and centralized
billing infrastructure. x402 replaces this with per-request on-chain payments:

- No accounts or signup required
- Pay-per-use granularity
- Verifiable on-chain receipts
- Machine-to-machine native
- No chargebacks or payment disputes

## HTTP 402 Flow

### Step 1: Client Makes Request

```http
GET /api/agent/trade HTTP/1.1
Host: api.pikky.sol
Accept: application/json
```

### Step 2: Server Returns 402

When payment is required, the server responds with HTTP 402 and payment
instructions in headers:

```http
HTTP/1.1 402 Payment Required
Content-Type: application/json
X-Payment-Version: x402/1.0
X-Payment-Network: solana:mainnet-beta
X-Payment-Amount: 10000000
X-Payment-Token-Mint: So11111111111111111111111111111111111111112
X-Payment-Address: PikkyVau1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
X-Payment-Nonce: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6
X-Payment-Expires: 1735689600
X-Payment-Description: AI trade execution - ENFP momentum strategy
X-Payment-Receipt-Schema: solana:transaction

{
  "error": "payment_required",
  "message": "Payment required to execute trade",
  "payment": {
    "amount": 10000000,
    "amount_display": "0.01 SOL",
    "token_mint": "So11111111111111111111111111111111111111112",
    "address": "PikkyVau1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
    "nonce": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "expires_at": 1735689600,
    "network": "solana:mainnet-beta"
  }
}
```

### Step 3: Client Submits Payment

The client constructs and submits a Solana transaction:

```
Transaction:
  - Transfer `amount` of `token_mint` to `address`
  - Include memo instruction with `nonce`
  - Sign with client wallet
```

### Step 4: Client Retries with Proof

```http
GET /api/agent/trade HTTP/1.1
Host: api.pikky.sol
Accept: application/json
X-Payment-Signature: 5UfDuX...txSignature
X-Payment-Nonce: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6
```

### Step 5: Server Verifies and Responds

```http
HTTP/1.1 200 OK
Content-Type: application/json
X-Payment-Receipt: 5UfDuX...txSignature
X-Payment-Status: verified

{
  "trade": {
    "id": "trade_abc123",
    "pair": "SOL/USDC",
    "side": "buy",
    "amount": 1.5,
    "price": 142.50,
    "status": "executed"
  }
}
```
