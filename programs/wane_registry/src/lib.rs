use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

declare_id!("5Arj4zbFs5GigEGUSUb9hKNMYaPLqv1XgJXUcnGJ1wJH");

// Wane antibody registry, Solana port of WaneRegistry.sol.
// Shared on-chain immune memory: one antibody = one PDA, keyed by (kind, subject).
// Reading is a client-side getAccountInfo, so reading is immunity with no view call.

#[program]
pub mod wane_registry {
    use super::*;

    /// One-time setup of the global config + the staked-$WANE vault authority.
    pub fn init_config(ctx: Context<InitConfig>, p: InitParams) -> Result<()> {
        let c = &mut ctx.accounts.config;
        c.governor = ctx.accounts.governor.key();
        c.pending_governor = Pubkey::default();
        c.treasury = p.treasury;
        c.wane_mint = ctx.accounts.wane_mint.key();
        c.stake_vault = ctx.accounts.stake_vault.key();
        c.antibody_count = 0;
        c.reserved = 0;
        c.mint_stake = p.mint_stake;
        c.challenge_stake = p.challenge_stake;
        c.maturity_secs = p.maturity_secs;
        c.enforce_window_secs = p.enforce_window_secs;
        c.enforce_corrobs = p.enforce_corrobs;
        c.genesis_open = true;
        c.paused = false;
        c.bump = ctx.bumps.config;
        Ok(())
    }

    /// Publish a new antibody against (kind, subject). Stakes $WANE.
    /// The Antibody PDA address IS the dedup key: init fails if it already exists.
    pub fn mint_antibody(
        ctx: Context<MintAntibody>,
        kind: u8,
        subject: [u8; 32],
        evidence: [u8; 32],
    ) -> Result<()> {
        let config = &mut ctx.accounts.config;
        require!(!config.paused, WaneError::Paused);
        require!(kind <= 3, WaneError::BadKind);

        let stake = config.mint_stake;
        // pull stake into the vault (CEI: take funds, then write state)
        token::transfer(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.publisher_ata.to_account_info(),
                    to: ctx.accounts.stake_vault.to_account_info(),
                    authority: ctx.accounts.publisher.to_account_info(),
                },
            ),
            stake,
        )?;

        config.antibody_count = config.antibody_count.checked_add(1).unwrap();
        config.reserved = config.reserved.checked_add(stake).unwrap();

        let now = Clock::get()?.unix_timestamp;
        let a = &mut ctx.accounts.antibody;
        a.id = config.antibody_count;
        a.kind = kind;
        a.status = Status::Active as u8;
        a.publisher = ctx.accounts.publisher.key();
        a.stake = stake;
        a.minted_ts = now;
        a.corroborations = 0;
        a.subject = subject;
        a.evidence = evidence;
        a.challenger = Pubkey::default();
        a.challenge_bond = 0;
        a.bump = ctx.bumps.antibody;
