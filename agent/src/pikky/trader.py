"""
Trade Executor for PIKKY.

Handles actual trade execution on Solana DEXs through Jupiter aggregator.
Manages order building, slippage calculation, transaction signing,
confirmation waiting, and trade result reporting.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import httpx
import structlog

from pikky.config import JupiterConfig, RiskConfig

logger = structlog.get_logger(__name__)

LAMPORTS_PER_SOL = 1_000_000_000
WSOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


class OrderSide(str, Enum):
    """Trade direction."""

    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    """Status of a trade order."""

    PENDING = "pending"
    QUOTING = "quoting"
    SIGNING = "signing"
    SUBMITTED = "submitted"
    CONFIRMING = "confirming"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SwapQuote:
    """A quote from Jupiter for a token swap."""

    input_mint: str
    output_mint: str
    in_amount: int
    out_amount: int
    other_amount_threshold: int
    swap_mode: str
    slippage_bps: int
    price_impact_pct: float
    route_plan: list[dict[str, Any]]
    raw_quote: dict[str, Any]
    fetched_at: float = field(default_factory=time.time)

    @property
    def effective_price(self) -> float:
        """Calculate the effective swap price."""
        if self.in_amount == 0:
            return 0.0
        return self.out_amount / self.in_amount

    @property
    def is_stale(self) -> bool:
        """Check if quote is older than 30 seconds."""
        return time.time() - self.fetched_at > 30.0


@dataclass
class TradeOrder:
    """A trade order to be executed."""

    order_id: str
    session_id: str
    side: OrderSide
    input_mint: str
    output_mint: str
    amount_in: int
    min_amount_out: int
    slippage_bps: int
    status: OrderStatus = OrderStatus.PENDING
    created_at: float = field(default_factory=time.time)
    quote: Optional[SwapQuote] = None
    tx_signature: Optional[str] = None
    confirmed_at: Optional[float] = None
    actual_amount_out: Optional[int] = None
    error: Optional[str] = None
    retries: int = 0

    @property
    def is_terminal(self) -> bool:
        """Check if the order is in a terminal state."""
        return self.status in (
            OrderStatus.CONFIRMED,
            OrderStatus.FAILED,
            OrderStatus.CANCELLED,
        )


@dataclass
class TradeResult:
    """Result of an executed trade."""

    order_id: str
    success: bool
    tx_signature: Optional[str]
    input_mint: str
    output_mint: str
    amount_in: int
    amount_out: int
    price_impact_pct: float
    slippage_actual_bps: int
    execution_time_ms: float
    error: Optional[str] = None

    @property