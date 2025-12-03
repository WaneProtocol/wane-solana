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


class FeeConfig(BaseSettings):
    """Fee and payment configuration."""

    model_config = {"env_prefix": "PIKKY_FEE_"}

    x402_base_fee_lamports: int = Field(
        default=5_000_000,
        description="Base fee in lamports for x402 payment (0.005 SOL)",
        ge=1000,
    )
    x402_session_duration_seconds: int = Field(
        default=3600,
        description="Duration of an x402 payment session in seconds",
        ge=60,
    )
    x402_fee_multiplier_per_mbti: dict[str, float] = Field(
        default_factory=lambda: {
            "INTJ": 1.5,
            "ENTJ": 1.5,
            "ENTP": 2.0,
            "INTP": 1.2,
            "INFJ": 1.0,
            "INFP": 1.0,
            "ENFJ": 1.1,
            "ENFP": 1.3,
            "ISTJ": 0.8,
            "ISFJ": 0.8,
            "ESTJ": 1.0,
            "ESFJ": 0.9,
            "ISTP": 1.1,
            "ISFP": 0.9,
            "ESTP": 1.4,
            "ESFP": 1.2,
        },
        description="Fee multiplier per MBTI type based on strategy complexity",
    )
    priority_fee_lamports: int = Field(
        default=100_000,
        description="Priority fee for Solana transactions in lamports",
        ge=0,
    )
    compute_unit_limit: int = Field(
        default=400_000,
        description="Compute unit limit for Solana transactions",
        ge=200_000,
        le=1_400_000,
    )
    refund_window_seconds: int = Field(
        default=300,
        description="Window in seconds after payment where refund is possible",
        ge=0,
    )


class JupiterConfig(BaseSettings):
    """Jupiter aggregator configuration."""

    model_config = {"env_prefix": "PIKKY_JUPITER_"}

    api_url: str = Field(
        default="https://quote-api.jup.ag/v6",
        description="Jupiter V6 API base URL",
    )
    price_api_url: str = Field(
        default="https://price.jup.ag/v6",
        description="Jupiter price API base URL",
    )
    max_accounts: int = Field(
        default=64,
        description="Maximum number of accounts in a Jupiter swap transaction",
        ge=10,
        le=64,
    )
    swap_mode: str = Field(
        default="ExactIn",
        description="Default swap mode: ExactIn or ExactOut",
    )
    dex_filter: list[str] = Field(
        default_factory=lambda: ["Raydium", "Orca", "Meteora", "Phoenix"],
        description="DEXs to include in routing",
    )
    only_direct_routes: bool = Field(
        default=False,
        description="Only use direct routes (no multi-hop)",
    )
    max_retries: int = Field(
        default=3,
        description="Maximum retries for Jupiter API calls",
        ge=1,
        le=10,
    )
    quote_timeout_seconds: float = Field(
        default=10.0,
        description="Timeout for quote requests in seconds",
        ge=1.0,
    )


class MbtiDefaultConfig(BaseSettings):
    """Default MBTI-related configuration."""

    model_config = {"env_prefix": "PIKKY_MBTI_"}

    default_type: str = Field(
        default="ISTJ",
        description="Default MBTI type for new users",
    )
    allow_type_change: bool = Field(
        default=True,
        description="Whether users can change their MBTI type",
    )
    type_change_cooldown_hours: int = Field(
        default=24,
        description="Hours between MBTI type changes",
        ge=0,
    )
    behavior_analysis_min_trades: int = Field(
        default=10,
        description="Minimum trades before behavior-based MBTI suggestion",
        ge=5,
    )

    @field_validator("default_type")
    @classmethod
    def validate_mbti_type(cls, v: str) -> str:
        """Ensure the default type is a valid MBTI type."""
        valid_types = {
            "INTJ", "INTP", "ENTJ", "ENTP",
            "INFJ", "INFP", "ENFJ", "ENFP",
            "ISTJ", "ISFJ", "ESTJ", "ESFJ",
            "ISTP", "ISFP", "ESTP", "ESFP",
        }
        upper = v.upper()
        if upper not in valid_types:
            raise ValueError(f"Invalid MBTI type: {v}. Must be one of {valid_types}")
        return upper


class PikkyConfig(BaseSettings):
    """Root configuration for the PIKKY trading agent."""

    model_config = {"env_prefix": "PIKKY_", "env_nested_delimiter": "__"}

    network: Network = Field(
        default=Network.MAINNET,
        description="Solana network to connect to",
    )
    rpc_url: str = Field(
        default="https://api.mainnet-beta.solana.com",
        description="Solana RPC endpoint URL",
    )
    rpc_ws_url: Optional[str] = Field(
        default=None,
        description="Solana WebSocket RPC endpoint (derived from rpc_url if not set)",
    )
    backup_rpc_urls: list[str] = Field(
        default_factory=list,
        description="Backup RPC endpoints for failover",
    )
    wallet_keypair_path: Optional[str] = Field(
        default=None,
        description="Path to the agent wallet keypair JSON file",
    )
    wallet_private_key: Optional[str] = Field(
        default=None,
        description="Base58-encoded private key (alternative to keypair file)",
    )
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Application log level",
    )
    engine_tick_interval_seconds: float = Field(
        default=5.0,
        description="Main engine loop tick interval in seconds",
        ge=0.5,
        le=60.0,
    )
    market_scan_interval_seconds: float = Field(
        default=30.0,
        description="Interval between market scans in seconds",
        ge=5.0,
    )
    pnl_report_interval_seconds: float = Field(
        default=300.0,
        description="Interval between PnL reports in seconds",
        ge=30.0,
    )
    health_check_port: int = Field(
        default=8080,
        description="Port for health check HTTP server",
        ge=1024,
        le=65535,
    )
    enable_paper_trading: bool = Field(
        default=True,
        description="Enable paper trading mode (no real transactions)",
    )
    token_watchlist: list[str] = Field(
        default_factory=lambda: [
            "So11111111111111111111111111111111111111112",   # wSOL
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",   # USDT
            "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # BONK
            "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",    # JUP
        ],
        description="Default token mint addresses to watch",
    )

    risk: RiskConfig = Field(default_factory=RiskConfig)
    fees: FeeConfig = Field(default_factory=FeeConfig)
    jupiter: JupiterConfig = Field(default_factory=JupiterConfig)
    mbti: MbtiDefaultConfig = Field(default_factory=MbtiDefaultConfig)

    @field_validator("rpc_ws_url", mode="before")
    @classmethod
    def derive_ws_url(cls, v: Optional[str], info: object) -> Optional[str]:
        """Derive WebSocket URL from HTTP URL if not explicitly set."""
        if v is not None:
            return v
        return None

    def get_ws_url(self) -> str:
        """Get the WebSocket URL, deriving from RPC URL if needed."""
        if self.rpc_ws_url:
            return self.rpc_ws_url
        ws_url = self.rpc_url.replace("https://", "wss://").replace("http://", "ws://")
        return ws_url

    def get_fee_for_mbti(self, mbti_type: str) -> int:
        """Calculate the x402 fee for a given MBTI type."""
        multiplier = self.fees.x402_fee_multiplier_per_mbti.get(mbti_type.upper(), 1.0)
        return int(self.fees.x402_base_fee_lamports * multiplier)
