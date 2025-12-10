"""
Main Trading Engine for PIKKY.

Manages the full lifecycle of the trading agent:
receive x402 payment -> load MBTI strategy -> scan markets -> execute trades -> report PnL.
Runs an async event loop with position management and risk checks.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import structlog

from pikky.config import PikkyConfig
from pikky.mbti.types import MbtiType
from pikky.solana.client import SolanaClient
from pikky.strategies.registry import StrategyRegistry
from pikky.trader import TradeExecutor, TradeResult
from pikky.x402 import PaymentSession, X402PaymentHandler

logger = structlog.get_logger(__name__)


class EngineState(str, Enum):
    """State of the trading engine."""

    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class PositionSide(str, Enum):
    """Side of a trading position."""

    LONG = "long"


@dataclass
class Position:
    """An open trading position."""

    position_id: str
    session_id: str
    token_mint: str
    token_symbol: str
    side: PositionSide
    entry_price: float
    current_price: float
    amount_tokens: int
    amount_sol_in: float
    entry_time: float
    mbti_type: str
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    trailing_stop_active: bool = False
    trailing_stop_peak: float = 0.0
    trailing_stop_price: float = 0.0

    @property
    def unrealized_pnl_pct(self) -> float:
        """Calculate unrealized PnL as a percentage."""
        if self.entry_price == 0:
            return 0.0
        return ((self.current_price - self.entry_price) / self.entry_price) * 100

    @property
    def unrealized_pnl_sol(self) -> float:
        """Calculate unrealized PnL in SOL."""
        if self.entry_price == 0:
            return 0.0
        price_change_pct = (self.current_price - self.entry_price) / self.entry_price
        return self.amount_sol_in * price_change_pct

    @property
    def holding_duration_seconds(self) -> float:
        """How long this position has been held."""
        return time.time() - self.entry_time

    def update_trailing_stop(self, activation_pct: float, distance_pct: float) -> None:
        """Update trailing stop based on current price movement."""
        pnl_pct = self.unrealized_pnl_pct / 100
        if pnl_pct >= activation_pct:
            self.trailing_stop_active = True
            if self.current_price > self.trailing_stop_peak:
                self.trailing_stop_peak = self.current_price
                self.trailing_stop_price = self.trailing_stop_peak * (1 - distance_pct)


@dataclass
class PnLReport:
    """Periodic PnL report."""

    timestamp: float
    total_balance_sol: float
    starting_balance_sol: float
    realized_pnl_sol: float
    unrealized_pnl_sol: float
    open_positions: int
    total_trades: int
    win_rate: float
    max_drawdown_pct: float
    daily_pnl_sol: float
    active_sessions: int

    @property
    def total_pnl_sol(self) -> float:
        """Total PnL including unrealized."""
        return self.realized_pnl_sol + self.unrealized_pnl_sol

    @property
    def total_pnl_pct(self) -> float:
        """Total PnL as percentage of starting balance."""
        if self.starting_balance_sol == 0:
            return 0.0
        return (self.total_pnl_sol / self.starting_balance_sol) * 100


@dataclass
class MarketData:
    """Market data snapshot for a token."""

    mint: str
    symbol: str
    price_usd: float
    volume_24h: float
    price_change_1h: float
    price_change_24h: float
    liquidity_usd: float
    timestamp: float
    prices_history: list[float] = field(default_factory=list)
    volumes_history: list[float] = field(default_factory=list)

