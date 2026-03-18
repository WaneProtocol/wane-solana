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
