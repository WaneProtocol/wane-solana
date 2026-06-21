use anchor_lang::prelude::*;
use anchor_lang::system_program;
use wane_registry::program::WaneRegistry;
use wane_registry::{Antibody, RegistryConfig};

declare_id!("5YK7gMzkjUvLaxfNisMdtjRK4UeAiJBCSonB3GgrtTYh");

// Wane vault: a non-custodial smart account with a true session key.
// Funds live in a program-owned vault PDA. The OWNER is a master key; the owner
// can also grant an AGENT a scoped SESSION KEY (a separate signer, time-boxed)
// that can ONLY drive screened wane_execute within the policy caps, and can
// NEVER withdraw or change the policy. wane_execute screens every native-SOL
// outflow against the shared antibody registry + the agent's policy and reverts
// before any lamport moves. The registry read is a CPI account-load (no view).

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
        p.session_key = Pubkey::default();
        p.session_expiry = 0;
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

    /// Owner: grant or replace the scoped agent session key (key = default to
    /// clear). The session key can drive screened sends within the policy caps
    /// until `expiry` (unix secs; 0 = no session). It can never withdraw.
    pub fn set_session(ctx: Context<OwnerOnly>, key: Pubkey, expiry: i64) -> Result<()> {
        let p = &mut ctx.accounts.policy;
        p.session_key = key;
        p.session_expiry = expiry;
        Ok(())
    }

    /// Owner: revoke the session key immediately.
    pub fn revoke_session(ctx: Context<OwnerOnly>) -> Result<()> {
        let p = &mut ctx.accounts.policy;
        p.session_key = Pubkey::default();
        p.session_expiry = 0;
        Ok(())
    }

    /// Screen + send native SOL from the vault to `destination`. Driven by the
    /// owner OR a live session key. Reverts (before any value moves) if the
    /// destination is a flagged, enforceable antibody, or if the policy
    /// caps/pause/expiry reject it.
    pub fn wane_execute(ctx: Context<WaneExecute>, amount: u64) -> Result<()> {
        let policy = &mut ctx.accounts.policy;
        let now = Clock::get()?.unix_timestamp;

        // ---- driver auth: owner (master) or the live session key ----
        let driver = ctx.accounts.driver.key();
        if driver != policy.owner {
            require!(
                policy.session_key != Pubkey::default() && driver == policy.session_key,
                VaultError::Unauthorized
            );
            require!(now < policy.session_expiry, VaultError::SessionExpired);
        }

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

        // ---- caps (apply to whoever drives, so they bound the session key too) ----
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
    /// A session key can NEVER reach this (owner-only).
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
    pub session_key: Pubkey,
    pub session_expiry: i64,
    pub bump: u8,
    pub vault_bump: u8,
}
impl AgentPolicy {
    pub const LEN: usize = 32 + 32 + 1 + 1 + 1 + 4 + 8 + 8 + 8 + 8 + 8 + 32 + 8 + 1 + 1;
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

#[derive(Accounts)]
pub struct Deposit<'info> {
    #[account(mut)]
    pub owner: Signer<'info>,
    /// CHECK: vault PDA
    #[account(mut, seeds = [b"vault", owner.key().as_ref()], bump)]
    pub vault: UncheckedAccount<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct WaneExecute<'info> {
    /// The authorizer: either the policy owner (master) or the live session key.
    pub driver: Signer<'info>,
    /// CHECK: the vault owner pubkey, used only for PDA derivation. Bound to the
    /// policy via has_one; never a signer here.
    pub owner: UncheckedAccount<'info>,
    #[account(
        mut,
        seeds = [b"policy", owner.key().as_ref()],
        bump = policy.bump,
        has_one = owner
    )]
    pub policy: Account<'info, AgentPolicy>,
    /// CHECK: vault PDA, validated by seeds
    #[account(mut, seeds = [b"vault", owner.key().as_ref()], bump = policy.vault_bump)]
    pub vault: UncheckedAccount<'info>,
    /// CHECK: arbitrary recipient
    #[account(mut)]
    pub destination: UncheckedAccount<'info>,
    /// The registry config (for enforce window/corrobs). Read-only.
    pub registry_config: Account<'info, RegistryConfig>,
    /// CHECK: bound by seeds to the (Address, destination) antibody PDA in the
    /// registry program. May be uninitialized (clean) but its ADDRESS is forced,
    /// so it cannot be omitted or swapped to dodge the screen. Data is validated
    /// in the handler before use.
    #[account(
        seeds = [b"antibody".as_ref(), std::slice::from_ref(&KIND_ADDRESS), destination.key().as_ref()],
        bump,
        seeds::program = wane_registry::ID
    )]
    pub antibody: UncheckedAccount<'info>,
    pub registry_program: Program<'info, WaneRegistry>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Withdraw<'info> {
    #[account(mut, address = policy.owner)]
    pub owner: Signer<'info>,
    #[account(mut, seeds = [b"policy", owner.key().as_ref()], bump = policy.bump, has_one = owner)]
    pub policy: Account<'info, AgentPolicy>,
    /// CHECK: vault PDA, validated by seeds
    #[account(mut, seeds = [b"vault", owner.key().as_ref()], bump = policy.vault_bump)]
    pub vault: UncheckedAccount<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct OwnerOnly<'info> {
    #[account(address = policy.owner)]
    pub owner: Signer<'info>,
    #[account(mut, seeds = [b"policy", owner.key().as_ref()], bump = policy.bump)]
    pub policy: Account<'info, AgentPolicy>,
}

#[error_code]
pub enum VaultError {
    #[msg("policy not enabled")]
    NotEnabled,
    #[msg("vault is paused (kill switch)")]
    Paused,
    #[msg("policy expired")]
    Expired,
    #[msg("destination is a flagged threat (antibody)")]
    Blocked,
    #[msg("over per-transaction cap")]
    OverPerTx,
    #[msg("over daily cap")]
    OverDaily,
    #[msg("caller is neither the owner nor the session key")]
    Unauthorized,
    #[msg("session key expired")]
    SessionExpired,
}
