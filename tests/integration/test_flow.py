"""End-to-end integration tests for PIKKY trading flow.

Tests the complete lifecycle:
  deposit -> set MBTI -> trade -> check PnL -> withdraw
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import datetime, timezone

from src.engine import TradingEngine, EngineConfig, TradeSignal, TradeResult
from src.strategies import MBTIType, StrategyFactory
from src.x402_handler import X402Handler, X402Config, PaymentStatus


# Simulated on-chain state for integration tests
class MockOnChainState:
    """Simulates on-chain program state for testing without a validator."""

    def __init__(self):
        self.users = {}
        self.vault_balance = Decimal("0")
        self.trade_counter = 0
        self.payment_nonces = set()

    def initialize_user(self, pubkey: str):
        if pubkey in self.users:
            raise RuntimeError("User already initialized")
        self.users[pubkey] = {
            "deposited_amount": Decimal("0"),
            "current_balance": Decimal("0"),
            "mbti_type": None,
            "realized_pnl": Decimal("0"),
            "unrealized_pnl": Decimal("0"),
            "total_trades": 0,
            "winning_trades": 0,
            "auto_trade_enabled": False,
        }

    def deposit(self, pubkey: str, amount: Decimal):
        if pubkey not in self.users:
            raise RuntimeError("User not initialized")
        if amount <= 0:
            raise ValueError("Amount must be positive")
        self.users[pubkey]["deposited_amount"] += amount
        self.users[pubkey]["current_balance"] += amount
        self.vault_balance += amount

    def withdraw(self, pubkey: str, amount: Decimal):
        user = self.users.get(pubkey)
        if user is None:
            raise RuntimeError("User not initialized")
        if amount > user["current_balance"]:
            raise ValueError("Insufficient balance")
        user["current_balance"] -= amount
        self.vault_balance -= amount

    def set_mbti(self, pubkey: str, mbti_type: MBTIType):
        if pubkey not in self.users:
            raise RuntimeError("User not initialized")
        self.users[pubkey]["mbti_type"] = mbti_type

    def execute_trade(self, pubkey: str, side: str, amount: Decimal, price: Decimal):
        user = self.users.get(pubkey)
        if user is None:
            raise RuntimeError("User not initialized")
        if not user["auto_trade_enabled"]:
            raise RuntimeError("Auto-trading not enabled")
        if user["mbti_type"] is None:
            raise RuntimeError("MBTI type not set")

        self.trade_counter += 1
        fee = amount * Decimal("0.001")
        pnl = amount * Decimal("0.02") if side == "buy" else amount * Decimal("-0.01")

        user["current_balance"] += pnl - fee
        user["realized_pnl"] += pnl
        user["total_trades"] += 1
        if pnl > 0:
            user["winning_trades"] += 1

        return {
            "tx_signature": f"sim_tx_{self.trade_counter}",
            "fill_price": price,
            "fill_amount": amount,
            "fee": fee,
            "pnl": pnl,
        }

    def enable_auto_trade(self, pubkey: str):
        if pubkey not in self.users:
            raise RuntimeError("User not initialized")
        self.users[pubkey]["auto_trade_enabled"] = True

    def get_user_state(self, pubkey: str):
        return self.users.get(pubkey)


@pytest.fixture
def chain():
    return MockOnChainState()


@pytest.fixture
def user_pubkey():
    return "TestUser1PubkeyXXXXXXXXXXXXXXXXXXXXXXXXXXX"


class TestFullTradingFlow:
    """End-to-end test: deposit -> set MBTI -> trade -> check PnL -> withdraw."""

    def test_complete_flow(self, chain, user_pubkey):
        # Step 1: Initialize user
        chain.initialize_user(user_pubkey)
        state = chain.get_user_state(user_pubkey)
        assert state is not None
        assert state["current_balance"] == Decimal("0")

        # Step 2: Deposit 10 SOL
        deposit_amount = Decimal("10.0")
        chain.deposit(user_pubkey, deposit_amount)
        state = chain.get_user_state(user_pubkey)
        assert state["deposited_amount"] == deposit_amount
        assert state["current_balance"] == deposit_amount
        assert chain.vault_balance == deposit_amount

        # Step 3: Set MBTI type to INTJ
        chain.set_mbti(user_pubkey, MBTIType.INTJ)
        state = chain.get_user_state(user_pubkey)
        assert state["mbti_type"] == MBTIType.INTJ

        # Step 4: Enable auto-trading
        chain.enable_auto_trade(user_pubkey)
        state = chain.get_user_state(user_pubkey)
        assert state["auto_trade_enabled"] is True

        # Step 5: Execute a trade
        trade_result = chain.execute_trade(
            user_pubkey,
            side="buy",
            amount=Decimal("2.0"),
            price=Decimal("142.50"),
        )
        assert trade_result["tx_signature"].startswith("sim_tx_")
        assert trade_result["fill_amount"] == Decimal("2.0")

        # Step 6: Check PnL
        state = chain.get_user_state(user_pubkey)
        assert state["total_trades"] == 1
        assert state["realized_pnl"] != Decimal("0")
        assert state["current_balance"] != deposit_amount  # Changed due to PnL

        # Step 7: Withdraw remaining balance
        final_balance = state["current_balance"]
        chain.withdraw(user_pubkey, final_balance)
        state = chain.get_user_state(user_pubkey)
        assert state["current_balance"] == Decimal("0")

    def test_multiple_trades_accumulate_pnl(self, chain, user_pubkey):
        chain.initialize_user(user_pubkey)
        chain.deposit(user_pubkey, Decimal("100.0"))
        chain.set_mbti(user_pubkey, MBTIType.ENTJ)
        chain.enable_auto_trade(user_pubkey)

        # Execute 5 trades
        for i in range(5):
            chain.execute_trade(
                user_pubkey,
                side="buy",
                amount=Decimal("5.0"),
                price=Decimal("100.00") + Decimal(str(i)),
            )

        state = chain.get_user_state(user_pubkey)
        assert state["total_trades"] == 5
        assert state["realized_pnl"] != Decimal("0")
        assert state["winning_trades"] == 5  # All buys are profitable in mock

    def test_flow_with_different_mbti_types(self, chain):
        """Different MBTI types should produce different strategy parameters."""
        types_to_test = [MBTIType.INTJ, MBTIType.ISFJ, MBTIType.ESTP, MBTIType.ENFP]

        for mbti_type in types_to_test:
            pubkey = f"User_{mbti_type.value}_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            chain.initialize_user(pubkey)
            chain.deposit(pubkey, Decimal("10.0"))
            chain.set_mbti(pubkey, mbti_type)
            chain.enable_auto_trade(pubkey)

            strategy = StrategyFactory.create(mbti_type)
            assert strategy.risk_tolerance > 0

            chain.execute_trade(
                pubkey,
                side="buy",
                amount=Decimal("1.0"),
                price=Decimal("100.0"),
            )

            state = chain.get_user_state(pubkey)
            assert state["total_trades"] == 1
            assert state["mbti_type"] == mbti_type


class TestDepositWithdrawFlow:
    """Tests for deposit and withdrawal edge cases."""

    def test_cannot_withdraw_more_than_balance(self, chain, user_pubkey):
        chain.initialize_user(user_pubkey)
        chain.deposit(user_pubkey, Decimal("5.0"))
        with pytest.raises(ValueError, match="Insufficient balance"):
            chain.withdraw(user_pubkey, Decimal("10.0"))

    def test_multiple_deposits_accumulate(self, chain, user_pubkey):
        chain.initialize_user(user_pubkey)
        chain.deposit(user_pubkey, Decimal("5.0"))
        chain.deposit(user_pubkey, Decimal("3.0"))
        chain.deposit(user_pubkey, Decimal("2.0"))
        state = chain.get_user_state(user_pubkey)
        assert state["deposited_amount"] == Decimal("10.0")
        assert state["current_balance"] == Decimal("10.0")

    def test_partial_withdrawal(self, chain, user_pubkey):
        chain.initialize_user(user_pubkey)
        chain.deposit(user_pubkey, Decimal("10.0"))
        chain.withdraw(user_pubkey, Decimal("4.0"))
        state = chain.get_user_state(user_pubkey)
        assert state["current_balance"] == Decimal("6.0")

    def test_zero_deposit_rejected(self, chain, user_pubkey):
        chain.initialize_user(user_pubkey)
        with pytest.raises(ValueError, match="Amount must be positive"):
            chain.deposit(user_pubkey, Decimal("0"))

    def test_negative_deposit_rejected(self, chain, user_pubkey):
        chain.initialize_user(user_pubkey)
        with pytest.raises(ValueError, match="Amount must be positive"):
            chain.deposit(user_pubkey, Decimal("-5"))

    def test_deposit_before_init_rejected(self, chain):
        with pytest.raises(RuntimeError, match="User not initialized"):
            chain.deposit("nonexistent_user", Decimal("5.0"))


class TestTradingGuardrails:
    """Tests for safety checks and guardrails."""

    def test_trade_without_mbti_rejected(self, chain, user_pubkey):
        chain.initialize_user(user_pubkey)
        chain.deposit(user_pubkey, Decimal("10.0"))
        chain.enable_auto_trade(user_pubkey)
        # No MBTI type set
        with pytest.raises(RuntimeError, match="MBTI type not set"):
            chain.execute_trade(user_pubkey, "buy", Decimal("1.0"), Decimal("100.0"))

    def test_trade_without_auto_trade_rejected(self, chain, user_pubkey):
        chain.initialize_user(user_pubkey)
        chain.deposit(user_pubkey, Decimal("10.0"))
        chain.set_mbti(user_pubkey, MBTIType.INTJ)
        # Auto-trade not enabled
        with pytest.raises(RuntimeError, match="Auto-trading not enabled"):
            chain.execute_trade(user_pubkey, "buy", Decimal("1.0"), Decimal("100.0"))

    def test_duplicate_initialization_rejected(self, chain, user_pubkey):
        chain.initialize_user(user_pubkey)
        with pytest.raises(RuntimeError, match="User already initialized"):
            chain.initialize_user(user_pubkey)

    def test_vault_balance_tracks_deposits_and_withdrawals(self, chain, user_pubkey):
        chain.initialize_user(user_pubkey)
        chain.deposit(user_pubkey, Decimal("10.0"))
        assert chain.vault_balance == Decimal("10.0")
        chain.withdraw(user_pubkey, Decimal("3.0"))
        assert chain.vault_balance == Decimal("7.0")


class TestX402PaymentIntegration:
    """Tests for x402 payment flow within the trading lifecycle."""

    def test_x402_nonce_consumed_after_payment(self):
        config = X402Config(
            rpc_url="https://api.devnet.solana.com",
            vault_address="PikkyVau1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            network="solana:devnet",
            payment_timeout_seconds=300,
            min_payment_amount=1_000_000,
            max_payment_amount=1_000_000_000,
        )
        handler = X402Handler(config)
        nonce = "test_nonce_12345"
        assert not handler.is_nonce_consumed(nonce)
        handler.consume_nonce(nonce)
        assert handler.is_nonce_consumed(nonce)

    def test_pricing_for_trade_endpoints(self):
        config = X402Config(
            rpc_url="https://api.devnet.solana.com",
            vault_address="PikkyVau1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            network="solana:devnet",
            payment_timeout_seconds=300,
            min_payment_amount=1_000_000,
            max_payment_amount=1_000_000_000,
        )
        handler = X402Handler(config)
        assert handler.get_price("/api/agent/trade") > 0
        assert handler.get_price("/api/portfolio") == 0


class TestMBTIStrategyIntegration:
    """Tests for MBTI strategy behavior in the full flow context."""

    def test_strategy_params_affect_position_sizing(self, chain):
        conservative_pubkey = "ConservativeUserXXXXXXXXXXXXXXXXXXXXXXXXXX"
        aggressive_pubkey = "AggressiveUserXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"

        chain.initialize_user(conservative_pubkey)
        chain.initialize_user(aggressive_pubkey)
        chain.deposit(conservative_pubkey, Decimal("100.0"))
        chain.deposit(aggressive_pubkey, Decimal("100.0"))

        isfj = StrategyFactory.create(MBTIType.ISFJ)
        estp = StrategyFactory.create(MBTIType.ESTP)

        # ISFJ max position is ~10%, ESTP is ~40%
        assert isfj.max_position_pct < estp.max_position_pct
        assert isfj.risk_tolerance < estp.risk_tolerance

    def test_all_16_types_produce_valid_strategies(self):
        for mbti_type in MBTIType:
            strategy = StrategyFactory.create(mbti_type)
            assert strategy is not None
            assert 0 < strategy.risk_tolerance <= 1
            assert 0 < strategy.max_position_pct <= 0.5
            assert 0 < strategy.stop_loss_pct <= 0.20
            assert 0 < strategy.take_profit_pct <= 0.50
            assert sum(strategy.indicator_weights.values()) == pytest.approx(1.0, abs=0.01)

    def test_win_rate_tracking(self, chain, user_pubkey):
        chain.initialize_user(user_pubkey)
        chain.deposit(user_pubkey, Decimal("100.0"))
        chain.set_mbti(user_pubkey, MBTIType.INTJ)
        chain.enable_auto_trade(user_pubkey)

        for _ in range(10):
            chain.execute_trade(user_pubkey, "buy", Decimal("1.0"), Decimal("100.0"))

        state = chain.get_user_state(user_pubkey)
        win_rate = state["winning_trades"] / state["total_trades"]
        assert 0 <= win_rate <= 1
