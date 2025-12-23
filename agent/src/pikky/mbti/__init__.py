"""
PIKKY MBTI personality typing module.

Maps the 16 Myers-Briggs personality types to trading characteristics.
Provides type definitions, profiles, and a matcher that can suggest
an MBTI type based on user preferences or on-chain trading behavior.
"""

from pikky.mbti.matcher import MbtiMatcher
from pikky.mbti.types import MbtiProfile, MbtiType

__all__ = [
    "MbtiMatcher",
    "MbtiProfile",
    "MbtiType",
]
