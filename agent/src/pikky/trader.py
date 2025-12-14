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

    async def get_token_price(self, token_mint: str) -> Optional[float]:
        """
        Get the current price of a token in USD via Jupiter price API.

        Args:
            token_mint: The token's mint address.

        Returns:
            Price in USD or None if unavailable.
        """
        if not self._http:
            return None

        try:
            resp = await self._http.get(
                f"{self._jupiter.price_api_url}/price",
                params={"ids": token_mint},
            )
            resp.raise_for_status()
            data = resp.json()
            price_data = data.get("data", {}).get(token_mint)
            if price_data:
                return float(price_data["price"])
            return None
        except Exception as exc:
            logger.warning("price_fetch_failed", token=token_mint[:8], error=str(exc))
            return None

    async def get_multiple_prices(self, token_mints: list[str]) -> dict[str, float]:
        """
        Get prices for multiple tokens in a single request.

        Args:
            token_mints: List of token mint addresses.

        Returns:
            Dict mapping mint address to USD price.
        """
        if not self._http or not token_mints:
            return {}

        try:
            resp = await self._http.get(
                f"{self._jupiter.price_api_url}/price",
                params={"ids": ",".join(token_mints)},
            )
            resp.raise_for_status()
            data = resp.json()
            prices: dict[str, float] = {}
            for mint in token_mints:
                price_data = data.get("data", {}).get(mint)
                if price_data:
                    prices[mint] = float(price_data["price"])
            return prices
        except Exception as exc:
            logger.warning("multi_price_fetch_failed", error=str(exc))
            return {}

    def calculate_slippage(
        self,
        expected_out: int,
        actual_out: int,
    ) -> int:
        """
        Calculate actual slippage in basis points.

        Args:
            expected_out: Expected output amount from quote.
            actual_out: Actual output amount received.

        Returns:
            Slippage in basis points (negative = worse than expected).
        """
        if expected_out == 0:
            return 0
        diff = actual_out - expected_out
        return int((diff / expected_out) * 10000)

    def get_stats(self) -> dict:
        """Get executor statistics."""
        return {
            "total_trades": self._total_trades,
            "failed_trades": self._failed_trades,
            "success_rate": (
                (self._total_trades - self._failed_trades) / self._total_trades
                if self._total_trades > 0
                else 0.0
            ),
            "total_volume_in": self._total_volume_in,
            "total_volume_out": self._total_volume_out,
            "pending_orders": len(self._pending_orders),
            "completed_orders": len(self._completed_orders),
            "paper_trading": self._paper_trading,
        }

    async def _get_jupiter_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int,
    ) -> SwapQuote:
        """Fetch a swap quote from Jupiter V6 API."""
        if not self._http:
            raise TradeExecutionError("HTTP client not initialized. Call start() first.")

        params: dict[str, Any] = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": slippage_bps,
            "swapMode": self._jupiter.swap_mode,
            "onlyDirectRoutes": str(self._jupiter.only_direct_routes).lower(),
            "maxAccounts": self._jupiter.max_accounts,
        }

        if self._jupiter.dex_filter:
            params["dexes"] = ",".join(self._jupiter.dex_filter)

        last_error: Optional[Exception] = None
        for attempt in range(self._jupiter.max_retries):
            try:
                resp = await self._http.get(
                    f"{self._jupiter.api_url}/quote",
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()

                route_plan = data.get("routePlan", [])
                price_impact = float(data.get("priceImpactPct", "0"))

                quote = SwapQuote(
                    input_mint=input_mint,
                    output_mint=output_mint,
                    in_amount=int(data["inAmount"]),
                    out_amount=int(data["outAmount"]),
                    other_amount_threshold=int(data["otherAmountThreshold"]),
                    swap_mode=data.get("swapMode", "ExactIn"),
                    slippage_bps=slippage_bps,
                    price_impact_pct=price_impact,
                    route_plan=route_plan,
                    raw_quote=data,
                )

                logger.debug(
                    "jupiter_quote_received",
                    input=input_mint[:8],
                    output=output_mint[:8],
                    in_amount=quote.in_amount,
                    out_amount=quote.out_amount,
                    price_impact=price_impact,
                    routes=len(route_plan),
                )

                return quote

            except httpx.HTTPStatusError as exc:
                last_error = exc
                logger.warning(
                    "jupiter_quote_http_error",
                    status=exc.response.status_code,
                    attempt=attempt + 1,
                    body=exc.response.text[:200],
                )
                if exc.response.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                elif exc.response.status_code >= 500:
                    await asyncio.sleep(1)
                else:
                    break

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "jupiter_quote_error",
                    error=str(exc),
                    attempt=attempt + 1,
                )
                await asyncio.sleep(1)

        raise TradeExecutionError(
            f"Failed to get Jupiter quote after {self._jupiter.max_retries} attempts: "
            f"{last_error}"
        )

    async def _execute_real_trade(
        self,
        order: TradeOrder,
        quote: SwapQuote,
    ) -> TradeResult:
        """Execute a real on-chain swap via Jupiter."""
        start_time = time.time()

        if not self._http:
            raise TradeExecutionError("HTTP client not initialized")

        order.status = OrderStatus.SIGNING

        wallet_pubkey = await self._solana.get_wallet_pubkey()

        swap_request = {
            "quoteResponse": quote.raw_quote,
            "userPublicKey": str(wallet_pubkey),
            "wrapAndUnwrapSol": True,
            "computeUnitPriceMicroLamports": self._risk.cool_down_seconds,
            "dynamicComputeUnitLimit": True,
        }

        resp = await self._http.post(
            f"{self._jupiter.api_url}/swap",
            json=swap_request,
        )
        resp.raise_for_status()
        swap_data = resp.json()

        swap_transaction = swap_data["swapTransaction"]

        order.status = OrderStatus.SUBMITTED
        tx_signature = await self._solana.sign_and_send_transaction(swap_transaction)

        order.status = OrderStatus.CONFIRMING
        confirmed = await self._solana.confirm_transaction(
            tx_signature, timeout_seconds=60
        )

        if not confirmed:
            raise TradeExecutionError(
                f"Transaction not confirmed within timeout: {tx_signature}"
            )

        actual_out = await self._get_actual_output(tx_signature, quote.output_mint)
        elapsed_ms = (time.time() - start_time) * 1000
        slippage_actual = self.calculate_slippage(quote.out_amount, actual_out)

        return TradeResult(
            order_id=order.order_id,
            success=True,
            tx_signature=tx_signature,
            input_mint=quote.input_mint,
            output_mint=quote.output_mint,
            amount_in=quote.in_amount,
            amount_out=actual_out,
            price_impact_pct=quote.price_impact_pct,
            slippage_actual_bps=slippage_actual,
            execution_time_ms=elapsed_ms,
        )

    async def _execute_paper_trade(
        self,
        order: TradeOrder,
        quote: SwapQuote,
    ) -> TradeResult:
        """Simulate a trade execution for paper trading mode."""
        start_time = time.time()

        await asyncio.sleep(0.1)

        import random
        slippage_factor = 1.0 - random.uniform(0, order.slippage_bps / 10000)
        simulated_out = int(quote.out_amount * slippage_factor)
        simulated_out = max(simulated_out, quote.other_amount_threshold)

        elapsed_ms = (time.time() - start_time) * 1000
        slippage_actual = self.calculate_slippage(quote.out_amount, simulated_out)

        fake_sig = f"paper_{order.order_id}_{int(time.time())}"

        logger.info(
            "paper_trade_executed",
            order_id=order.order_id,
            simulated_out=simulated_out,
            slippage_bps=slippage_actual,
        )

        return TradeResult(
            order_id=order.order_id,
            success=True,
            tx_signature=fake_sig,
            input_mint=quote.input_mint,
            output_mint=quote.output_mint,
            amount_in=quote.in_amount,
            amount_out=simulated_out,
            price_impact_pct=quote.price_impact_pct,
            slippage_actual_bps=slippage_actual,
            execution_time_ms=elapsed_ms,
        )

    async def _get_actual_output(self, tx_signature: str, output_mint: str) -> int:
        """
        Parse the actual output amount from a confirmed transaction.

        Examines token balance changes in the transaction metadata.
        """
        try:
            tx_info = await self._solana.get_transaction(tx_signature)
            if tx_info is None:
                logger.warning("cannot_parse_tx_output", tx=tx_signature)
                return 0

            meta = tx_info.get("meta", {})

            pre_token_balances = meta.get("preTokenBalances", [])
            post_token_balances = meta.get("postTokenBalances", [])

            wallet_pubkey = await self._solana.get_wallet_pubkey()
            wallet_str = str(wallet_pubkey)

            pre_amount = 0
            post_amount = 0

            for bal in pre_token_balances:
                if (
                    bal.get("mint") == output_mint
                    and bal.get("owner") == wallet_str
                ):
                    pre_amount = int(bal.get("uiTokenAmount", {}).get("amount", "0"))
                    break

            for bal in post_token_balances:
                if (
                    bal.get("mint") == output_mint
                    and bal.get("owner") == wallet_str
                ):
                    post_amount = int(bal.get("uiTokenAmount", {}).get("amount", "0"))
                    break

            return max(0, post_amount - pre_amount)

        except Exception as exc:
            logger.error("parse_output_error", tx=tx_signature, error=str(exc))
            return 0


class TradeExecutionError(Exception):
    """Raised when trade execution fails."""
