"""
Configuration management for PIKKY trading agent.

Uses pydantic-settings for environment variable loading with validation,
type coercion, and sensible defaults for all operational parameters.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Network(str, Enum):
    """Solana network selection."""

    MAINNET = "mainnet-beta"
    DEVNET = "devnet"
    TESTNET = "testnet"
    LOCALNET = "localnet"


class LogLevel(str, Enum):
    """Application log level."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class RiskConfig(BaseSettings):
    """Risk management configuration."""

    model_config = {"env_prefix": "PIKKY_RISK_"}

    max_position_size_sol: float = Field(
        default=10.0,
        description="Maximum position size in SOL for any single trade",
        ge=0.01,
    )
    max_portfolio_exposure_pct: float = Field(
        default=0.25,
        description="Maximum percentage of portfolio in active positions",
        ge=0.01,
        le=1.0,
    )
    max_concurrent_positions: int = Field(
        default=5,
        description="Maximum number of concurrent open positions",
        ge=1,
        le=50,
    )
    max_daily_loss_pct: float = Field(
        default=0.10,
        description="Maximum daily loss as percentage of starting balance",
        ge=0.01,
        le=1.0,
    )
    max_single_trade_loss_pct: float = Field(
        default=0.05,
        description="Maximum loss on a single trade as percentage of portfolio",
        ge=0.005,
        le=0.5,
    )
    default_slippage_bps: int = Field(
        default=50,
        description="Default slippage tolerance in basis points",
        ge=1,
        le=1000,
    )
    min_liquidity_usd: float = Field(
        default=10000.0,
        description="Minimum pool liquidity in USD to consider for trading",
        ge=100.0,
    )
    cool_down_seconds: int = Field(
        default=30,
        description="Minimum seconds between trades on same token",
        ge=0,
    )
    max_drawdown_pct: float = Field(
        default=0.20,
        description="Maximum drawdown before halting all trading",
        ge=0.05,
        le=0.5,
    )
    trailing_stop_activation_pct: float = Field(
        default=0.05,
        description="Profit percentage to activate trailing stop",
        ge=0.01,
    )
    trailing_stop_distance_pct: float = Field(
        default=0.03,
        description="Distance of trailing stop from peak",
        ge=0.005,
    )

