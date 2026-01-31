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

