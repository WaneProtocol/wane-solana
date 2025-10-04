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