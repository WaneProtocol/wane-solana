use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, Token, TokenAccount, Transfer};

use crate::state::{TradingAgent, UserAccount, X402PaymentRecord};
use crate::error::PikkyError;
use crate::utils::{
    TRADING_AGENT_SEED, USER_ACCOUNT_SEED, X402_PAYMENT_SEED,
    compute_payment_hash, is_payment_expired,
};

/// Deposit tokens into the user's trading account.
#[derive(Accounts)]
pub struct Deposit<'info> {
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

    /// The agent's token vault.
    #[account(
        mut,
        constraint = vault.key() == trading_agent.vault @ PikkyError::MintMismatch,
    )]
    pub vault: Account<'info, TokenAccount>,

    /// The user's token account to deposit from.
    #[account(
        mut,
        constraint = user_token_account.mint == trading_agent.quote_mint @ PikkyError::MintMismatch,
        constraint = user_token_account.owner == owner.key() @ PikkyError::Unauthorized,
    )]
    pub user_token_account: Account<'info, TokenAccount>,

    #[account(mut)]
    pub owner: Signer<'info>,

    pub token_program: Program<'info, Token>,
}

#[derive(AnchorSerialize, AnchorDeserialize)]
pub struct DepositParams {
    pub amount: u64,
}

pub fn handler_deposit(ctx: Context<Deposit>, params: DepositParams) -> Result<()> {
    require!(params.amount > 0, PikkyError::ZeroDeposit);
    require!(!ctx.accounts.trading_agent.paused, PikkyError::AgentPaused);

    let clock = Clock::get()?;

    // Transfer tokens from user to vault
    let transfer_ctx = CpiContext::new(
        ctx.accounts.token_program.to_account_info(),
        Transfer {
            from: ctx.accounts.user_token_account.to_account_info(),
            to: ctx.accounts.vault.to_account_info(),
            authority: ctx.accounts.owner.to_account_info(),
        },
    );
    token::transfer(transfer_ctx, params.amount)?;

    // Update user balance
    let user = &mut ctx.accounts.user_account;
    user.balance = user
        .balance
        .checked_add(params.amount)
        .ok_or(PikkyError::MathOverflow)?;

    // Update agent totals
    let agent = &mut ctx.accounts.trading_agent;
    agent.total_deposits = agent
        .total_deposits
        .checked_add(params.amount)
        .ok_or(PikkyError::MathOverflow)?;
    agent.last_activity = clock.unix_timestamp;

    msg!(
        "Deposited {} tokens for user {}. New balance: {}",
        params.amount,
        user.owner,
        user.balance,
    );

    Ok(())
}

/// Record and verify an x402 payment for accessing trading services.
#[derive(Accounts)]
#[instruction(params: X402DepositParams)]
pub struct X402Deposit<'info> {
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
        space = X402PaymentRecord::LEN,
        seeds = [X402_PAYMENT_SEED, user_account.key().as_ref(), &params.payment_hash],
        bump,
    )]
    pub payment_record: Account<'info, X402PaymentRecord>,

    /// The agent's token vault.
    #[account(
        mut,
        constraint = vault.key() == trading_agent.vault @ PikkyError::MintMismatch,
    )]
    pub vault: Account<'info, TokenAccount>,

    /// The user's token account to pay from.
    #[account(
        mut,
        constraint = user_token_account.mint == trading_agent.quote_mint @ PikkyError::MintMismatch,
        constraint = user_token_account.owner == owner.key() @ PikkyError::Unauthorized,
    )]
    pub user_token_account: Account<'info, TokenAccount>,

    #[account(mut)]
    pub owner: Signer<'info>,

    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
}

#[derive(AnchorSerialize, AnchorDeserialize)]
pub struct X402DepositParams {
    /// The amount to pay for x402 access
    pub amount: u64,
    /// Unique hash identifying this payment (prevents double-spend)
    pub payment_hash: [u8; 32],
    /// Resource URI being paid for (hashed)
    pub resource_hash: [u8; 32],
    /// Expiry timestamp for this payment authorization
    pub expires_at: i64,
}

pub fn handler_x402_deposit(ctx: Context<X402Deposit>, params: X402DepositParams) -> Result<()> {
    require!(params.amount > 0, PikkyError::ZeroDeposit);
    require!(!ctx.accounts.trading_agent.paused, PikkyError::AgentPaused);

    let clock = Clock::get()?;

    // Verify payment hasn't expired
    require!(
        !is_payment_expired(params.expires_at, clock.unix_timestamp),
        PikkyError::X402PaymentExpired
    );

    // Transfer payment tokens from user to vault
    let transfer_ctx = CpiContext::new(
        ctx.accounts.token_program.to_account_info(),
        Transfer {
            from: ctx.accounts.user_token_account.to_account_info(),
            to: ctx.accounts.vault.to_account_info(),
            authority: ctx.accounts.owner.to_account_info(),
        },
    );
    token::transfer(transfer_ctx, params.amount)?;

    // Record the x402 payment
    let payment = &mut ctx.accounts.payment_record;
    payment.bump = ctx.bumps.payment_record;
    payment.user_account = ctx.accounts.user_account.key();
    payment.payment_hash = params.payment_hash;
    payment.amount = params.amount;
    payment.paid_at = clock.unix_timestamp;
    payment.consumed = false;
    payment.consumed_by_position = 0;
    payment.expires_at = params.expires_at;
    payment.resource_hash = params.resource_hash;
    payment._reserved = [0u8; 32];

    // Update user account x402 stats
    let user = &mut ctx.accounts.user_account;
    user.balance = user
        .balance
        .checked_add(params.amount)
        .ok_or(PikkyError::MathOverflow)?;
    user.total_x402_payments = user
        .total_x402_payments
        .checked_add(params.amount)
        .ok_or(PikkyError::MathOverflow)?;
    user.x402_payment_count = user
        .x402_payment_count
        .checked_add(1)
        .ok_or(PikkyError::MathOverflow)?;

    // Update agent totals
    let agent = &mut ctx.accounts.trading_agent;
    agent.total_deposits = agent
        .total_deposits
        .checked_add(params.amount)
        .ok_or(PikkyError::MathOverflow)?;
    agent.last_activity = clock.unix_timestamp;

    msg!(
        "x402 payment recorded: {} tokens from user {}. Payment hash: {:?}",
        params.amount,
        user.owner,
        &params.payment_hash[..8],
    );

    Ok(())
}
