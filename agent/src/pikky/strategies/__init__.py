"""
PIKKY MBTI-based trading strategies.

Each strategy maps to a personality archetype with distinct trading characteristics:
- INTJ "The Sniper": High conviction, few trades, mathematical precision
- ENFP "The FOMO King": Momentum-based, aggressive breakout buying
- ISTJ "The DCA Machine": Time-weighted accumulation, ignores noise
- ENTP "The Degen": Leveraged contrarian plays, high risk tolerance
"""

from pikky.strategies.base import BaseStrategy
from pikky.strategies.enfp import EnfpStrategy
from pikky.strategies.entp import EntpStrategy
from pikky.strategies.intj import IntjStrategy
from pikky.strategies.istj import IstjStrategy
from pikky.strategies.registry import StrategyRegistry

__all__ = [
    "BaseStrategy",
    "EnfpStrategy",
    "EntpStrategy",
    "IntjStrategy",
    "IstjStrategy",
    "StrategyRegistry",
]
