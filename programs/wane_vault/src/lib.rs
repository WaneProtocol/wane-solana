use anchor_lang::prelude::*;
use anchor_lang::system_program;
use wane_registry::program::WaneRegistry;
use wane_registry::{Antibody, RegistryConfig};

declare_id!("5YK7gMzkjUvLaxfNisMdtjRK4UeAiJBCSonB3GgrtTYh");

// Wane vault: a non-custodial session-key smart account.
// Funds live in a program-owned vault PDA, but only the owner can drive it and
// the program can ONLY block, never divert: wane_execute screens every native-SOL
// outflow against the shared antibody registry + the agent's own policy, and
// reverts before any lamport moves. This is the Solana analog of the Base 7702
// WaneDelegate (block-only, owner-driven), with the registry read done via CPI
// account-load instead of an EVM view call.

#[program]
pub mod wane_vault {
    use super::*;

    /// Enroll an agent: create its policy + vault authority. One-time.
    pub fn enroll(ctx: Context<Enroll>, params: PolicyParams) -> Result<()> {
        let p = &mut ctx.accounts.policy;
        p.owner = ctx.accounts.owner.key();
        p.vault = ctx.accounts.vault.key();
        p.enabled = true;
        p.paused = false;
        p.block_kinds = params.block_kinds;
        p.min_corrobs = params.min_corrobs;
        p.per_tx_cap = params.per_tx_cap;
        p.daily_cap = params.daily_cap;
        p.spent_today = 0;
        p.day_start = Clock::get()?.unix_timestamp / 86400;
        p.expires_at = params.expires_at;
        p.bump = ctx.bumps.policy;
        p.vault_bump = ctx.bumps.vault;
        Ok(())
    }

    /// Deposit native SOL into the owner's vault PDA. Funds stay owner-controlled;
    /// the program can only release them through screened wane_execute.
    pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {
        system_program::transfer(
            CpiContext::new(
                ctx.accounts.system_program.to_account_info(),
                system_program::Transfer {
                    from: ctx.accounts.owner.to_account_info(),
                    to: ctx.accounts.vault.to_account_info(),
                },
            ),
            amount,
        )?;
        Ok(())
    }

    /// Screen + send native SOL from the vault to `destination`.
    /// Reverts (before any value moves) if the destination is a flagged,
    /// enforceable antibody, or if the policy caps/pause/expiry reject it.
    pub fn wane_execute(ctx: Context<WaneExecute>, amount: u64) -> Result<()> {
        let policy = &mut ctx.accounts.policy;
        let now = Clock::get()?.unix_timestamp;

        // ---- policy gate (mirrors WanePolicy._evaluate order) ----
        require!(policy.enabled, VaultError::NotEnabled);
        require!(!policy.paused, VaultError::Paused);
        require!(
            policy.expires_at == 0 || now < policy.expires_at,
            VaultError::Expired
        );

        // ---- registry threat screen (the core: reuse is_enforceable) ----
        // `antibody` is constrained by seeds to be THE (Address, destination) PDA in
        // the registry program. This binding is the security property: a client
        // CANNOT omit it or point it at a different (clean) address to bypass the
        // screen. If the PDA carries registry-owned data, the destination is flagged.
        if policy.block_kinds & K_ADDRESS != 0 {
            let ab_ai = ctx.accounts.antibody.to_account_info();
            if ab_ai.owner == &wane_registry::ID && !ab_ai.data_is_empty() {
                let data = ab_ai.try_borrow_data()?;
                let ab = Antibody::try_deserialize(&mut &data[..])?;
                let cfg = &ctx.accounts.registry_config;
                if ab.is_enforceable(now, cfg.enforce_window_secs, cfg.enforce_corrobs)
                    && ab.corroborations >= policy.min_corrobs
                {
                    return err!(VaultError::Blocked);
                }
            }
        }
