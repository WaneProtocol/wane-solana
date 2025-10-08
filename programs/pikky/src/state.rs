use anchor_lang::prelude::*;

/// The 16 MBTI personality types mapped to trading strategy archetypes.
#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, Debug, PartialEq, Eq)]
#[repr(u8)]
pub enum MbtiType {
    /// INTJ - "The Architect": systematic trend-following, low frequency, high conviction
    Intj = 0,
    /// INTP - "The Logician": mean-reversion quant, statistical arbitrage
    Intp = 1,
    /// ENTJ - "The Commander": aggressive momentum, high leverage
    Entj = 2,
    /// ENTP - "The Debater": contrarian plays, volatility harvesting
    Entp = 3,
    /// INFJ - "The Advocate": ESG-weighted, long-horizon value
    Infj = 4,
    /// INFP - "The Mediator": sentiment-driven, narrative trading
    Infp = 5,
    /// ENFJ - "The Protagonist": social-signal copy trading
    Enfj = 6,
    /// ENFP - "The Campaigner": hype-cycle momentum, meme awareness
    Enfp = 7,
    /// ISTJ - "The Logistician": conservative DCA, blue-chip only
    Istj = 8,
    /// ISFJ - "The Defender": capital preservation, hedged positions
    Isfj = 9,
    /// ESTJ - "The Executive": rule-based breakout trading
    Estj = 10,
    /// ESFJ - "The Consul": community-consensus following
    Esfj = 11,
    /// ISTP - "The Virtuoso": scalping, high-frequency micro trades
    Istp = 12,
    /// ISFP - "The Adventurer": artistic pattern recognition, chart-based
    Isfp = 13,
    /// ESTP - "The Entrepreneur": event-driven, news trading
    Estp = 14,
    /// ESFP - "The Entertainer": FOMO plays, social momentum
    Esfp = 15,
}

impl MbtiType {
    pub fn from_code(code: u8) -> Option<Self> {
        match code {
            0 => Some(Self::Intj),
            1 => Some(Self::Intp),
            2 => Some(Self::Entj),
            3 => Some(Self::Entp),
            4 => Some(Self::Infj),
            5 => Some(Self::Infp),
            6 => Some(Self::Enfj),
            7 => Some(Self::Enfp),
            8 => Some(Self::Istj),
            9 => Some(Self::Isfj),
            10 => Some(Self::Estj),
            11 => Some(Self::Esfj),
            12 => Some(Self::Istp),
            13 => Some(Self::Isfp),
            14 => Some(Self::Estp),
            15 => Some(Self::Esfp),
            _ => None,
        }
    }

    pub fn name(&self) -> &'static str {
        match self {
            Self::Intj => "INTJ",
            Self::Intp => "INTP",
            Self::Entj => "ENTJ",
            Self::Entp => "ENTP",
            Self::Infj => "INFJ",
            Self::Infp => "INFP",
            Self::Enfj => "ENFJ",
            Self::Enfp => "ENFP",
            Self::Istj => "ISTJ",
            Self::Isfj => "ISFJ",
            Self::Estj => "ESTJ",
            Self::Esfj => "ESFJ",
            Self::Istp => "ISTP",
            Self::Isfp => "ISFP",
            Self::Estp => "ESTP",
            Self::Esfp => "ESFP",
        }
    }
}

/// Direction of a trade position.
#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, Debug, PartialEq, Eq)]
#[repr(u8)]
pub enum TradeDirection {
    Long = 0,
    Short = 1,
}

/// Current status of a trade position.
#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, Debug, PartialEq, Eq)]
#[repr(u8)]
pub enum PositionStatus {
    Open = 0,
    Closed = 1,
    Liquidated = 2,
    StopLossTriggered = 3,
    TakeProfitTriggered = 4,
}

/// MBTI-derived trading strategy parameters stored on-chain.
#[derive(AnchorSerialize, AnchorDeserialize, Clone, Debug)]
pub struct MbtiProfile {
    /// The MBTI personality type
    pub mbti_type: MbtiType,
    /// Maximum position size as percentage of portfolio (basis points, e.g. 2500 = 25%)
    pub max_position_bps: u16,
    /// Risk tolerance: max drawdown before auto-close (basis points)
    pub max_drawdown_bps: u16,
    /// Preferred trade frequency cooldown in seconds
    pub trade_cooldown_secs: i64,
    /// Leverage multiplier (100 = 1x, 200 = 2x, max 500 = 5x)
    pub leverage_factor: u16,
    /// Slippage tolerance in basis points
    pub slippage_tolerance_bps: u16,
    /// Whether this strategy prefers trend-following (true) or mean-reversion (false)
    pub trend_following: bool,
    /// Minimum confidence score (0-100) from AI before executing
    pub min_confidence: u8,
    /// Take-profit threshold in basis points from entry
    pub take_profit_bps: u16,
    /// Stop-loss threshold in basis points from entry
    pub stop_loss_bps: u16,
}

impl MbtiProfile {
    pub const LEN: usize = 1 + 2 + 2 + 8 + 2 + 2 + 1 + 1 + 2 + 2;

    /// Build a default strategy profile for a given MBTI type.
    pub fn default_for(mbti_type: MbtiType) -> Self {
        match mbti_type {
            MbtiType::Intj => Self {
                mbti_type,
                max_position_bps: 2000,
                max_drawdown_bps: 500,
                trade_cooldown_secs: 3600,
                leverage_factor: 150,
                slippage_tolerance_bps: 30,
                trend_following: true,
                min_confidence: 75,
                take_profit_bps: 800,
                stop_loss_bps: 300,
            },
            MbtiType::Intp => Self {
                mbti_type,
                max_position_bps: 1500,
                max_drawdown_bps: 400,
                trade_cooldown_secs: 1800,
                leverage_factor: 100,
                slippage_tolerance_bps: 20,
                trend_following: false,
                min_confidence: 80,
                take_profit_bps: 500,
                stop_loss_bps: 250,
            },
            MbtiType::Entj => Self {
                mbti_type,
                max_position_bps: 3500,
                max_drawdown_bps: 1000,
                trade_cooldown_secs: 600,
                leverage_factor: 300,
                slippage_tolerance_bps: 75,
                trend_following: true,
                min_confidence: 60,
                take_profit_bps: 1500,
                stop_loss_bps: 500,
            },
            MbtiType::Entp => Self {
                mbti_type,
                max_position_bps: 2500,
                max_drawdown_bps: 800,
                trade_cooldown_secs: 900,
                leverage_factor: 200,
                slippage_tolerance_bps: 100,
                trend_following: false,
                min_confidence: 55,
                take_profit_bps: 2000,
                stop_loss_bps: 700,
            },
            MbtiType::Infj => Self {
                mbti_type,
                max_position_bps: 1500,
                max_drawdown_bps: 300,
                trade_cooldown_secs: 86400,
                leverage_factor: 100,
                slippage_tolerance_bps: 20,
                trend_following: true,
                min_confidence: 85,
                take_profit_bps: 1200,
                stop_loss_bps: 200,
            },
            MbtiType::Infp => Self {
                mbti_type,
                max_position_bps: 1800,
                max_drawdown_bps: 500,
                trade_cooldown_secs: 3600,
                leverage_factor: 100,
                slippage_tolerance_bps: 50,
                trend_following: true,
                min_confidence: 70,
                take_profit_bps: 1000,
                stop_loss_bps: 400,
            },
            MbtiType::Enfj => Self {
                mbti_type,
                max_position_bps: 2000,
                max_drawdown_bps: 600,
                trade_cooldown_secs: 1800,
                leverage_factor: 150,
                slippage_tolerance_bps: 40,
                trend_following: true,
                min_confidence: 65,
                take_profit_bps: 900,
                stop_loss_bps: 350,
            },
            MbtiType::Enfp => Self {
                mbti_type,
                max_position_bps: 3000,
                max_drawdown_bps: 900,
                trade_cooldown_secs: 300,
                leverage_factor: 250,
                slippage_tolerance_bps: 120,
                trend_following: true,
                min_confidence: 45,
                take_profit_bps: 2500,
                stop_loss_bps: 600,
            },
            MbtiType::Istj => Self {
                mbti_type,
                max_position_bps: 1000,
                max_drawdown_bps: 200,
                trade_cooldown_secs: 86400,
                leverage_factor: 100,
                slippage_tolerance_bps: 15,
                trend_following: true,
                min_confidence: 90,
                take_profit_bps: 400,
                stop_loss_bps: 150,
            },
            MbtiType::Isfj => Self {
                mbti_type,
                max_position_bps: 800,
                max_drawdown_bps: 150,
                trade_cooldown_secs: 86400,
                leverage_factor: 100,
                slippage_tolerance_bps: 10,
                trend_following: false,
                min_confidence: 92,
                take_profit_bps: 300,
                stop_loss_bps: 100,
            },
            MbtiType::Estj => Self {
                mbti_type,
                max_position_bps: 2500,
                max_drawdown_bps: 600,
                trade_cooldown_secs: 1800,
                leverage_factor: 200,
                slippage_tolerance_bps: 50,
                trend_following: true,
                min_confidence: 70,
                take_profit_bps: 1000,
                stop_loss_bps: 400,
            },
            MbtiType::Esfj => Self {
                mbti_type,
                max_position_bps: 1800,
                max_drawdown_bps: 400,
                trade_cooldown_secs: 3600,
                leverage_factor: 100,
                slippage_tolerance_bps: 30,
                trend_following: true,
                min_confidence: 75,
                take_profit_bps: 700,
                stop_loss_bps: 300,
            },
            MbtiType::Istp => Self {
                mbti_type,
                max_position_bps: 1200,
                max_drawdown_bps: 300,
                trade_cooldown_secs: 60,
                leverage_factor: 150,
                slippage_tolerance_bps: 15,
                trend_following: false,
                min_confidence: 65,
                take_profit_bps: 200,
                stop_loss_bps: 100,
            },
            MbtiType::Isfp => Self {
                mbti_type,
                max_position_bps: 2000,
                max_drawdown_bps: 500,
                trade_cooldown_secs: 1800,
                leverage_factor: 100,
                slippage_tolerance_bps: 40,
                trend_following: true,
                min_confidence: 70,
                take_profit_bps: 800,
                stop_loss_bps: 350,
            },
            MbtiType::Estp => Self {
                mbti_type,
                max_position_bps: 3000,
                max_drawdown_bps: 800,
                trade_cooldown_secs: 120,
                leverage_factor: 300,
                slippage_tolerance_bps: 100,
                trend_following: true,
                min_confidence: 50,
                take_profit_bps: 1800,
                stop_loss_bps: 500,
            },
            MbtiType::Esfp => Self {
                mbti_type,
                max_position_bps: 3500,
                max_drawdown_bps: 1000,
                trade_cooldown_secs: 180,
                leverage_factor: 250,
                slippage_tolerance_bps: 150,
                trend_following: true,
                min_confidence: 40,
                take_profit_bps: 3000,
                stop_loss_bps: 800,
            },
        }
    }
}

/// Global trading agent configuration account.
/// PDA seeds: [b"trading_agent", authority.key().as_ref()]
#[account]
pub struct TradingAgent {
    /// Bump seed for PDA derivation
    pub bump: u8,
    /// The wallet that controls this agent
    pub authority: Pubkey,
    /// The SPL token mint used for deposits/trading (e.g. USDC)
    pub quote_mint: Pubkey,
    /// The agent's token vault (ATA owned by this PDA)
    pub vault: Pubkey,
    /// Protocol fee destination wallet
    pub fee_receiver: Pubkey,
    /// Protocol fee in basis points (e.g. 50 = 0.5%)
    pub fee_bps: u16,
    /// Whether the agent is paused
    pub paused: bool,
    /// Total deposits received across all users (in token base units)
    pub total_deposits: u64,
    /// Total withdrawals across all users
    pub total_withdrawals: u64,
    /// Total trades executed
    pub total_trades: u64,
    /// Total protocol fees collected
    pub total_fees_collected: u64,
    /// Unix timestamp of agent creation
    pub created_at: i64,
    /// Unix timestamp of last activity
    pub last_activity: i64,
    /// Reserved space for future upgrades
    pub _reserved: [u8; 128],
}

impl TradingAgent {
    pub const LEN: usize = 8  // discriminator
        + 1   // bump
        + 32  // authority
        + 32  // quote_mint
        + 32  // vault
        + 32  // fee_receiver
        + 2   // fee_bps
        + 1   // paused
        + 8   // total_deposits
        + 8   // total_withdrawals
        + 8   // total_trades
        + 8   // total_fees_collected
        + 8   // created_at
        + 8   // last_activity
        + 128; // reserved
}

/// Per-user account tracking deposits, PnL, and strategy selection.
/// PDA seeds: [b"user_account", trading_agent.key().as_ref(), owner.key().as_ref()]
#[account]