use anchor_lang::prelude::*;
use anchor_spl::token::{Mint, Token, TokenAccount};
use anchor_spl::associated_token::AssociatedToken;

use crate::state::{TradingAgent, UserAccount, MbtiProfile, MbtiType};
use crate::error::PikkyError;
use crate::utils::{TRADING_AGENT_SEED, USER_ACCOUNT_SEED, VAULT_SEED};

/// Initialize a new PIKKY trading agent instance.
#[derive(Accounts)]
pub struct InitializeAgent<'info> {
    #[account(
        init,
        payer = authority,
        space = TradingAgent::LEN,
        seeds = [TRADING_AGENT_SEED, authority.key().as_ref()],
        bump,
    )]
    pub trading_agent: Account<'info, TradingAgent>,

    /// The SPL token mint used as the quote currency (e.g. USDC).
    pub quote_mint: Account<'info, Mint>,

    /// The agent's token vault, an ATA owned by the trading_agent PDA.
    #[account(
        init,
        payer = authority,
        associated_token::mint = quote_mint,
        associated_token::authority = trading_agent,
    )]
    pub vault: Account<'info, TokenAccount>,

    /// The wallet that will control this agent.
    #[account(mut)]
    pub authority: Signer<'info>,

    /// Where protocol fees are sent.
    /// CHECK: Validated as a system account; fee_receiver is just a destination pubkey.
    pub fee_receiver: UncheckedAccount<'info>,

    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
    pub associated_token_program: Program<'info, AssociatedToken>,
    pub rent: Sysvar<'info, Rent>,
}

/// Parameters for agent initialization.
#[derive(AnchorSerialize, AnchorDeserialize)]
pub struct InitializeAgentParams {
    /// Protocol fee in basis points (max 500 = 5%)
    pub fee_bps: u16,
}

pub fn handler_initialize_agent(
    ctx: Context<InitializeAgent>,
    params: InitializeAgentParams,
) -> Result<()> {
    require!(params.fee_bps <= 500, PikkyError::InvalidFeeBps);

    let clock = Clock::get()?;
    let agent = &mut ctx.accounts.trading_agent;

    agent.bump = ctx.bumps.trading_agent;
    agent.authority = ctx.accounts.authority.key();
    agent.quote_mint = ctx.accounts.quote_mint.key();
    agent.vault = ctx.accounts.vault.key();
    agent.fee_receiver = ctx.accounts.fee_receiver.key();
    agent.fee_bps = params.fee_bps;
    agent.paused = false;
    agent.total_deposits = 0;
    agent.total_withdrawals = 0;
    agent.total_trades = 0;
    agent.total_fees_collected = 0;
    agent.created_at = clock.unix_timestamp;
    agent.last_activity = clock.unix_timestamp;
    agent._reserved = [0u8; 128];

    msg!(
        "PIKKY Trading Agent initialized. Authority: {}, Quote mint: {}, Fee: {} bps",
        agent.authority,
        agent.quote_mint,
        agent.fee_bps,
    );

    Ok(())
}

/// Initialize a user account under a trading agent.
#[derive(Accounts)]