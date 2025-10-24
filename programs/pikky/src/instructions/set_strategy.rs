use anchor_lang::prelude::*;

use crate::state::{TradingAgent, UserAccount, MbtiProfile, MbtiType};
use crate::error::PikkyError;
use crate::utils::{TRADING_AGENT_SEED, USER_ACCOUNT_SEED, BPS_DENOMINATOR, MAX_LEVERAGE};

/// Set or update the user's MBTI-based trading strategy.
#[derive(Accounts)]
pub struct SetStrategy<'info> {
    #[account(
        seeds = [TRADING_AGENT_SEED, trading_agent.authority.as_ref()],
        bump = trading_agent.bump,
    )]
    pub trading_agent: Account<'info, TradingAgent>,

    #[account(
        mut,
        seeds = [USER_ACCOUNT_SEED, trading_agent.key().as_ref(), owner.key().as_ref()],
        bump = user_account.bump,
        has_one = owner @ PikkyError::Unauthorized,
        has_one = trading_agent,
    )]
    pub user_account: Account<'info, UserAccount>,

    pub owner: Signer<'info>,
}

#[derive(AnchorSerialize, AnchorDeserialize)]
pub struct SetStrategyParams {
    /// MBTI type code (0-15)
    pub mbti_code: u8,
    /// Whether to use custom overrides or the MBTI defaults
    pub use_custom: bool,
    /// Custom max position size in BPS (only used if use_custom = true)
    pub custom_max_position_bps: Option<u16>,
    /// Custom max drawdown in BPS
    pub custom_max_drawdown_bps: Option<u16>,
    /// Custom trade cooldown in seconds
    pub custom_cooldown_secs: Option<i64>,
    /// Custom leverage factor (100 = 1x)
    pub custom_leverage: Option<u16>,
    /// Custom slippage tolerance in BPS
    pub custom_slippage_bps: Option<u16>,
    /// Custom minimum confidence (0-100)
    pub custom_min_confidence: Option<u8>,
    /// Custom take-profit in BPS
    pub custom_take_profit_bps: Option<u16>,
    /// Custom stop-loss in BPS
    pub custom_stop_loss_bps: Option<u16>,
}

pub fn handler_set_strategy(
    ctx: Context<SetStrategy>,
    params: SetStrategyParams,
) -> Result<()> {
    // Validate MBTI type
    let mbti_type = MbtiType::from_code(params.mbti_code)
        .ok_or(PikkyError::InvalidMbtiType)?;

    // Start with MBTI defaults
    let mut profile = MbtiProfile::default_for(mbti_type);

    // Apply custom overrides if requested
    if params.use_custom {
        if let Some(max_pos) = params.custom_max_position_bps {
            require!(
                max_pos > 0 && max_pos <= BPS_DENOMINATOR as u16,
                PikkyError::InvalidFeeBps
            );
            profile.max_position_bps = max_pos;
        }

        if let Some(max_dd) = params.custom_max_drawdown_bps {
            require!(
                max_dd > 0 && max_dd <= BPS_DENOMINATOR as u16,
                PikkyError::InvalidFeeBps
            );
            profile.max_drawdown_bps = max_dd;
        }

        if let Some(cooldown) = params.custom_cooldown_secs {
            require!(cooldown >= 0, PikkyError::InvalidFeeBps);
            profile.trade_cooldown_secs = cooldown;
        }

        if let Some(leverage) = params.custom_leverage {
            require!(
                leverage >= 100 && leverage <= MAX_LEVERAGE,
                PikkyError::InvalidFeeBps
            );
            profile.leverage_factor = leverage;
        }

        if let Some(slippage) = params.custom_slippage_bps {
            require!(
                slippage <= 1000, // max 10% slippage
                PikkyError::SlippageExceeded
            );
            profile.slippage_tolerance_bps = slippage;
        }

        if let Some(confidence) = params.custom_min_confidence {
            require!(confidence <= 100, PikkyError::InvalidFeeBps);
            profile.min_confidence = confidence;
        }

        if let Some(tp) = params.custom_take_profit_bps {
            require!(tp > 0, PikkyError::InvalidTakeProfit);
            profile.take_profit_bps = tp;
        }

        if let Some(sl) = params.custom_stop_loss_bps {
            require!(sl > 0, PikkyError::InvalidStopLoss);
            profile.stop_loss_bps = sl;
        }
    }

    // Apply to user account
    let user = &mut ctx.accounts.user_account;
    user.mbti_profile = profile;
    user.strategy_configured = true;

    msg!(
        "Strategy set for user {}: {} ({}). Max position: {} bps, leverage: {}x, cooldown: {}s",
        user.owner,
        mbti_type.name(),
        if params.use_custom { "custom" } else { "default" },
        user.mbti_profile.max_position_bps,
        user.mbti_profile.leverage_factor as f64 / 100.0,
        user.mbti_profile.trade_cooldown_secs,
    );

    Ok(())
}

/// Update the agent's fee configuration (authority only).
#[derive(Accounts)]
pub struct UpdateFees<'info> {
    #[account(
        mut,
        seeds = [TRADING_AGENT_SEED, trading_agent.authority.as_ref()],
        bump = trading_agent.bump,
        has_one = authority @ PikkyError::Unauthorized,
    )]
    pub trading_agent: Account<'info, TradingAgent>,

    pub authority: Signer<'info>,
}

#[derive(AnchorSerialize, AnchorDeserialize)]
pub struct UpdateFeesParams {
    /// New fee in basis points
    pub fee_bps: u16,
    /// New fee receiver pubkey (pass Pubkey::default() to keep current)
    pub new_fee_receiver: Option<Pubkey>,
}

pub fn handler_update_fees(
    ctx: Context<UpdateFees>,
    params: UpdateFeesParams,
) -> Result<()> {
    require!(params.fee_bps <= 500, PikkyError::InvalidFeeBps);

    let agent = &mut ctx.accounts.trading_agent;
    agent.fee_bps = params.fee_bps;

    if let Some(new_receiver) = params.new_fee_receiver {
        if new_receiver != Pubkey::default() {
            agent.fee_receiver = new_receiver;
        }
    }

    msg!(
        "Agent fees updated: {} bps, receiver: {}",
        agent.fee_bps,
        agent.fee_receiver,
    );

    Ok(())
}
