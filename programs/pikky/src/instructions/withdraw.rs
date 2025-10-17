use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

use crate::state::{TradingAgent, UserAccount};
use crate::error::PikkyError;
use crate::utils::{TRADING_AGENT_SEED, USER_ACCOUNT_SEED};

/// Withdraw funds from a user's trading account back to their wallet.
#[derive(Accounts)]
pub struct Withdraw<'info> {
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

    /// The user's token account to receive withdrawn funds.
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
pub struct WithdrawParams {
    /// Amount to withdraw in quote token base units. Pass u64::MAX for full balance.
    pub amount: u64,
}

pub fn handler_withdraw(ctx: Context<Withdraw>, params: WithdrawParams) -> Result<()> {
    let clock = Clock::get()?;
    let user = &ctx.accounts.user_account;

    // Determine actual withdrawal amount
    let withdraw_amount = if params.amount == u64::MAX {
        user.balance
    } else {
        params.amount
    };

    require!(withdraw_amount > 0, PikkyError::ZeroDeposit);
    require!(
        user.balance >= withdraw_amount,
        PikkyError::InsufficientFunds
    );

    // Check that vault has sufficient tokens
    let vault_balance = ctx.accounts.vault.amount;
    require!(
        vault_balance >= withdraw_amount,
        PikkyError::InsufficientFunds
    );

    // Transfer tokens from vault to user using PDA signer
    let agent = &ctx.accounts.trading_agent;
    let authority_key = agent.authority;
    let agent_seeds = &[
        TRADING_AGENT_SEED,
        authority_key.as_ref(),
        &[agent.bump],
    ];
    let signer_seeds = &[&agent_seeds[..]];

    let transfer_ctx = CpiContext::new_with_signer(
        ctx.accounts.token_program.to_account_info(),
        Transfer {
            from: ctx.accounts.vault.to_account_info(),
            to: ctx.accounts.user_token_account.to_account_info(),
            authority: ctx.accounts.trading_agent.to_account_info(),
        },
        signer_seeds,
    );
    token::transfer(transfer_ctx, withdraw_amount)?;

    // Update user balance
    let user = &mut ctx.accounts.user_account;
    user.balance = user
        .balance
        .checked_sub(withdraw_amount)
        .ok_or(PikkyError::MathOverflow)?;

    // Update agent totals
    let agent = &mut ctx.accounts.trading_agent;
    agent.total_withdrawals = agent
        .total_withdrawals
        .checked_add(withdraw_amount)
        .ok_or(PikkyError::MathOverflow)?;
    agent.last_activity = clock.unix_timestamp;

    msg!(
        "Withdrew {} tokens for user {}. Remaining balance: {}",
        withdraw_amount,
        user.owner,
        user.balance,
    );

    Ok(())
}

/// Emergency withdrawal by the agent authority (returns all user funds).
#[derive(Accounts)]
pub struct EmergencyWithdraw<'info> {
    #[account(
        mut,
        seeds = [TRADING_AGENT_SEED, trading_agent.authority.as_ref()],
        bump = trading_agent.bump,
        has_one = authority @ PikkyError::Unauthorized,
    )]
    pub trading_agent: Account<'info, TradingAgent>,

    #[account(
        mut,
        has_one = trading_agent,
    )]
    pub user_account: Account<'info, UserAccount>,

    /// The agent's token vault.
    #[account(
        mut,
        constraint = vault.key() == trading_agent.vault @ PikkyError::MintMismatch,
    )]
    pub vault: Account<'info, TokenAccount>,

    /// The user's token account to receive funds.
    #[account(
        mut,
        constraint = user_token_account.mint == trading_agent.quote_mint @ PikkyError::MintMismatch,
        constraint = user_token_account.owner == user_account.owner @ PikkyError::Unauthorized,
    )]
    pub user_token_account: Account<'info, TokenAccount>,

    pub authority: Signer<'info>,

    pub token_program: Program<'info, Token>,
}

pub fn handler_emergency_withdraw(ctx: Context<EmergencyWithdraw>) -> Result<()> {
    let clock = Clock::get()?;
    let user = &ctx.accounts.user_account;
    let withdraw_amount = user.balance;

    if withdraw_amount == 0 {
        msg!("No balance to withdraw for user {}", user.owner);
        return Ok(());
    }

    // Check vault
    let vault_balance = ctx.accounts.vault.amount;
    let actual_withdraw = withdraw_amount.min(vault_balance);

    // Transfer using PDA signer
    let agent = &ctx.accounts.trading_agent;
    let authority_key = agent.authority;
    let agent_seeds = &[
        TRADING_AGENT_SEED,
        authority_key.as_ref(),
        &[agent.bump],
    ];
    let signer_seeds = &[&agent_seeds[..]];

    let transfer_ctx = CpiContext::new_with_signer(
        ctx.accounts.token_program.to_account_info(),
        Transfer {
            from: ctx.accounts.vault.to_account_info(),
            to: ctx.accounts.user_token_account.to_account_info(),
            authority: ctx.accounts.trading_agent.to_account_info(),
        },
        signer_seeds,
    );
    token::transfer(transfer_ctx, actual_withdraw)?;

    // Update user
    let user = &mut ctx.accounts.user_account;
    user.balance = user.balance.saturating_sub(actual_withdraw);

    // Update agent
    let agent = &mut ctx.accounts.trading_agent;
    agent.total_withdrawals = agent
        .total_withdrawals
        .checked_add(actual_withdraw)
        .ok_or(PikkyError::MathOverflow)?;
    agent.last_activity = clock.unix_timestamp;

    msg!(
        "Emergency withdrawal: {} tokens returned to user {}",
        actual_withdraw,
        user.owner,
    );

    Ok(())
}
