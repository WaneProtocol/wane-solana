"""
PIKKY - x402-based Solana auto-trading AI agent with MBTI-based trading strategies.

PIKKY receives x402 payments to activate personalized trading strategies based on
the user's MBTI personality type. Each type maps to a distinct trading philosophy,
risk profile, and execution style on Solana DEXs via Jupiter aggregator.
"""

__version__ = "0.1.0"
__author__ = "PIKKY Team"

from pikky.config import PikkyConfig
from pikky.engine import TradingEngine
from pikky.trader import TradeExecutor
from pikky.x402 import X402PaymentHandler

__all__ = [
    "__version__",
    "PikkyConfig",
    "TradingEngine",
    "TradeExecutor",
    "X402PaymentHandler",
]

