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
    def pnl_basis_points(self) -> int:
        """Calculate PnL in basis points relative to expected output."""
        if self.amount_out == 0:
            return -10000
        return 0


class TradeExecutor:
    """
    Executes trades on Solana DEXs via Jupiter aggregator.

    Handles the full lifecycle of a trade:
    1. Fetch quote from Jupiter
    2. Build swap transaction
    3. Sign and submit transaction
    4. Wait for confirmation
    5. Report result
    """

    def __init__(
        self,
        solana_client: Any,
        jupiter_config: JupiterConfig,
        risk_config: RiskConfig,
        paper_trading: bool = True,
    ) -> None:
        """
        Initialize the trade executor.

        Args:
            solana_client: SolanaClient instance for transaction submission.
            jupiter_config: Jupiter aggregator configuration.
            risk_config: Risk management configuration.
            paper_trading: If True, simulate trades without on-chain execution.
        """
        self._solana = solana_client
        self._jupiter = jupiter_config
        self._risk = risk_config
        self._paper_trading = paper_trading
        self._http: Optional[httpx.AsyncClient] = None

        self._pending_orders: dict[str, TradeOrder] = {}
        self._completed_orders: dict[str, TradeOrder] = {}
        self._order_counter: int = 0
        self._last_trade_time: dict[str, float] = {}

        self._total_volume_in: int = 0
        self._total_volume_out: int = 0
        self._total_trades: int = 0
        self._failed_trades: int = 0

        logger.info(
            "trade_executor_initialized",
            paper_trading=paper_trading,
            jupiter_url=jupiter_config.api_url,
        )

    async def start(self) -> None:
        """Start the executor and create HTTP client."""
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(self._jupiter.quote_timeout_seconds),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        logger.info("trade_executor_started")

    async def stop(self) -> None:
        """Stop the executor and close HTTP client."""
        if self._http:
            await self._http.aclose()
            self._http = None
        logger.info("trade_executor_stopped")

    async def execute_swap(
        self,
        session_id: str,
        input_mint: str,
        output_mint: str,
        amount_in: int,
        slippage_bps: Optional[int] = None,
    ) -> TradeResult:
        """
        Execute a token swap via Jupiter.

        Args:
            session_id: The payment session authorizing this trade.
            input_mint: Mint address of the token to sell.
            output_mint: Mint address of the token to buy.
            amount_in: Amount of input token (in smallest units).
            slippage_bps: Slippage tolerance in basis points. Uses default if None.

        Returns:
            TradeResult with execution details.
        """
        start_time = time.time()
        slippage = slippage_bps or self._risk.default_slippage_bps

        self._order_counter += 1
        order_id = f"ord_{session_id[:8]}_{self._order_counter}_{int(start_time)}"

        cooldown_key = f"{input_mint}:{output_mint}"
        last_trade = self._last_trade_time.get(cooldown_key, 0)
        if time.time() - last_trade < self._risk.cool_down_seconds:
            wait_time = self._risk.cool_down_seconds - (time.time() - last_trade)
            logger.info("trade_cooldown_waiting", wait_seconds=wait_time, pair=cooldown_key)
            await asyncio.sleep(wait_time)

        order = TradeOrder(
            order_id=order_id,
            session_id=session_id,
            side=OrderSide.BUY if output_mint != WSOL_MINT else OrderSide.SELL,
            input_mint=input_mint,
            output_mint=output_mint,
            amount_in=amount_in,
            min_amount_out=0,
            slippage_bps=slippage,
        )
        self._pending_orders[order_id] = order

        try:
            order.status = OrderStatus.QUOTING
            quote = await self._get_jupiter_quote(
                input_mint=input_mint,
                output_mint=output_mint,
                amount=amount_in,
                slippage_bps=slippage,
            )
            order.quote = quote
            order.min_amount_out = quote.other_amount_threshold

            if quote.price_impact_pct > 5.0:
                raise TradeExecutionError(
                    f"Price impact too high: {quote.price_impact_pct:.2f}%"
                )

            if self._paper_trading:
                result = await self._execute_paper_trade(order, quote)
            else:
                result = await self._execute_real_trade(order, quote)

            order.status = OrderStatus.CONFIRMED
            order.confirmed_at = time.time()
            order.actual_amount_out = result.amount_out
            order.tx_signature = result.tx_signature

            self._total_volume_in += amount_in
            self._total_volume_out += result.amount_out
            self._total_trades += 1
            self._last_trade_time[cooldown_key] = time.time()

            logger.info(
                "trade_executed",
                order_id=order_id,
                input_mint=input_mint[:8],
                output_mint=output_mint[:8],
                amount_in=amount_in,
                amount_out=result.amount_out,
                price_impact=quote.price_impact_pct,
                paper=self._paper_trading,
            )

            return result

        except Exception as exc:
            order.status = OrderStatus.FAILED
            order.error = str(exc)
            self._failed_trades += 1

            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(
                "trade_execution_failed",
                order_id=order_id,
                error=str(exc),
                elapsed_ms=elapsed_ms,
            )

            return TradeResult(
                order_id=order_id,
                success=False,
                tx_signature=None,
                input_mint=input_mint,
                output_mint=output_mint,
                amount_in=amount_in,
                amount_out=0,
                price_impact_pct=0.0,
                slippage_actual_bps=0,
                execution_time_ms=elapsed_ms,
                error=str(exc),
            )

        finally:
            if order_id in self._pending_orders:
                self._completed_orders[order_id] = self._pending_orders.pop(order_id)

    async def execute_buy(
        self,
        session_id: str,
        token_mint: str,
        sol_amount: float,
        slippage_bps: Optional[int] = None,
    ) -> TradeResult:
        """
        Buy a token using SOL.

        Args:
            session_id: Payment session ID.
            token_mint: Mint address of the token to buy.
            sol_amount: Amount of SOL to spend.
            slippage_bps: Slippage tolerance.

        Returns:
            TradeResult of the buy execution.
        """
        amount_lamports = int(sol_amount * LAMPORTS_PER_SOL)

        max_lamports = int(self._risk.max_position_size_sol * LAMPORTS_PER_SOL)
        if amount_lamports > max_lamports:
            logger.warning(
                "trade_size_capped",
                requested=amount_lamports,
                max_allowed=max_lamports,
            )
            amount_lamports = max_lamports

        return await self.execute_swap(
            session_id=session_id,
            input_mint=WSOL_MINT,
            output_mint=token_mint,
            amount_in=amount_lamports,
            slippage_bps=slippage_bps,
        )

    async def execute_sell(
        self,
        session_id: str,
        token_mint: str,
        token_amount: int,
        slippage_bps: Optional[int] = None,
    ) -> TradeResult:
        """
        Sell a token for SOL.

        Args:
            session_id: Payment session ID.
            token_mint: Mint address of the token to sell.
            token_amount: Amount of tokens to sell (in smallest units).
            slippage_bps: Slippage tolerance.

        Returns:
            TradeResult of the sell execution.
        """
        return await self.execute_swap(
            session_id=session_id,
            input_mint=token_mint,
            output_mint=WSOL_MINT,
            amount_in=token_amount,
            slippage_bps=slippage_bps,
        )
