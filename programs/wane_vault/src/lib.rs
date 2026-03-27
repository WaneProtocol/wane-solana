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

        // ---- caps ----
        if policy.per_tx_cap != 0 {
            require!(amount <= policy.per_tx_cap, VaultError::OverPerTx);
        }
        if policy.daily_cap != 0 {
            let today = now / 86400;
            if today != policy.day_start {
                policy.day_start = today;
                policy.spent_today = 0;
            }
            let used = policy.spent_today.checked_add(amount).unwrap();
            require!(used <= policy.daily_cap, VaultError::OverDaily);
            policy.spent_today = used;
        }

        // ---- passed: move SOL from vault PDA via signed transfer ----
        let owner_key = policy.owner;
        let seeds: &[&[u8]] = &[b"vault", owner_key.as_ref(), &[policy.vault_bump]];
        system_program::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.system_program.to_account_info(),
                system_program::Transfer {
                    from: ctx.accounts.vault.to_account_info(),
                    to: ctx.accounts.destination.to_account_info(),
                },
                &[seeds],
            ),
            amount,
        )?;
        Ok(())
    }

    /// Owner kill switch.
    pub fn set_paused(ctx: Context<OwnerOnly>, paused: bool) -> Result<()> {
        ctx.accounts.policy.paused = paused;
        Ok(())
    }

    /// Owner: adjust policy params (caps, expiry, blocked kinds, min corrobs)
    /// after enrollment. Does not touch spent_today / day_start accounting.
    pub fn update_policy(ctx: Context<OwnerOnly>, params: PolicyParams) -> Result<()> {
        let p = &mut ctx.accounts.policy;
        p.block_kinds = params.block_kinds;
        p.min_corrobs = params.min_corrobs;
        p.per_tx_cap = params.per_tx_cap;
        p.daily_cap = params.daily_cap;
        p.expires_at = params.expires_at;
        Ok(())
    }

    /// Owner: withdraw native SOL from the vault back to themselves. Unscreened
    /// (returning your own funds is never a threat) so funds can never be trapped.
    pub fn withdraw(ctx: Context<Withdraw>, amount: u64) -> Result<()> {
        let owner_key = ctx.accounts.policy.owner;
        let bump = ctx.accounts.policy.vault_bump;
        let seeds: &[&[u8]] = &[b"vault", owner_key.as_ref(), &[bump]];
        system_program::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.system_program.to_account_info(),
                system_program::Transfer {
                    from: ctx.accounts.vault.to_account_info(),
                    to: ctx.accounts.owner.to_account_info(),
                },
                &[seeds],
            ),
            amount,
        )?;
        Ok(())
    }
}

/// Antibody enum kind for an address threat (matches registry Status/kind 0 and
/// the SDK ThreatKind.Address). Distinct from the K_ADDRESS policy bitmask below.
pub const KIND_ADDRESS: u8 = 0;

pub const K_ADDRESS: u8 = 1;
pub const K_CALL: u8 = 2;
pub const K_BYTECODE: u8 = 4;
pub const K_SEMANTIC: u8 = 8;

#[account]
pub struct AgentPolicy {
    pub owner: Pubkey,
    pub vault: Pubkey,
    pub enabled: bool,
    pub paused: bool,
    pub block_kinds: u8,
    pub min_corrobs: u32,
    pub per_tx_cap: u64,
    pub daily_cap: u64,
    pub spent_today: u64,
    pub day_start: i64,
    pub expires_at: i64,
    pub bump: u8,
    pub vault_bump: u8,
}
impl AgentPolicy {
    pub const LEN: usize = 32 + 32 + 1 + 1 + 1 + 4 + 8 + 8 + 8 + 8 + 8 + 1 + 1;
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone)]
pub struct PolicyParams {
    pub block_kinds: u8,
    pub min_corrobs: u32,
    pub per_tx_cap: u64,
    pub daily_cap: u64,
    pub expires_at: i64,
}

#[derive(Accounts)]
pub struct Enroll<'info> {
    #[account(mut)]
    pub owner: Signer<'info>,
    #[account(
        init,
        payer = owner,
        space = 8 + AgentPolicy::LEN,
        seeds = [b"policy", owner.key().as_ref()],
        bump
    )]
    pub policy: Account<'info, AgentPolicy>,
    /// CHECK: vault PDA, holds native SOL, owner-scoped. No data.
    #[account(
        mut,
        seeds = [b"vault", owner.key().as_ref()],
        bump
    )]
    pub vault: UncheckedAccount<'info>,
    pub system_program: Program<'info, System>,
}
