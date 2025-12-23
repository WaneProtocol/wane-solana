"""
MBTI type definitions and trading profiles.

Defines the MbtiType enum for all 16 personality types and the MbtiProfile
dataclass that encodes each type's trading characteristics including risk
tolerance, trade frequency, holding period, position sizing, and emotional
factors.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MbtiType(str, Enum):
    """All 16 MBTI personality types."""

    INTJ = "INTJ"
    INTP = "INTP"
    ENTJ = "ENTJ"
    ENTP = "ENTP"
    INFJ = "INFJ"
    INFP = "INFP"
    ENFJ = "ENFJ"
    ENFP = "ENFP"
    ISTJ = "ISTJ"
    ISFJ = "ISFJ"
    ESTJ = "ESTJ"
    ESFJ = "ESFJ"
    ISTP = "ISTP"
    ISFP = "ISFP"
    ESTP = "ESTP"
    ESFP = "ESFP"


class TradeFrequency(str, Enum):
    """How often a type tends to trade."""

    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

