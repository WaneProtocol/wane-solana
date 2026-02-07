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

## Payment Headers

### Response Headers (402)

| Header | Required | Type | Description |
|--------|----------|------|-------------|
| `X-Payment-Version` | Yes | String | Protocol version (`x402/1.0`) |
| `X-Payment-Network` | Yes | String | Network identifier (`solana:mainnet-beta`, `solana:devnet`) |
| `X-Payment-Amount` | Yes | Integer | Payment amount in smallest unit (lamports for SOL) |
| `X-Payment-Token-Mint` | Yes | String | SPL token mint address (native SOL uses wrapped SOL mint) |
| `X-Payment-Address` | Yes | String | Destination address (base58-encoded) |
| `X-Payment-Nonce` | Yes | String | Unique 32-byte hex nonce for replay protection |
| `X-Payment-Expires` | Yes | Integer | Unix timestamp when payment offer expires |
| `X-Payment-Description` | No | String | Human-readable description of the service |
| `X-Payment-Receipt-Schema` | No | String | Expected receipt format |

### Request Headers (Retry)

| Header | Required | Type | Description |
|--------|----------|------|-------------|
| `X-Payment-Signature` | Yes | String | Solana transaction signature (base58) |
| `X-Payment-Nonce` | Yes | String | Same nonce from the 402 response |

### Response Headers (200 with Receipt)

| Header | Required | Type | Description |
|--------|----------|------|-------------|
| `X-Payment-Receipt` | Yes | String | Transaction signature as receipt |
| `X-Payment-Status` | Yes | String | `verified` or `pending` |

## Payment Verification

### On-Chain Verification

The PIKKY program verifies payments through the following process:

```
1. Parse transaction from signature
2. Verify transaction is finalized (commitment: confirmed)
3. Check transfer instruction:
   a. Destination matches vault PDA
   b. Amount >= required amount
   c. Token mint matches expected mint
4. Check memo instruction:
   a. Contains expected nonce
5. Verify nonce has not been consumed:
   a. Check PaymentRecord PDA does not exist
   b. Create PaymentRecord PDA to mark as consumed
6. Verify timestamp:
   a. Transaction slot timestamp <= expiry time
```

### Verification States

| State | Description |
|-------|-------------|
| `verified` | Payment confirmed on-chain, nonce consumed |
| `pending` | Transaction submitted but not yet confirmed |
| `expired` | Nonce expired before payment was submitted |
| `invalid` | Transaction does not match payment requirements |
| `replayed` | Nonce has already been consumed |

## Nonce Management

Nonces provide replay protection. Each nonce is a random 32-byte value
represented as a 64-character hex string.

### Nonce Lifecycle

```
Generated (server) --> Issued (402 response) --> Consumed (verification)
                                             --> Expired (timeout)
```

### Nonce Storage

Consumed nonces are stored as PDAs on-chain:

```
Seeds: ["payment", payer_pubkey, nonce_bytes]
```

This ensures:
- Each nonce can only be used once (PDA creation fails if it exists)
- Verification is trustless and on-chain
- No off-chain database required for nonce tracking

## Pricing

### Endpoint Pricing Table

| Endpoint | Cost | Description |
|----------|------|-------------|
| `POST /api/agent/trade` | 0.01 SOL | Execute a single trade |
| `POST /api/agent/analyze` | 0.005 SOL | Market analysis without execution |
| `GET /api/agent/signals` | 0.002 SOL | Get current trade signals |
| `POST /api/agent/strategy` | 0.001 SOL | Get MBTI strategy parameters |
| `GET /api/agent/portfolio` | Free | View portfolio status |
| `POST /api/deposit` | Free | Deposit funds |
| `POST /api/withdraw` | Free | Withdraw funds |

### Dynamic Pricing

Prices may be adjusted based on:
- Network congestion (higher fees during high-traffic periods)
- Computational complexity of the request
- Market volatility conditions

Dynamic pricing is communicated through the `X-Payment-Amount` header
in each 402 response.

## Solana Integration

### Transaction Construction

Clients must construct a Solana transaction with the following instructions:

1. **Transfer instruction**: Move tokens from payer to vault
   - For native SOL: `SystemProgram.transfer`
   - For SPL tokens: `Token.transfer`

2. **Memo instruction**: Include nonce for identification
   - Program: `MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr`
   - Data: nonce bytes (UTF-8 encoded hex string)

### Example Transaction (TypeScript)

```typescript
import { Transaction, SystemProgram } from '@solana/web3.js';
import { createMemoInstruction } from '@solana/spl-memo';

const transaction = new Transaction();

// Transfer payment
transaction.add(
  SystemProgram.transfer({
    fromPubkey: payer.publicKey,
    toPubkey: new PublicKey(paymentAddress),
    lamports: paymentAmount,
  })
);

// Attach nonce as memo
transaction.add(
  createMemoInstruction(paymentNonce)
);

const signature = await sendAndConfirmTransaction(
  connection,
  transaction,
  [payer],
);
```

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `payment_required` | 402 | Payment needed to access resource |
| `payment_invalid` | 400 | Transaction does not match requirements |
| `payment_expired` | 410 | Nonce or payment offer has expired |
| `payment_replayed` | 409 | Nonce has already been consumed |
| `payment_pending` | 202 | Transaction not yet confirmed |
| `payment_insufficient` | 402 | Amount too low |
| `network_mismatch` | 400 | Transaction on wrong network |

## Security Considerations

### Replay Protection

- Every payment requires a unique nonce
- Nonces are consumed on-chain via PDA creation
- Attempting to reuse a nonce fails because the PDA already exists
- Nonces expire after a configurable timeout (default: 5 minutes)

### Amount Verification

- The exact amount (or greater) must be transferred
- Token mint must match exactly
- Destination must be the protocol vault PDA

### Timing Attacks

- Payment expiry is checked against on-chain slot timestamps
- Clock drift tolerance: 30 seconds
- Expired payments are rejected even if the transaction is valid

### Front-Running

- Nonces are bound to the requesting client
- Payment records include the payer's public key
- A different payer cannot claim another client's nonce
