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
pub fn derive_position_pda(
    program_id: &Pubkey,
    user_account: &Pubkey,
    position_id: u64,
) -> (Pubkey, u8) {
    Pubkey::find_program_address(
        &[
            POSITION_SEED,
            user_account.as_ref(),
            &position_id.to_le_bytes(),
        ],
        program_id,
    )
}

/// Derive an x402 payment PDA.
pub fn derive_x402_payment_pda(
    program_id: &Pubkey,
    user_account: &Pubkey,
    payment_hash: &[u8; 32],
) -> (Pubkey, u8) {
    Pubkey::find_program_address(
        &[X402_PAYMENT_SEED, user_account.as_ref(), payment_hash],
        program_id,
    )
}

/// Open a new trade position via the on-chain program.
pub fn execute_open_trade(
    rpc_url: &str,
    program_id: &Pubkey,
    keypair: &Keypair,
    authority: &Pubkey,
    base_mint: &str,
    direction: &str,
    size: f64,
    price: f64,
    confidence: u8,
    stop_loss_override: Option<f64>,
    take_profit_override: Option<f64>,
    payment_hash: [u8; 32],
) -> Result<()> {
    let client = RpcClient::new_with_commitment(rpc_url, CommitmentConfig::confirmed());
    let payer = keypair;

    let (agent_pda, _) = derive_agent_pda(program_id, authority);
    let (user_pda, _) = derive_user_pda(program_id, &agent_pda, &payer.pubkey());

    // Fetch user account to determine next position ID
    let user_data = client
        .get_account_data(&user_pda)
        .context("Failed to fetch user account. Has it been initialized?")?;

    // Parse total_trades from user account data to derive position_id
    // Offset: 8 (disc) + 1 (bump) + 32 (agent) + 32 (owner) + 8 (balance) + 8 (pnl)
    //         + 2 (open_pos) + 4 (total_trades)
    let total_trades_offset = 8 + 1 + 32 + 32 + 8 + 8 + 2;
    let total_trades = if user_data.len() > total_trades_offset + 4 {
        u32::from_le_bytes(
            user_data[total_trades_offset..total_trades_offset + 4]
                .try_into()
                .unwrap_or([0; 4]),
        )
    } else {
        0u32
    };
    let position_id = total_trades as u64;

    let (position_pda, _) = derive_position_pda(program_id, &user_pda, position_id);
    let (x402_pda, _) = derive_x402_payment_pda(program_id, &user_pda, &payment_hash);

    let base_mint_pubkey = Pubkey::from_str(base_mint)
        .context("Invalid base mint address")?;

    // Convert human-readable values to on-chain representation
    let size_lamports = (size * 1_000_000.0) as u64;
    let price_scaled = (price * 1_000_000.0) as u64;
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs() as i64;

    let sl = stop_loss_override.map(|p| (p * 1_000_000.0) as u64).unwrap_or(0);
    let tp = take_profit_override.map(|p| (p * 1_000_000.0) as u64).unwrap_or(0);

    let dir_byte: u8 = match direction.to_uppercase().as_str() {
        "LONG" => 0,
        "SHORT" => 1,
        _ => bail!("Invalid direction: use LONG or SHORT"),
    };

    // We need the vault and fee_receiver_token accounts.
    // Fetch agent account to read vault and fee_receiver.
    let agent_data = client
        .get_account_data(&agent_pda)
        .context("Failed to fetch agent account")?;

    // Parse vault pubkey from agent data
    // Offset: 8 (disc) + 1 (bump) + 32 (authority) + 32 (quote_mint) = 73
    let vault_offset = 8 + 1 + 32 + 32;
    let vault_pubkey = Pubkey::try_from(&agent_data[vault_offset..vault_offset + 32])
        .context("Failed to parse vault from agent data")?;

    // Parse fee_receiver from agent data: vault_offset + 32 = 105
    let fee_offset = vault_offset + 32;
    let fee_receiver = Pubkey::try_from(&agent_data[fee_offset..fee_offset + 32])
        .context("Failed to parse fee_receiver from agent data")?;

    // Derive fee_receiver token ATA (assume USDC)
    let quote_mint_offset = 8 + 1 + 32;
    let quote_mint_pubkey = Pubkey::try_from(&agent_data[quote_mint_offset..quote_mint_offset + 32])
        .context("Failed to parse quote_mint")?;

    let fee_receiver_token = spl_associated_token_account::get_associated_token_address(
        &fee_receiver,
        &quote_mint_pubkey,
    );

    // Build the instruction data
    // Anchor instruction discriminator for "execute_trade"
    let mut ix_data = Vec::new();
    // sighash("global:execute_trade")
    let discriminator = anchor_lang::solana_program::hash::hash(b"global:execute_trade");
    ix_data.extend_from_slice(&discriminator.to_bytes()[..8]);

    // Serialize params: position_id, base_mint, direction, size, price, price_timestamp,
    //                    confidence, stop_loss, take_profit
    ix_data.extend_from_slice(&position_id.to_le_bytes());
    ix_data.extend_from_slice(base_mint_pubkey.as_ref());
    ix_data.push(dir_byte);
    ix_data.extend_from_slice(&size_lamports.to_le_bytes());
    ix_data.extend_from_slice(&price_scaled.to_le_bytes());
    ix_data.extend_from_slice(&now.to_le_bytes());
    ix_data.push(confidence);
    ix_data.extend_from_slice(&sl.to_le_bytes());
    ix_data.extend_from_slice(&tp.to_le_bytes());

    let token_program = spl_token::id();

    let accounts = vec![
        AccountMeta::new(agent_pda, false),
        AccountMeta::new(user_pda, false),
        AccountMeta::new(position_pda, false),
        AccountMeta::new(x402_pda, false),
        AccountMeta::new(vault_pubkey, false),
        AccountMeta::new(fee_receiver_token, false),
        AccountMeta::new(payer.pubkey(), true),
        AccountMeta::new_readonly(system_program::id(), false),
        AccountMeta::new_readonly(token_program, false),
    ];

    let ix = Instruction {
        program_id: *program_id,
        accounts,
        data: ix_data,
    };

    let recent_blockhash = client.get_latest_blockhash()?;
    let tx = Transaction::new_signed_with_payer(
        &[ix],
        Some(&payer.pubkey()),
        &[payer],
        recent_blockhash,
    );

    let sig = client
        .send_and_confirm_transaction(&tx)
        .context("Failed to send execute_trade transaction")?;

    display::display_trade_confirmation(
        position_id,
        direction,
        size_lamports,
        price_scaled,
        0, // leverage read from profile on-chain
        sl,
        tp,
        0, // fee computed on-chain
        "from-profile",
        confidence,
        &sig.to_string(),
    );

    Ok(())
}

/// Close an existing position.
pub fn execute_close_position(
    rpc_url: &str,
    program_id: &Pubkey,
    keypair: &Keypair,
    authority: &Pubkey,
    position_id: u64,
    exit_price: f64,
    close_reason: u8,
) -> Result<()> {
    let client = RpcClient::new_with_commitment(rpc_url, CommitmentConfig::confirmed());
    let payer = keypair;

    let (agent_pda, _) = derive_agent_pda(program_id, authority);
    let (user_pda, _) = derive_user_pda(program_id, &agent_pda, &payer.pubkey());
    let (position_pda, _) = derive_position_pda(program_id, &user_pda, position_id);

    let agent_data = client.get_account_data(&agent_pda)?;
    let vault_offset = 8 + 1 + 32 + 32;
    let vault_pubkey = Pubkey::try_from(&agent_data[vault_offset..vault_offset + 32])?;

    let price_scaled = (exit_price * 1_000_000.0) as u64;
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs() as i64;

    let mut ix_data = Vec::new();
    let discriminator = anchor_lang::solana_program::hash::hash(b"global:close_position");
    ix_data.extend_from_slice(&discriminator.to_bytes()[..8]);
    ix_data.extend_from_slice(&price_scaled.to_le_bytes());
    ix_data.extend_from_slice(&now.to_le_bytes());
    ix_data.push(close_reason);

    let token_program = spl_token::id();

    let accounts = vec![
        AccountMeta::new(agent_pda, false),
        AccountMeta::new(user_pda, false),
        AccountMeta::new(position_pda, false),
        AccountMeta::new(vault_pubkey, false),
        AccountMeta::new(payer.pubkey(), true),
        AccountMeta::new_readonly(token_program, false),
    ];

    let ix = Instruction {
        program_id: *program_id,
        accounts,
        data: ix_data,
    };

    let recent_blockhash = client.get_latest_blockhash()?;
    let tx = Transaction::new_signed_with_payer(
        &[ix],
        Some(&payer.pubkey()),
        &[payer],
        recent_blockhash,
    );

    let sig = client.send_and_confirm_transaction(&tx)?;
    display::print_success(&format!(
        "Position #{} closed @ {}. Tx: {}",
        position_id,
        display::format_price(price_scaled),
        sig,
    ));

    Ok(())
}

/// Deposit tokens into the user's trading account.
pub fn execute_deposit(
    rpc_url: &str,
    program_id: &Pubkey,
    keypair: &Keypair,
    authority: &Pubkey,
    amount: f64,
) -> Result<()> {
    let client = RpcClient::new_with_commitment(rpc_url, CommitmentConfig::confirmed());
    let payer = keypair;

    let (agent_pda, _) = derive_agent_pda(program_id, authority);
    let (user_pda, _) = derive_user_pda(program_id, &agent_pda, &payer.pubkey());

    let agent_data = client.get_account_data(&agent_pda)?;
    let vault_offset = 8 + 1 + 32 + 32;
    let vault_pubkey = Pubkey::try_from(&agent_data[vault_offset..vault_offset + 32])?;

    let quote_mint_offset = 8 + 1 + 32;
    let quote_mint = Pubkey::try_from(&agent_data[quote_mint_offset..quote_mint_offset + 32])?;

    let user_ata = spl_associated_token_account::get_associated_token_address(
        &payer.pubkey(),
        &quote_mint,
    );

    let amount_lamports = (amount * 1_000_000.0) as u64;

    let mut ix_data = Vec::new();
    let discriminator = anchor_lang::solana_program::hash::hash(b"global:deposit");
    ix_data.extend_from_slice(&discriminator.to_bytes()[..8]);
    ix_data.extend_from_slice(&amount_lamports.to_le_bytes());

    let token_program = spl_token::id();

    let accounts = vec![
        AccountMeta::new(agent_pda, false),
        AccountMeta::new(user_pda, false),
        AccountMeta::new(vault_pubkey, false),
        AccountMeta::new(user_ata, false),
        AccountMeta::new(payer.pubkey(), true),
        AccountMeta::new_readonly(token_program, false),
    ];

    let ix = Instruction {
        program_id: *program_id,
        accounts,
        data: ix_data,
    };

    let recent_blockhash = client.get_latest_blockhash()?;
    let tx = Transaction::new_signed_with_payer(
        &[ix],
        Some(&payer.pubkey()),
        &[payer],
        recent_blockhash,
    );

    let sig = client.send_and_confirm_transaction(&tx)?;

    // Fetch updated balance
    let updated_user_data = client.get_account_data(&user_pda)?;
    let balance_offset = 8 + 1 + 32 + 32;
    let new_balance = u64::from_le_bytes(
        updated_user_data[balance_offset..balance_offset + 8]
            .try_into()
            .unwrap_or([0; 8]),
    );

    display::display_transfer_confirmation("Deposit", amount_lamports, new_balance, &sig.to_string());

    Ok(())
}

/// Withdraw tokens from the user's trading account.
pub fn execute_withdraw(
    rpc_url: &str,
    program_id: &Pubkey,
    keypair: &Keypair,
    authority: &Pubkey,
    amount: Option<f64>,
) -> Result<()> {
    let client = RpcClient::new_with_commitment(rpc_url, CommitmentConfig::confirmed());
    let payer = keypair;

    let (agent_pda, _) = derive_agent_pda(program_id, authority);
    let (user_pda, _) = derive_user_pda(program_id, &agent_pda, &payer.pubkey());

    let agent_data = client.get_account_data(&agent_pda)?;
    let vault_offset = 8 + 1 + 32 + 32;
    let vault_pubkey = Pubkey::try_from(&agent_data[vault_offset..vault_offset + 32])?;

    let quote_mint_offset = 8 + 1 + 32;
    let quote_mint = Pubkey::try_from(&agent_data[quote_mint_offset..quote_mint_offset + 32])?;

    let user_ata = spl_associated_token_account::get_associated_token_address(
        &payer.pubkey(),
        &quote_mint,
    );

    let amount_lamports = match amount {
        Some(a) => (a * 1_000_000.0) as u64,
        None => u64::MAX, // signals "withdraw all"
    };

    let mut ix_data = Vec::new();
    let discriminator = anchor_lang::solana_program::hash::hash(b"global:withdraw");
    ix_data.extend_from_slice(&discriminator.to_bytes()[..8]);
    ix_data.extend_from_slice(&amount_lamports.to_le_bytes());

    let token_program = spl_token::id();

    let accounts = vec![
        AccountMeta::new(agent_pda, false),
        AccountMeta::new(user_pda, false),
        AccountMeta::new(vault_pubkey, false),
        AccountMeta::new(user_ata, false),
        AccountMeta::new(payer.pubkey(), true),
        AccountMeta::new_readonly(token_program, false),
    ];

    let ix = Instruction {
        program_id: *program_id,
        accounts,
        data: ix_data,
    };

    let recent_blockhash = client.get_latest_blockhash()?;
    let tx = Transaction::new_signed_with_payer(
        &[ix],
        Some(&payer.pubkey()),
        &[payer],
        recent_blockhash,
    );

    let sig = client.send_and_confirm_transaction(&tx)?;

    let updated_user_data = client.get_account_data(&user_pda)?;
    let balance_offset = 8 + 1 + 32 + 32;
    let new_balance = u64::from_le_bytes(
        updated_user_data[balance_offset..balance_offset + 8]
            .try_into()
            .unwrap_or([0; 8]),
    );

    let display_amount = if amount_lamports == u64::MAX {
        0 // will show "all" effectively via balance diff
    } else {
        amount_lamports
    };

    display::display_transfer_confirmation("Withdrawal", display_amount, new_balance, &sig.to_string());

    Ok(())
}
