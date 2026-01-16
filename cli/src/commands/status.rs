use anyhow::{Context, Result};
use solana_client::rpc_client::RpcClient;
use solana_sdk::{
    commitment_config::CommitmentConfig,
    pubkey::Pubkey,
    signature::{Keypair, Signer},
};

use crate::commands::trade::{derive_agent_pda, derive_user_pda, derive_position_pda};
use crate::display;

/// Fetch and display the trading agent status.
pub fn show_agent_status(
    rpc_url: &str,
    program_id: &Pubkey,
    authority: &Pubkey,
) -> Result<()> {
    let client = RpcClient::new_with_commitment(rpc_url, CommitmentConfig::confirmed());
    let (agent_pda, _) = derive_agent_pda(program_id, authority);

    let data = client
        .get_account_data(&agent_pda)
        .context("Agent account not found. Has it been initialized?")?;

    // Parse fields from raw account data
    // Layout after 8-byte discriminator:
    // bump(1), authority(32), quote_mint(32), vault(32), fee_receiver(32),
    // fee_bps(2), paused(1), total_deposits(8), total_withdrawals(8),
    // total_trades(8), total_fees_collected(8), created_at(8), last_activity(8)
    let mut offset = 8; // skip discriminator

    let _bump = data[offset];
    offset += 1;

    let authority_bytes = &data[offset..offset + 32];
    let authority_str = bs58::encode(authority_bytes).into_string();
    offset += 32;

    let quote_mint_bytes = &data[offset..offset + 32];
    let quote_mint_str = bs58::encode(quote_mint_bytes).into_string();
    offset += 32;

    offset += 32; // vault
    offset += 32; // fee_receiver

    let fee_bps = u16::from_le_bytes(data[offset..offset + 2].try_into().unwrap());
    offset += 2;

    let paused = data[offset] != 0;
    offset += 1;

    let total_deposits = u64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());
    offset += 8;

    let total_withdrawals = u64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());
    offset += 8;

    let total_trades = u64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());
    offset += 8;

    let total_fees = u64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());
    offset += 8;

    let created_at = i64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());
    offset += 8;

    let last_activity = i64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());

    display::display_agent_status(
        &authority_str,
        &quote_mint_str,
        fee_bps,
        paused,
        total_deposits,
        total_withdrawals,
        total_trades,
        total_fees,
        created_at,
        last_activity,
    );

    Ok(())
}

/// Fetch and display the user account status and PnL.