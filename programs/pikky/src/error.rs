use anchor_lang::prelude::*;

#[error_code]
pub enum PikkyError {
    #[msg("Unauthorized: only the agent authority can perform this action")]
    Unauthorized,

    #[msg("Invalid MBTI type code provided")]
    InvalidMbtiType,

    #[msg("Deposit amount must be greater than zero")]
    ZeroDeposit,

    #[msg("Insufficient funds for withdrawal")]
    InsufficientFunds,

    #[msg("Trade size exceeds maximum allowed position size")]
    ExceedsMaxPosition,

    #[msg("Trade size is below the minimum threshold")]
    BelowMinTradeSize,

    #[msg("Position is already closed")]
    PositionAlreadyClosed,

    #[msg("Position is still open and cannot be settled")]
    PositionStillOpen,

    #[msg("Invalid price feed: price must be positive")]
    InvalidPrice,

    #[msg("Price feed is stale beyond acceptable threshold")]
    StalePriceFeed,

    #[msg("Slippage tolerance exceeded on this trade")]
    SlippageExceeded,

    #[msg("Risk limit reached: aggregate exposure exceeds threshold for this MBTI profile")]
    RiskLimitExceeded,

    #[msg("Strategy not configured: set an MBTI profile before trading")]
    StrategyNotConfigured,

    #[msg("x402 payment verification failed")]
    X402PaymentInvalid,

    #[msg("x402 payment has already been consumed")]
    X402PaymentAlreadyUsed,

    #[msg("x402 payment amount does not match the expected fee")]
    X402PaymentAmountMismatch,

    #[msg("x402 payment has expired")]
    X402PaymentExpired,

    #[msg("Maximum number of open positions reached")]
    MaxPositionsReached,

    #[msg("Arithmetic overflow in calculation")]
    MathOverflow,

    #[msg("Invalid stop-loss price relative to entry")]
    InvalidStopLoss,

    #[msg("Invalid take-profit price relative to entry")]
    InvalidTakeProfit,

    #[msg("Agent is currently paused by authority")]
    AgentPaused,

    #[msg("Cooldown period not elapsed since last trade")]
    CooldownActive,

    #[msg("Invalid fee basis points: must be <= 10000")]
    InvalidFeeBps,

    #[msg("Token mint mismatch")]
    MintMismatch,
}
