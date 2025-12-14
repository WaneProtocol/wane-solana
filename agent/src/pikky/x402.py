"""
X402 Payment Handler for PIKKY.

Implements the HTTP 402 Payment Required protocol for gating access to
PIKKY's trading agent services. Users must pay in SOL on Solana to activate
their trading session. Payments are verified on-chain before granting access.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import base58
import structlog

logger = structlog.get_logger(__name__)


class PaymentStatus(str, Enum):
    """Status of an x402 payment."""

    PENDING = "pending"
    CONFIRMING = "confirming"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    REFUNDED = "refunded"
    FAILED = "failed"


@dataclass
class PaymentChallenge:
    """An x402 payment challenge issued to a client."""

    challenge_id: str
    recipient_address: str
    amount_lamports: int
    memo: str
    created_at: float
    expires_at: float
    mbti_type: str
    client_address: Optional[str] = None

    def is_expired(self) -> bool:
        """Check if this challenge has expired."""
        return time.time() > self.expires_at

    def to_header_value(self) -> str:
        """Serialize to x402 WWW-Authenticate header value."""
        return (
            f'X402 realm="pikky", '
            f'challenge="{self.challenge_id}", '
            f'recipient="{self.recipient_address}", '
            f'amount="{self.amount_lamports}", '
            f'memo="{self.memo}", '
            f'chain="solana", '
            f'expires="{int(self.expires_at)}"'
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON responses."""
        return {
            "challenge_id": self.challenge_id,
            "recipient": self.recipient_address,
            "amount_lamports": self.amount_lamports,
            "memo": self.memo,
            "chain": "solana",
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "mbti_type": self.mbti_type,
        }


@dataclass
class PaymentSession:
    """An active payment session after successful x402 payment."""

    session_id: str
    challenge_id: str
    client_address: str
    tx_signature: str
    amount_lamports: int
    mbti_type: str
    activated_at: float
    expires_at: float
    status: PaymentStatus = PaymentStatus.CONFIRMED
    trades_executed: int = 0
    pnl_lamports: int = 0

    def is_active(self) -> bool:
        """Check if this session is still active."""
        return self.status == PaymentStatus.CONFIRMED and time.time() < self.expires_at

    def remaining_seconds(self) -> float:
        """Get remaining session time in seconds."""
        remaining = self.expires_at - time.time()
        return max(0.0, remaining)

    def record_trade(self, pnl_lamports: int) -> None:
        """Record a trade execution and its PnL."""
        self.trades_executed += 1
        self.pnl_lamports += pnl_lamports


@dataclass
class RefundRecord:
    """Record of a payment refund."""

    refund_id: str
    session_id: str
    original_tx: str
    refund_tx: str
    amount_lamports: int
    reason: str
    created_at: float


class X402PaymentHandler:
    """
    Handles the x402 payment protocol for PIKKY trading agent access.

    The x402 flow:
    1. Client requests trading service without payment
    2. Server responds with 402 + payment challenge
    3. Client sends SOL payment on-chain with challenge memo
    4. Client retries request with payment proof (tx signature)
    5. Server verifies payment on-chain and activates session
    """
