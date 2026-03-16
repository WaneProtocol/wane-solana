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

        emit!(AntibodyMinted { id: a.id, kind, subject, publisher: a.publisher });
        Ok(())
    }

    /// Independently corroborate an existing antibody. The Corroboration marker
    /// PDA enforces one-vote-per-account: init fails on a second attempt.
    pub fn corroborate(ctx: Context<Corroborate>) -> Result<()> {
        let a = &mut ctx.accounts.antibody;
        require!(a.status == Status::Active as u8, WaneError::NotActive);
        require!(
            ctx.accounts.corroborator.key() != a.publisher,
            WaneError::SelfCorroborate
        );
        a.corroborations = a.corroborations.checked_add(1).unwrap();
        ctx.accounts.corroboration.bump = ctx.bumps.corroboration;
        Ok(())
    }

    /// Seed protocol-owned genesis antibodies (stake = 0, trusted, enforce now).
    pub fn seed_genesis(ctx: Context<SeedGenesis>, kind: u8, subject: [u8; 32]) -> Result<()> {
        let config = &mut ctx.accounts.config;
        require!(config.genesis_open, WaneError::GenesisClosed);
        require!(kind <= 3, WaneError::BadKind);
        config.antibody_count = config.antibody_count.checked_add(1).unwrap();

        let now = Clock::get()?.unix_timestamp;
        let key = config.key();
        let a = &mut ctx.accounts.antibody;
        a.id = config.antibody_count;
        a.kind = kind;
        a.status = Status::Active as u8;
        a.publisher = key; // protocol-owned
        a.stake = 0; // genesis: trusted, enforces immediately
        a.minted_ts = now;
        a.corroborations = 0;
        a.subject = subject;
        a.evidence = [0u8; 32];
        a.challenger = Pubkey::default();
        a.challenge_bond = 0;
        a.bump = ctx.bumps.antibody;
        Ok(())
    }

    /// Close the genesis window (governor only). After this, no more stake=0 seeds.
    pub fn close_genesis(ctx: Context<GovernorOnly>) -> Result<()> {
        ctx.accounts.config.genesis_open = false;
        Ok(())
    }

    /// Challenge an active antibody as a false positive. Posts a bond, moves the
    /// antibody to Challenged (still fail-closed) until the governor resolves.
    pub fn challenge(ctx: Context<Challenge>) -> Result<()> {
        let config = &mut ctx.accounts.config;
        let bond = config.challenge_stake;
        token::transfer(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.challenger_ata.to_account_info(),
                    to: ctx.accounts.stake_vault.to_account_info(),
                    authority: ctx.accounts.challenger.to_account_info(),
                },
            ),
            bond,
        )?;
        config.reserved = config.reserved.checked_add(bond).unwrap();

        let a = &mut ctx.accounts.antibody;
        require!(a.status == Status::Active as u8, WaneError::NotActive);
        a.status = Status::Challenged as u8;
        a.challenger = ctx.accounts.challenger.key();
        a.challenge_bond = bond;
        Ok(())
    }

    /// Governor resolves a challenge.
    /// false_positive=true: antibody Revoked, challenger gets bond + the publisher
    /// stake (slash). false_positive=false: antibody back to Active, publisher
    /// keeps stake and earns the challenge bond (challenger slashed).
    pub fn resolve(ctx: Context<Resolve>, false_positive: bool) -> Result<()> {
        let config = &mut ctx.accounts.config;
        let a = &mut ctx.accounts.antibody;
        require!(a.status == Status::Challenged as u8, WaneError::NotChallenged);

        let bond = a.challenge_bond;
        let stake = a.stake;
        // CEI: clear state first
        a.challenge_bond = 0;

        if false_positive {
            // antibody was wrong: revoke, pay challenger bond + slashed stake
            a.status = Status::Revoked as u8;
            a.stake = 0;
            let payout = bond.checked_add(stake).unwrap();
            config.reserved = config.reserved.checked_sub(payout).unwrap();
            pay_from_vault(
                &ctx.accounts.token_program,
                &ctx.accounts.stake_vault,
                &ctx.accounts.challenger_ata,
                ctx.accounts.config_for_signer.to_account_info(),
                config.bump,
                payout,
            )?;
        } else {
            // antibody was right: restore, challenger bond credited to publisher earned
            a.status = Status::Active as u8;
            // bond reclassified from reserved-as-bond to reserved-as-earned: net unchanged
            let earned = &mut ctx.accounts.publisher_earned;
            earned.amount = earned.amount.checked_add(bond).unwrap();
            earned.bump = ctx.bumps.publisher_earned;
        }
        a.challenger = Pubkey::default();
        Ok(())
    }

    /// Claim accumulated rewards (earned bonds) to your token account.
    pub fn claim_rewards(ctx: Context<ClaimRewards>) -> Result<()> {
        let config = &mut ctx.accounts.config;
        let earned = &mut ctx.accounts.earned;
        let amt = earned.amount;
        require!(amt > 0, WaneError::NothingToClaim);
        earned.amount = 0;
        config.reserved = config.reserved.checked_sub(amt).unwrap();
        pay_from_vault(
            &ctx.accounts.token_program,
            &ctx.accounts.stake_vault,
            &ctx.accounts.claimer_ata,
            ctx.accounts.config_for_signer.to_account_info(),
            config.bump,
            amt,
        )?;
        Ok(())
    }

    /// Governor: update the $WANE mint, stake vault, treasury, and economic
    /// params. The mint/vault are re-read from the passed accounts; the scalar
    /// params are taken from `p`. governor / counters / reserved are untouched.
    pub fn update_config(ctx: Context<UpdateConfig>, p: InitParams) -> Result<()> {
        let c = &mut ctx.accounts.config;
        c.treasury = p.treasury;
        c.wane_mint = ctx.accounts.wane_mint.key();
        c.stake_vault = ctx.accounts.stake_vault.key();
        c.mint_stake = p.mint_stake;
        c.challenge_stake = p.challenge_stake;
        c.maturity_secs = p.maturity_secs;
        c.enforce_window_secs = p.enforce_window_secs;
        c.enforce_corrobs = p.enforce_corrobs;
        Ok(())
    }

    /// Governor: pause / unpause the registry (blocks new mints).
    pub fn set_registry_paused(ctx: Context<GovernorOnly>, paused: bool) -> Result<()> {
        ctx.accounts.config.paused = paused;
        Ok(())
    }

    /// Governor: nominate a successor. Takes effect only after the nominee calls
    /// accept_governor (two-step transfer, avoids handing control to a typo).
    pub fn nominate_governor(ctx: Context<GovernorOnly>, new_governor: Pubkey) -> Result<()> {
        ctx.accounts.config.pending_governor = new_governor;
        Ok(())
    }

    /// Pending governor: accept the nomination and become governor.
    pub fn accept_governor(ctx: Context<AcceptGovernor>) -> Result<()> {
        let c = &mut ctx.accounts.config;
        require!(
            c.pending_governor != Pubkey::default()
                && ctx.accounts.new_governor.key() == c.pending_governor,
            WaneError::NotPending
        );
        c.governor = c.pending_governor;
        c.pending_governor = Pubkey::default();
        Ok(())
    }
}

/// Helper: pay $WANE out of the stake vault, signed by the RegistryConfig PDA.
fn pay_from_vault<'info>(
    token_program: &Program<'info, Token>,
    stake_vault: &Account<'info, TokenAccount>,
    to: &Account<'info, TokenAccount>,
    config_ai: AccountInfo<'info>,
    config_bump: u8,
    amount: u64,
) -> Result<()> {
    let seeds: &[&[u8]] = &[b"config", &[config_bump]];
    token::transfer(
        CpiContext::new_with_signer(
            token_program.to_account_info(),
            Transfer {
                from: stake_vault.to_account_info(),
                to: to.to_account_info(),
                authority: config_ai,
            },
            &[seeds],
        ),
        amount,
    )?;
    Ok(())
}

// ----------------------------------------------------------------------------
// Shared enforceability logic (mirrors WaneRegistry _enforceable in Solidity).
// The vault program ports the identical rule when it screens a send.
// ----------------------------------------------------------------------------
impl Antibody {
    pub fn is_enforceable(&self, now: i64, enforce_window_secs: i64, enforce_corrobs: u32) -> bool {
        if self.status == Status::Revoked as u8 {
            return false;
        }
        if self.status == Status::Challenged as u8 {
            return true; // fail-closed during dispute
        }
        if self.stake == 0 {
            return true; // genesis / protocol-owned, trusted
        }
        if self.corroborations >= enforce_corrobs {
            return true;
        }
        now >= self.minted_ts + enforce_window_secs
    }
}

// ---------------------------- state ----------------------------

#[account]
pub struct RegistryConfig {
    pub governor: Pubkey,
    pub pending_governor: Pubkey,
    pub treasury: Pubkey,
    pub wane_mint: Pubkey,
    pub stake_vault: Pubkey,
    pub antibody_count: u64,
    pub reserved: u64,
    pub mint_stake: u64,
    pub challenge_stake: u64,
    pub maturity_secs: i64,
    pub enforce_window_secs: i64,
    pub enforce_corrobs: u32,
    pub genesis_open: bool,
    pub paused: bool,
    pub bump: u8,
}
impl RegistryConfig {
    // 5 pubkeys + (count,reserved,mint_stake,challenge_stake)=4*u64 + (maturity,window)=2*i64 + corrobs u32 + 2 bool + bump
    pub const LEN: usize = 32 * 5 + 8 * 4 + 8 * 2 + 4 + 1 + 1 + 1;
}

#[account]
pub struct Antibody {
    pub id: u64,
    pub kind: u8,
    pub status: u8,
    pub publisher: Pubkey,
    pub stake: u64,
    pub minted_ts: i64,
    pub corroborations: u32,
    pub subject: [u8; 32],
    pub evidence: [u8; 32],
    pub challenger: Pubkey,
    pub challenge_bond: u64,
    pub bump: u8,
}
impl Antibody {
    pub const LEN: usize = 8 + 1 + 1 + 32 + 8 + 8 + 4 + 32 + 32 + 32 + 8 + 1;
}

#[account]
pub struct Corroboration {
    pub bump: u8,
}

#[account]
pub struct Earned {
    pub amount: u64,
    pub bump: u8,
}
impl Earned {
    pub const LEN: usize = 8 + 1;
}

#[repr(u8)]
pub enum Status {
    None = 0,
    Active = 1,
    Challenged = 2,
    Revoked = 3,
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone)]
pub struct InitParams {
    pub treasury: Pubkey,
    pub mint_stake: u64,
    pub challenge_stake: u64,
    pub maturity_secs: i64,
    pub enforce_window_secs: i64,
    pub enforce_corrobs: u32,
}

#[event]
pub struct AntibodyMinted {
    pub id: u64,
    pub kind: u8,
    pub subject: [u8; 32],
    pub publisher: Pubkey,
}

// ---------------------------- accounts ----------------------------

#[derive(Accounts)]
pub struct InitConfig<'info> {
    #[account(mut)]
    pub governor: Signer<'info>,
    #[account(
        init,
        payer = governor,
        space = 8 + RegistryConfig::LEN,
        seeds = [b"config"],
        bump
    )]
    pub config: Account<'info, RegistryConfig>,
    /// CHECK: $WANE mint, recorded only
    pub wane_mint: UncheckedAccount<'info>,
    /// CHECK: the PDA token account holding staked $WANE, recorded only
    pub stake_vault: UncheckedAccount<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(kind: u8, subject: [u8; 32])]
pub struct MintAntibody<'info> {
    #[account(mut)]
    pub publisher: Signer<'info>,
    #[account(mut, seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, RegistryConfig>,
    #[account(
        init,
        payer = publisher,
        space = 8 + Antibody::LEN,
        seeds = [b"antibody".as_ref(), std::slice::from_ref(&kind), subject.as_ref()],
        bump
    )]
    pub antibody: Account<'info, Antibody>,
    #[account(mut)]
    pub publisher_ata: Account<'info, TokenAccount>,
    #[account(mut, address = config.stake_vault)]
    pub stake_vault: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Corroborate<'info> {
    #[account(mut)]
    pub corroborator: Signer<'info>,
    #[account(mut)]
    pub antibody: Account<'info, Antibody>,
    #[account(
        init,
        payer = corroborator,
        space = 8 + 1,
        seeds = [b"corrob", antibody.key().as_ref(), corroborator.key().as_ref()],
        bump
    )]
    pub corroboration: Account<'info, Corroboration>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(kind: u8, subject: [u8; 32])]
pub struct SeedGenesis<'info> {
    #[account(mut, address = config.governor)]
    pub governor: Signer<'info>,
    #[account(mut, seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, RegistryConfig>,
    #[account(
        init,
        payer = governor,
        space = 8 + Antibody::LEN,
        seeds = [b"antibody".as_ref(), std::slice::from_ref(&kind), subject.as_ref()],
        bump
    )]
    pub antibody: Account<'info, Antibody>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct GovernorOnly<'info> {
    #[account(address = config.governor)]
    pub governor: Signer<'info>,
    #[account(mut, seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, RegistryConfig>,
}

#[derive(Accounts)]
pub struct UpdateConfig<'info> {
    #[account(address = config.governor)]
    pub governor: Signer<'info>,
    #[account(mut, seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, RegistryConfig>,
    /// CHECK: new $WANE mint, recorded only
    pub wane_mint: UncheckedAccount<'info>,
    /// CHECK: the PDA token account holding staked $WANE, recorded only
    pub stake_vault: UncheckedAccount<'info>,
}

#[derive(Accounts)]
pub struct AcceptGovernor<'info> {
    pub new_governor: Signer<'info>,
    #[account(mut, seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, RegistryConfig>,
}

#[derive(Accounts)]
pub struct Challenge<'info> {
    #[account(mut)]
    pub challenger: Signer<'info>,
    #[account(mut, seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, RegistryConfig>,
    #[account(mut)]
    pub antibody: Account<'info, Antibody>,
    #[account(mut)]
    pub challenger_ata: Account<'info, TokenAccount>,
    #[account(mut, address = config.stake_vault)]
    pub stake_vault: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct Resolve<'info> {
    #[account(mut, address = config.governor)]
    pub governor: Signer<'info>,
    #[account(mut, seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, RegistryConfig>,
    /// CHECK: same as config, passed as the invoke_signed authority for payouts
    #[account(address = config.key())]
    pub config_for_signer: UncheckedAccount<'info>,
    #[account(mut)]
    pub antibody: Account<'info, Antibody>,
    #[account(mut, address = config.stake_vault)]
    pub stake_vault: Account<'info, TokenAccount>,
    #[account(mut)]
    pub challenger_ata: Account<'info, TokenAccount>,
    #[account(
        init_if_needed,
        payer = governor,
        space = 8 + Earned::LEN,
        seeds = [b"earned", antibody.publisher.as_ref()],
        bump
    )]
    pub publisher_earned: Account<'info, Earned>,
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct ClaimRewards<'info> {
    #[account(mut)]
    pub claimer: Signer<'info>,
    #[account(mut, seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, RegistryConfig>,
    /// CHECK: same as config, invoke_signed authority
    #[account(address = config.key())]
    pub config_for_signer: UncheckedAccount<'info>,
    #[account(
        mut,
        seeds = [b"earned", claimer.key().as_ref()],
        bump = earned.bump
    )]
    pub earned: Account<'info, Earned>,
    #[account(mut, address = config.stake_vault)]
    pub stake_vault: Account<'info, TokenAccount>,
    #[account(mut)]
    pub claimer_ata: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
}

// ---------------------------- errors ----------------------------

#[error_code]
pub enum WaneError {
    #[msg("registry is paused")]
    Paused,
    #[msg("threat kind must be 0..3")]
    BadKind,
    #[msg("antibody is not active")]
    NotActive,
    #[msg("cannot corroborate your own antibody")]
    SelfCorroborate,
    #[msg("genesis window is closed")]
    GenesisClosed,
    #[msg("antibody is not challenged")]
    NotChallenged,
    #[msg("nothing to claim")]
    NothingToClaim,
    #[msg("no pending governor / caller is not the nominee")]
    NotPending,
}
