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


class TradingEngine:
    """
    Core trading engine for PIKKY.

    Orchestrates the entire trading workflow:
    - Manages x402 payment sessions
    - Loads MBTI-based trading strategies
    - Scans markets for opportunities
    - Executes trades through TradeExecutor
    - Manages open positions with risk controls
    - Reports PnL periodically
    """

    def __init__(self, config: PikkyConfig) -> None:
        """
        Initialize the trading engine.

        Args:
            config: Complete PIKKY configuration.
        """
        self._config = config
        self._state = EngineState.IDLE
        self._solana = SolanaClient(
            rpc_url=config.rpc_url,
            ws_url=config.get_ws_url(),
        )
        self._executor = TradeExecutor(
            solana_client=self._solana,
            jupiter_config=config.jupiter,
            risk_config=config.risk,
            paper_trading=config.enable_paper_trading,
        )
        self._x402 = X402PaymentHandler(
            recipient_address="",
            solana_client=self._solana,
            base_fee_lamports=config.fees.x402_base_fee_lamports,
            session_duration_seconds=config.fees.x402_session_duration_seconds,
            refund_window_seconds=config.fees.refund_window_seconds,
        )
        self._strategy_registry = StrategyRegistry()

        self._positions: dict[str, Position] = {}
        self._closed_positions: list[Position] = []
        self._market_data: dict[str, MarketData] = {}
        self._session_strategies: dict[str, Any] = {}

        self._starting_balance_sol: float = 0.0
        self._current_balance_sol: float = 0.0
        self._realized_pnl_sol: float = 0.0
        self._peak_balance_sol: float = 0.0
        self._max_drawdown_pct: float = 0.0
        self._daily_start_balance: float = 0.0
        self._daily_start_time: float = 0.0
        self._win_count: int = 0
        self._loss_count: int = 0

        self._main_loop_task: Optional[asyncio.Task] = None
        self._market_scan_task: Optional[asyncio.Task] = None
        self._pnl_report_task: Optional[asyncio.Task] = None
        self._position_monitor_task: Optional[asyncio.Task] = None

        logger.info(
            "trading_engine_initialized",
            network=config.network.value,
            paper_trading=config.enable_paper_trading,
        )

    @property
    def state(self) -> EngineState:
        """Get current engine state."""
        return self._state

    @property
    def positions(self) -> dict[str, Position]:
        """Get open positions."""
        return self._positions.copy()

    async def start(self) -> None:
        """Start the trading engine and all subsystems."""
        if self._state == EngineState.RUNNING:
            logger.warning("engine_already_running")
            return

        self._state = EngineState.STARTING
        logger.info("engine_starting")

        try:
            await self._solana.connect()
            await self._executor.start()
            await self._x402.start()

            balance = await self._solana.get_sol_balance()
            self._starting_balance_sol = balance
            self._current_balance_sol = balance
            self._peak_balance_sol = balance
            self._daily_start_balance = balance
            self._daily_start_time = time.time()

            wallet_pubkey = await self._solana.get_wallet_pubkey()
            self._x402._recipient = str(wallet_pubkey)

            self._main_loop_task = asyncio.create_task(self._main_loop())
            self._market_scan_task = asyncio.create_task(self._market_scan_loop())
            self._pnl_report_task = asyncio.create_task(self._pnl_report_loop())
            self._position_monitor_task = asyncio.create_task(self._position_monitor_loop())

            self._state = EngineState.RUNNING
            logger.info(
                "engine_started",
                balance_sol=balance,
                wallet=str(wallet_pubkey),
            )

        except Exception as exc:
            self._state = EngineState.ERROR
            logger.error("engine_start_failed", error=str(exc))
            raise

    async def stop(self) -> None:
        """Stop the trading engine gracefully."""
        if self._state not in (EngineState.RUNNING, EngineState.ERROR):
            return

        self._state = EngineState.STOPPING
        logger.info("engine_stopping")

        tasks = [
            self._main_loop_task,
            self._market_scan_task,
            self._pnl_report_task,
            self._position_monitor_task,
        ]
        for task in tasks:
            if task and not task.done():
                task.cancel()

        for task in tasks:
            if task:
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        await self._x402.stop()
        await self._executor.stop()
        await self._solana.disconnect()

        self._state = EngineState.STOPPED
        logger.info(
            "engine_stopped",
            realized_pnl=self._realized_pnl_sol,
            total_trades=self._win_count + self._loss_count,
        )

    async def activate_session(
        self,
        session: PaymentSession,
    ) -> None:
        """
        Activate a trading session with the appropriate MBTI strategy.

        Args:
            session: A verified payment session.
        """
        mbti_type = MbtiType(session.mbti_type)
        strategy = self._strategy_registry.get_strategy(mbti_type)

        if strategy is None:
            logger.error("no_strategy_for_type", mbti_type=session.mbti_type)
            return

        self._session_strategies[session.session_id] = strategy

        logger.info(
            "session_activated",
            session_id=session.session_id,
            mbti_type=session.mbti_type,
            strategy=strategy.__class__.__name__,
            expires_in=session.remaining_seconds(),
        )

    async def process_session_tick(self, session: PaymentSession) -> None:
        """
        Process one tick of trading logic for a session.

        Runs the MBTI strategy analysis and executes any signals.
        """
        strategy = self._session_strategies.get(session.session_id)
        if strategy is None:
            return

        if not session.is_active():
            await self._close_session_positions(session.session_id)
            return

        num_positions = sum(
            1 for p in self._positions.values()
            if p.session_id == session.session_id
        )
        if num_positions >= self._config.risk.max_concurrent_positions:
            return

        total_exposure = sum(p.amount_sol_in for p in self._positions.values())
        max_exposure = self._current_balance_sol * self._config.risk.max_portfolio_exposure_pct
        if total_exposure >= max_exposure:
            return

        daily_pnl = self._get_daily_pnl()
        if daily_pnl < -(self._daily_start_balance * self._config.risk.max_daily_loss_pct):
            logger.warning(
                "daily_loss_limit_hit",
                daily_pnl=daily_pnl,
                limit=self._config.risk.max_daily_loss_pct,
            )
            return

        for mint, market in self._market_data.items():
            if market.liquidity_usd < self._config.risk.min_liquidity_usd:
                continue

            already_holding = any(
                p.token_mint == mint and p.session_id == session.session_id
                for p in self._positions.values()
            )

            analysis = strategy.analyze(market)

            if not already_holding and strategy.should_enter(analysis, market):
                position_size_sol = strategy.calculate_position_size(
                    analysis=analysis,
                    portfolio_balance_sol=self._current_balance_sol,
                    current_exposure_sol=total_exposure,
                )

                max_trade_size = (
                    self._current_balance_sol
                    * self._config.risk.max_single_trade_loss_pct
                    / 0.1
                )
                position_size_sol = min(position_size_sol, max_trade_size)
                position_size_sol = min(
                    position_size_sol, self._config.risk.max_position_size_sol
                )

                if position_size_sol >= 0.01:
                    await self._open_position(
                        session=session,
                        token_mint=mint,
                        token_symbol=market.symbol,
                        sol_amount=position_size_sol,
                        strategy=strategy,
                        analysis=analysis,
                        current_price=market.price_usd,
                    )

    async def _open_position(
        self,
        session: PaymentSession,
        token_mint: str,
        token_symbol: str,
        sol_amount: float,
        strategy: Any,
        analysis: dict,
        current_price: float,
    ) -> Optional[Position]:
        """Open a new position by executing a buy trade."""
        risk_params = strategy.get_risk_params()

        result = await self._executor.execute_buy(
            session_id=session.session_id,
            token_mint=token_mint,
            sol_amount=sol_amount,
            slippage_bps=risk_params.get("slippage_bps", self._config.risk.default_slippage_bps),
        )

        if not result.success:
            logger.warning(
                "position_open_failed",
                token=token_symbol,
                error=result.error,
            )
            return None

        stop_loss_pct = risk_params.get("stop_loss_pct", 0.10)
        take_profit_pct = risk_params.get("take_profit_pct", 0.30)

        position_id = f"pos_{session.session_id[:8]}_{token_symbol}_{int(time.time())}"
        position = Position(
            position_id=position_id,
            session_id=session.session_id,
            token_mint=token_mint,
            token_symbol=token_symbol,
            side=PositionSide.LONG,
            entry_price=current_price,
            current_price=current_price,
            amount_tokens=result.amount_out,
            amount_sol_in=sol_amount,
            entry_time=time.time(),
            mbti_type=session.mbti_type,
            stop_loss_price=current_price * (1 - stop_loss_pct),
            take_profit_price=current_price * (1 + take_profit_pct),
        )

        self._positions[position_id] = position
        session.record_trade(0)

        logger.info(
            "position_opened",
            position_id=position_id,
            token=token_symbol,
            sol_amount=sol_amount,
            entry_price=current_price,
            stop_loss=position.stop_loss_price,
            take_profit=position.take_profit_price,
            mbti=session.mbti_type,
        )

        return position

    async def _close_position(
        self,
        position: Position,
        reason: str = "strategy_signal",
    ) -> Optional[TradeResult]:
        """Close a position by executing a sell trade."""
        result = await self._executor.execute_sell(
            session_id=position.session_id,
            token_mint=position.token_mint,
            token_amount=position.amount_tokens,
        )

        if not result.success:
            logger.warning(
                "position_close_failed",
                position_id=position.position_id,
                error=result.error,
            )
            return None

        sol_out = result.amount_out / 1_000_000_000
        pnl_sol = sol_out - position.amount_sol_in
        self._realized_pnl_sol += pnl_sol

        if pnl_sol >= 0:
            self._win_count += 1
        else:
            self._loss_count += 1

        session = self._x402.get_session(position.session_id)
        if session:
            session.record_trade(int(pnl_sol * 1_000_000_000))

        del self._positions[position.position_id]
        self._closed_positions.append(position)

        logger.info(
            "position_closed",
            position_id=position.position_id,
            token=position.token_symbol,
            pnl_sol=pnl_sol,
            pnl_pct=position.unrealized_pnl_pct,
            reason=reason,
            hold_duration=position.holding_duration_seconds,
        )

        return result

    async def _close_session_positions(self, session_id: str) -> None:
        """Close all positions for an expired session."""
        positions_to_close = [
            p for p in self._positions.values() if p.session_id == session_id
        ]
        for position in positions_to_close:
            await self._close_position(position, reason="session_expired")

        if session_id in self._session_strategies:
            del self._session_strategies[session_id]

    async def _main_loop(self) -> None:
        """Main engine event loop. Processes active sessions each tick."""
        logger.info("main_loop_started", tick_interval=self._config.engine_tick_interval_seconds)

        while self._state == EngineState.RUNNING:
            try:
                active_sessions = self._x402.get_all_active_sessions()

                for session in active_sessions:
                    if session.session_id not in self._session_strategies:
                        await self.activate_session(session)
                    await self.process_session_tick(session)

                expired_session_ids = set(self._session_strategies.keys()) - {
                    s.session_id for s in active_sessions
                }
                for sid in expired_session_ids:
                    await self._close_session_positions(sid)

                await self._update_balances()

                await asyncio.sleep(self._config.engine_tick_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("main_loop_error", error=str(exc))
                await asyncio.sleep(self._config.engine_tick_interval_seconds)

    async def _market_scan_loop(self) -> None:
        """Periodically scan markets and update market data."""
        logger.info("market_scan_loop_started")

        while self._state == EngineState.RUNNING:
            try:
                await self._scan_markets()
                await asyncio.sleep(self._config.market_scan_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("market_scan_error", error=str(exc))
                await asyncio.sleep(self._config.market_scan_interval_seconds)

    async def _position_monitor_loop(self) -> None:
        """Monitor open positions for stop-loss, take-profit, and trailing stops."""
        logger.info("position_monitor_started")

        while self._state == EngineState.RUNNING:
            try:
                await self._check_position_exits()
                await asyncio.sleep(2.0)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("position_monitor_error", error=str(exc))
                await asyncio.sleep(5.0)

    async def _pnl_report_loop(self) -> None:
        """Periodically generate and log PnL reports."""
        logger.info("pnl_report_loop_started")

        while self._state == EngineState.RUNNING:
            try:
                await asyncio.sleep(self._config.pnl_report_interval_seconds)
                report = self._generate_pnl_report()
                self._log_pnl_report(report)
                self._check_daily_reset()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("pnl_report_error", error=str(exc))

    async def _scan_markets(self) -> None:
        """Scan token watchlist and update market data."""
        prices = await self._executor.get_multiple_prices(self._config.token_watchlist)

        for mint in self._config.token_watchlist:
            price = prices.get(mint, 0.0)
            if price <= 0:
                continue

            existing = self._market_data.get(mint)
            if existing:
                existing.prices_history.append(price)
                if len(existing.prices_history) > 500:
                    existing.prices_history = existing.prices_history[-500:]

                if len(existing.prices_history) >= 2:
                    prev = existing.prices_history[-2]
                    existing.price_change_1h = ((price - prev) / prev) * 100 if prev else 0
                existing.price_usd = price
                existing.timestamp = time.time()
            else:
                symbol = mint[:4].upper()
                self._market_data[mint] = MarketData(
                    mint=mint,
                    symbol=symbol,
                    price_usd=price,
                    volume_24h=0.0,
                    price_change_1h=0.0,
                    price_change_24h=0.0,
                    liquidity_usd=100000.0,
                    timestamp=time.time(),
                    prices_history=[price],
                )

    async def _check_position_exits(self) -> None:
        """Check all open positions against exit conditions."""
        positions_to_check = list(self._positions.values())

        for position in positions_to_check:
            if position.position_id not in self._positions:
                continue

            market = self._market_data.get(position.token_mint)
            if market:
                position.current_price = market.price_usd

            position.update_trailing_stop(
                activation_pct=self._config.risk.trailing_stop_activation_pct,
                distance_pct=self._config.risk.trailing_stop_distance_pct,
            )

            if position.stop_loss_price and position.current_price <= position.stop_loss_price:
                await self._close_position(position, reason="stop_loss")
                continue

            if (
                position.take_profit_price
                and position.current_price >= position.take_profit_price
            ):
                await self._close_position(position, reason="take_profit")
                continue

            if (
                position.trailing_stop_active
                and position.current_price <= position.trailing_stop_price
            ):
                await self._close_position(position, reason="trailing_stop")
                continue

            strategy = self._session_strategies.get(position.session_id)
            if strategy:
                analysis = strategy.analyze(market) if market else {}
                if market and strategy.should_exit(analysis, market, position):
                    await self._close_position(position, reason="strategy_exit")
                    continue

            max_loss = self._config.risk.max_single_trade_loss_pct * 100
            if position.unrealized_pnl_pct < -max_loss:
                await self._close_position(position, reason="max_loss_breached")

    async def _update_balances(self) -> None:
        """Update current balance and drawdown tracking."""
        try:
            self._current_balance_sol = await self._solana.get_sol_balance()

            total_balance = self._current_balance_sol + sum(
                p.amount_sol_in + p.unrealized_pnl_sol for p in self._positions.values()
            )

            if total_balance > self._peak_balance_sol:
                self._peak_balance_sol = total_balance

            if self._peak_balance_sol > 0:
                current_drawdown = (
                    (self._peak_balance_sol - total_balance) / self._peak_balance_sol
                )
                self._max_drawdown_pct = max(self._max_drawdown_pct, current_drawdown)

                if current_drawdown >= self._config.risk.max_drawdown_pct:
                    logger.critical(
                        "max_drawdown_breached",
                        drawdown_pct=current_drawdown * 100,
                        limit_pct=self._config.risk.max_drawdown_pct * 100,
                    )
                    for pos in list(self._positions.values()):
                        await self._close_position(pos, reason="max_drawdown")

        except Exception as exc:
            logger.warning("balance_update_failed", error=str(exc))

    def _get_daily_pnl(self) -> float:
        """Calculate PnL since the start of the trading day."""
        unrealized = sum(p.unrealized_pnl_sol for p in self._positions.values())
        return self._realized_pnl_sol + unrealized - (
            self._starting_balance_sol - self._daily_start_balance
        )

    def _generate_pnl_report(self) -> PnLReport:
        """Generate a comprehensive PnL report."""
        unrealized = sum(p.unrealized_pnl_sol for p in self._positions.values())
        total_trades = self._win_count + self._loss_count
        win_rate = self._win_count / total_trades if total_trades > 0 else 0.0
        daily_pnl = self._get_daily_pnl()

        return PnLReport(
            timestamp=time.time(),
            total_balance_sol=self._current_balance_sol,
            starting_balance_sol=self._starting_balance_sol,
            realized_pnl_sol=self._realized_pnl_sol,
            unrealized_pnl_sol=unrealized,
            open_positions=len(self._positions),
            total_trades=total_trades,
            win_rate=win_rate,
            max_drawdown_pct=self._max_drawdown_pct * 100,
            daily_pnl_sol=daily_pnl,
            active_sessions=len(self._x402.get_all_active_sessions()),
        )

    def _log_pnl_report(self, report: PnLReport) -> None:
        """Log a PnL report."""
        logger.info(
            "pnl_report",
            balance_sol=f"{report.total_balance_sol:.4f}",
            realized_pnl=f"{report.realized_pnl_sol:.4f}",
            unrealized_pnl=f"{report.unrealized_pnl_sol:.4f}",
            total_pnl_pct=f"{report.total_pnl_pct:.2f}%",
            positions=report.open_positions,
            trades=report.total_trades,
            win_rate=f"{report.win_rate:.1%}",
            max_drawdown=f"{report.max_drawdown_pct:.2f}%",
            daily_pnl=f"{report.daily_pnl_sol:.4f}",
            sessions=report.active_sessions,
        )

    def _check_daily_reset(self) -> None:
        """Reset daily tracking at midnight UTC."""
        now = time.time()
        if now - self._daily_start_time >= 86400:
            self._daily_start_balance = self._current_balance_sol
            self._daily_start_time = now
            logger.info("daily_reset", new_start_balance=self._current_balance_sol)

    def get_engine_stats(self) -> dict:
        """Get comprehensive engine statistics."""
        return {
            "state": self._state.value,
            "balance_sol": self._current_balance_sol,
            "starting_balance_sol": self._starting_balance_sol,
            "realized_pnl_sol": self._realized_pnl_sol,
            "unrealized_pnl_sol": sum(
                p.unrealized_pnl_sol for p in self._positions.values()
            ),
            "open_positions": len(self._positions),
            "closed_positions": len(self._closed_positions),
            "win_count": self._win_count,
            "loss_count": self._loss_count,
            "max_drawdown_pct": self._max_drawdown_pct * 100,
            "active_sessions": len(self._x402.get_all_active_sessions()),
            "market_tokens_tracked": len(self._market_data),
            "executor_stats": self._executor.get_stats(),
            "x402_stats": self._x402.get_stats(),
            "paper_trading": self._config.enable_paper_trading,
        }
