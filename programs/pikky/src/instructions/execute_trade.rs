use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

use crate::state::{
    TradingAgent, UserAccount, TradePosition, X402PaymentRecord,
    TradeDirection, PositionStatus,
};
use crate::error::PikkyError;
use crate::utils::*;

/// Execute a new trade based on the user's MBTI strategy.
#[derive(Accounts)]
#[instruction(params: ExecuteTradeParams)]
pub struct ExecuteTrade<'info> {
    #[account(
        mut,
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

    #[account(
        init,
        payer = owner,
        space = TradePosition::LEN,
        seeds = [POSITION_SEED, user_account.key().as_ref(), &params.position_id.to_le_bytes()],
        bump,
    )]
    pub position: Account<'info, TradePosition>,

    /// The x402 payment record that authorizes this trade.
    #[account(
        mut,
        seeds = [X402_PAYMENT_SEED, user_account.key().as_ref(), &payment_record.payment_hash],
        bump = payment_record.bump,
        constraint = !payment_record.consumed @ PikkyError::X402PaymentAlreadyUsed,
        constraint = payment_record.user_account == user_account.key() @ PikkyError::X402PaymentInvalid,
    )]
    pub payment_record: Account<'info, X402PaymentRecord>,

    /// The agent's token vault for fee collection.
    #[account(
        mut,
        constraint = vault.key() == trading_agent.vault @ PikkyError::MintMismatch,
    )]
    pub vault: Account<'info, TokenAccount>,

    /// Fee receiver token account.
    #[account(
        mut,
        constraint = fee_receiver_token.owner == trading_agent.fee_receiver @ PikkyError::Unauthorized,
    )]
    pub fee_receiver_token: Account<'info, TokenAccount>,

    #[account(mut)]
    pub owner: Signer<'info>,

    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
}

#[derive(AnchorSerialize, AnchorDeserialize)]
pub struct ExecuteTradeParams {
    /// Sequential position ID for the user
    pub position_id: u64,
    /// The base asset mint address
    pub base_mint: Pubkey,
    /// Trade direction (0 = Long, 1 = Short)
    pub direction: u8,
    /// Trade size in quote token units
    pub size: u64,
    /// Current market price (scaled by 1e6)
    pub price: u64,
    /// Price feed timestamp
    pub price_timestamp: i64,
    /// AI confidence score for this trade (0-100)
    pub confidence: u8,
    /// Optional explicit stop-loss (0 = use MBTI default)
    pub stop_loss: u64,
    /// Optional explicit take-profit (0 = use MBTI default)
    pub take_profit: u64,
}

pub fn handler_execute_trade(
    ctx: Context<ExecuteTrade>,
    params: ExecuteTradeParams,
) -> Result<()> {
    let clock = Clock::get()?;
    let agent = &ctx.accounts.trading_agent;

    // Agent must not be paused
    require!(!agent.paused, PikkyError::AgentPaused);

    // User must have a configured strategy
    let user = &ctx.accounts.user_account;
    require!(user.strategy_configured, PikkyError::StrategyNotConfigured);

    // Validate price
    validate_price(params.price, params.price_timestamp, clock.unix_timestamp)?;

    // Validate trade size
    require!(params.size >= MIN_TRADE_SIZE, PikkyError::BelowMinTradeSize);

    // Parse direction
    let direction = match params.direction {
        0 => TradeDirection::Long,
        1 => TradeDirection::Short,
        _ => return Err(PikkyError::InvalidMbtiType.into()),
    };

    let profile = &user.mbti_profile;

    // Validate trade against MBTI profile risk parameters
    validate_trade_against_profile(
        profile,
        params.size,
        user.balance,
        user.open_positions,
        user.last_trade_at,
        clock.unix_timestamp,
        params.confidence,
    )?;

    // Determine leverage (capped by profile and global max)
    let leverage = profile.leverage_factor.min(MAX_LEVERAGE);

    // Calculate notional and fee
    let notional = calculate_leveraged_notional(params.size, params.price, leverage)?;
    let fee = calculate_fee(notional, agent.fee_bps)?;

    // Ensure user has sufficient balance for size + fee
    let total_required = params
        .size
        .checked_add(fee)
        .ok_or(PikkyError::MathOverflow)?;
    require!(user.balance >= total_required, PikkyError::InsufficientFunds);

    // Verify x402 payment hasn't expired
    let payment = &ctx.accounts.payment_record;
    require!(
        !is_payment_expired(payment.expires_at, clock.unix_timestamp),
        PikkyError::X402PaymentExpired
    );

    // Determine stop-loss and take-profit prices
    let stop_loss = if params.stop_loss > 0 {
        params.stop_loss
    } else {
        derive_stop_loss(params.price, profile, direction)?
    };

    let take_profit = if params.take_profit > 0 {
        params.take_profit
    } else {
        derive_take_profit(params.price, profile, direction)?
    };

    // Validate SL/TP
    validate_sl_tp(params.price, stop_loss, take_profit, direction)?;

    // Transfer fee from vault to fee receiver using PDA signer
    if fee > 0 {
        let authority_key = agent.authority;
        let agent_seeds = &[
            TRADING_AGENT_SEED,
            authority_key.as_ref(),
            &[agent.bump],
        ];
        let signer_seeds = &[&agent_seeds[..]];

        let fee_transfer_ctx = CpiContext::new_with_signer(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.vault.to_account_info(),
                to: ctx.accounts.fee_receiver_token.to_account_info(),
                authority: ctx.accounts.trading_agent.to_account_info(),
            },
            signer_seeds,
        );
        token::transfer(fee_transfer_ctx, fee)?;
    }

    // Initialize position
    let position = &mut ctx.accounts.position;
    position.bump = ctx.bumps.position;
    position.user_account = ctx.accounts.user_account.key();
    position.position_id = params.position_id;
    position.base_mint = params.base_mint;
    position.direction = direction;
    position.size = params.size;
    position.entry_price = params.price;
    position.exit_price = 0;
    position.leverage = leverage;
    position.stop_loss = stop_loss;
    position.take_profit = take_profit;
    position.pnl = 0;
    position.status = PositionStatus::Open;
    position.mbti_type = profile.mbti_type;
    position.confidence_score = params.confidence;
    position.opened_at = clock.unix_timestamp;
    position.closed_at = 0;
    position.fee_paid = fee;
    position._reserved = [0u8; 32];

    // Update user account
    let user = &mut ctx.accounts.user_account;
    user.balance = user
        .balance
        .checked_sub(total_required)
        .ok_or(PikkyError::MathOverflow)?;
    user.open_positions = user
        .open_positions
        .checked_add(1)
        .ok_or(PikkyError::MathOverflow)?;
    user.total_trades = user
        .total_trades
        .checked_add(1)
        .ok_or(PikkyError::MathOverflow)?;
    user.last_trade_at = clock.unix_timestamp;

    // Mark x402 payment as consumed
    let payment = &mut ctx.accounts.payment_record;
    payment.consumed = true;
    payment.consumed_by_position = params.position_id;

    // Update agent stats
    let agent = &mut ctx.accounts.trading_agent;
    agent.total_trades = agent
        .total_trades
        .checked_add(1)
        .ok_or(PikkyError::MathOverflow)?;
    agent.total_fees_collected = agent
        .total_fees_collected
        .checked_add(fee)
        .ok_or(PikkyError::MathOverflow)?;
    agent.last_activity = clock.unix_timestamp;

    msg!(
        "Trade executed: {} {} @ {} ({}x leverage). Position #{}, confidence: {}%, fee: {}",
        if direction == TradeDirection::Long { "LONG" } else { "SHORT" },
        params.size,
        params.price,
        leverage as f64 / 100.0,
        params.position_id,
        params.confidence,
        fee,
    );

    Ok(())
}

/// Close an existing position at the current market price.
#[derive(Accounts)]
pub struct ClosePosition<'info> {
    #[account(
        mut,
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

    #[account(
        mut,
        seeds = [POSITION_SEED, user_account.key().as_ref(), &position.position_id.to_le_bytes()],
        bump = position.bump,
        constraint = position.user_account == user_account.key() @ PikkyError::Unauthorized,
        constraint = position.status == PositionStatus::Open @ PikkyError::PositionAlreadyClosed,
    )]
    pub position: Account<'info, TradePosition>,

    /// The agent's token vault.
    #[account(
        mut,
        constraint = vault.key() == trading_agent.vault @ PikkyError::MintMismatch,
    )]
    pub vault: Account<'info, TokenAccount>,

    #[account(mut)]
    pub owner: Signer<'info>,

    pub token_program: Program<'info, Token>,
}

#[derive(AnchorSerialize, AnchorDeserialize)]
pub struct ClosePositionParams {
    /// Current exit price (scaled by 1e6)
    pub exit_price: u64,
    /// Price feed timestamp
    pub price_timestamp: i64,
    /// Close reason: 0 = manual, 1 = stop-loss, 2 = take-profit
    pub close_reason: u8,
}

pub fn handler_close_position(
    ctx: Context<ClosePosition>,
    params: ClosePositionParams,
) -> Result<()> {
    let clock = Clock::get()?;

    // Validate exit price
    validate_price(params.exit_price, params.price_timestamp, clock.unix_timestamp)?;

    let position = &ctx.accounts.position;

    // Calculate PnL
    let pnl = calculate_pnl(
        position.size,
        position.entry_price,
        params.exit_price,
        position.leverage,
        position.direction,
    )?;

    // Determine close status
    let close_status = match params.close_reason {
        1 => PositionStatus::StopLossTriggered,
        2 => PositionStatus::TakeProfitTriggered,
        _ => PositionStatus::Closed,
    };

    // Calculate the amount to return to user balance
    // Original size was deducted on open. Now return size + pnl (clamped to 0 minimum).
    let return_amount = if pnl >= 0 {
        position
            .size
            .checked_add(pnl as u64)
            .ok_or(PikkyError::MathOverflow)?
    } else {
        let loss = (-pnl) as u64;
        position.size.saturating_sub(loss)
    };

    // Update position
    let position = &mut ctx.accounts.position;
    position.exit_price = params.exit_price;
    position.pnl = pnl;
    position.status = close_status;
    position.closed_at = clock.unix_timestamp;

    // Update user account
    let user = &mut ctx.accounts.user_account;
    user.balance = user
        .balance
        .checked_add(return_amount)
        .ok_or(PikkyError::MathOverflow)?;
    user.realized_pnl = user
        .realized_pnl
        .checked_add(pnl)
        .ok_or(PikkyError::MathOverflow)?;
    user.open_positions = user.open_positions.saturating_sub(1);

    if pnl > 0 {
        user.winning_trades = user
            .winning_trades
            .checked_add(1)
            .ok_or(PikkyError::MathOverflow)?;
    }

    // Update agent
    let agent = &mut ctx.accounts.trading_agent;
    agent.last_activity = clock.unix_timestamp;

    msg!(
        "Position #{} closed @ {}. PnL: {}, Status: {:?}. Returned {} to balance.",
        position.position_id,
        params.exit_price,
        pnl,
        close_status,
        return_amount,
    );

    Ok(())
}
