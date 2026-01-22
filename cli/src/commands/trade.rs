use anyhow::{Context, Result, bail};
use solana_client::rpc_client::RpcClient;
use solana_sdk::{
    commitment_config::CommitmentConfig,
    instruction::{AccountMeta, Instruction},
    pubkey::Pubkey,
    signature::{Keypair, Signer},
    transaction::Transaction,
    system_program,
};
use anchor_lang::{AnchorSerialize, InstructionData, Discriminator};
use std::str::FromStr;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::display;

/// Seeds constants (must match on-chain program).
const TRADING_AGENT_SEED: &[u8] = b"trading_agent";
const USER_ACCOUNT_SEED: &[u8] = b"user_account";
const POSITION_SEED: &[u8] = b"position";
const X402_PAYMENT_SEED: &[u8] = b"x402_payment";

/// Derive the trading agent PDA.
pub fn derive_agent_pda(program_id: &Pubkey, authority: &Pubkey) -> (Pubkey, u8) {
    Pubkey::find_program_address(
        &[TRADING_AGENT_SEED, authority.as_ref()],
        program_id,
    )
}

/// Derive the user account PDA.
pub fn derive_user_pda(program_id: &Pubkey, agent: &Pubkey, owner: &Pubkey) -> (Pubkey, u8) {
    Pubkey::find_program_address(
        &[USER_ACCOUNT_SEED, agent.as_ref(), owner.as_ref()],
        program_id,
    )
}

/// Derive a position PDA.