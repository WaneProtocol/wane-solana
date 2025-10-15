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
