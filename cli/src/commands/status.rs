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
pub fn show_user_status(
    rpc_url: &str,
    program_id: &Pubkey,
    keypair: &Keypair,
    authority: &Pubkey,
) -> Result<()> {
    let client = RpcClient::new_with_commitment(rpc_url, CommitmentConfig::confirmed());
    let (agent_pda, _) = derive_agent_pda(program_id, authority);
    let (user_pda, _) = derive_user_pda(program_id, &agent_pda, &keypair.pubkey());

    let data = client
        .get_account_data(&user_pda)
        .context("User account not found. Run 'pikky config init-user' first.")?;

    // Parse user account data
    let mut offset = 8; // discriminator

    let _bump = data[offset];
    offset += 1;

    offset += 32; // trading_agent

    let owner_bytes = &data[offset..offset + 32];
    let owner_str = bs58::encode(owner_bytes).into_string();
    offset += 32;

    let balance = u64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());
    offset += 8;

    let realized_pnl = i64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());
    offset += 8;

    let open_positions = u16::from_le_bytes(data[offset..offset + 2].try_into().unwrap());
    offset += 2;

    let total_trades = u32::from_le_bytes(data[offset..offset + 4].try_into().unwrap());
    offset += 4;

    let winning_trades = u32::from_le_bytes(data[offset..offset + 4].try_into().unwrap());
    offset += 4;

    // MbtiProfile: mbti_type(1), max_position_bps(2), max_drawdown_bps(2),
    //   trade_cooldown_secs(8), leverage_factor(2), slippage_tolerance_bps(2),
    //   trend_following(1), min_confidence(1), take_profit_bps(2), stop_loss_bps(2)
    let mbti_code = data[offset];
    let mbti_name = mbti_code_to_name(mbti_code);
    let profile_start = offset;
    offset += 1; // mbti_type

    let max_position_bps = u16::from_le_bytes(data[offset..offset + 2].try_into().unwrap());
    offset += 2;
    let max_drawdown_bps = u16::from_le_bytes(data[offset..offset + 2].try_into().unwrap());
    offset += 2;
    let cooldown_secs = i64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());
    offset += 8;
    let leverage = u16::from_le_bytes(data[offset..offset + 2].try_into().unwrap());
    offset += 2;
    let slippage_bps = u16::from_le_bytes(data[offset..offset + 2].try_into().unwrap());
    offset += 2;
    let trend_following = data[offset] != 0;
    offset += 1;
    let min_confidence = data[offset];
    offset += 1;
    let take_profit_bps = u16::from_le_bytes(data[offset..offset + 2].try_into().unwrap());
    offset += 2;
    let stop_loss_bps = u16::from_le_bytes(data[offset..offset + 2].try_into().unwrap());
    offset += 2;

    let strategy_configured = data[offset] != 0;
    offset += 1;

    offset += 8; // created_at

    let last_trade_at = i64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());
    offset += 8;

    let x402_payments = u64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());

    display::display_user_status(
        &owner_str,
        balance,
        realized_pnl,
        open_positions,
        total_trades,
        winning_trades,
        mbti_name,
        strategy_configured,
        last_trade_at,
        x402_payments,
    );

    // Also display strategy details
    display::display_strategy(
        mbti_name,
        max_position_bps,
        max_drawdown_bps,
        cooldown_secs,
        leverage,
        slippage_bps,
        trend_following,
        min_confidence,
        take_profit_bps,
        stop_loss_bps,
    );

    Ok(())
}

/// Show details of a specific position.
pub fn show_position(
    rpc_url: &str,
    program_id: &Pubkey,
    keypair: &Keypair,
    authority: &Pubkey,
    position_id: u64,
) -> Result<()> {
    let client = RpcClient::new_with_commitment(rpc_url, CommitmentConfig::confirmed());
    let (agent_pda, _) = derive_agent_pda(program_id, authority);
    let (user_pda, _) = derive_user_pda(program_id, &agent_pda, &keypair.pubkey());
    let (position_pda, _) = derive_position_pda(program_id, &user_pda, position_id);

    let data = client
        .get_account_data(&position_pda)
        .context(format!("Position #{} not found", position_id))?;

    // Parse position data
    let mut offset = 8; // discriminator

    let _bump = data[offset];
    offset += 1;

    offset += 32; // user_account

    let pos_id = u64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());
    offset += 8;

    let base_mint_bytes = &data[offset..offset + 32];
    let base_mint_str = bs58::encode(base_mint_bytes).into_string();
    offset += 32;

    let direction_byte = data[offset];
    let direction_str = if direction_byte == 0 { "LONG" } else { "SHORT" };
    offset += 1;

    let size = u64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());
    offset += 8;

    let entry_price = u64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());
    offset += 8;

    let exit_price = u64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());
    offset += 8;

    let leverage = u16::from_le_bytes(data[offset..offset + 2].try_into().unwrap());
    offset += 2;

    let stop_loss = u64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());
    offset += 8;

    let take_profit = u64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());
    offset += 8;

    let pnl = i64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());
    offset += 8;

    let status_byte = data[offset];
    let status_str = match status_byte {
        0 => "Open",
        1 => "Closed",
        2 => "Liquidated",
        3 => "Stop-Loss",
        4 => "Take-Profit",
        _ => "Unknown",
    };
    offset += 1;

    let mbti_code = data[offset];
    let mbti_name = mbti_code_to_name(mbti_code);
    offset += 1;

    let confidence = data[offset];
    offset += 1;

    let opened_at = i64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());
    offset += 8;

    let closed_at = i64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());
    offset += 8;

    let fee_paid = u64::from_le_bytes(data[offset..offset + 8].try_into().unwrap());

    display::print_header(&format!("Position #{}", pos_id));
    display::print_kv("Status", status_str);
    display::print_kv("Direction", direction_str);
    display::print_kv("Base Asset", &base_mint_str);
    display::print_kv("Size", &format!("{} USDC", display::format_amount(size, 6)));
    display::print_kv("Entry Price", &display::format_price(entry_price));
    if exit_price > 0 {
        display::print_kv("Exit Price", &display::format_price(exit_price));
    }
    display::print_kv("Leverage", &display::format_leverage(leverage));
    display::print_kv("Stop Loss", &display::format_price(stop_loss));
    display::print_kv("Take Profit", &display::format_price(take_profit));
    display::print_kv_pnl("PnL", pnl, 6);
    display::print_kv("Strategy", mbti_name);
    display::print_kv("Confidence", &format!("{}%", confidence));
    display::print_kv("Fee Paid", &format!("{} USDC", display::format_amount(fee_paid, 6)));
    display::print_kv("Opened", &display::format_timestamp(opened_at));
    if closed_at > 0 {
        display::print_kv("Closed", &display::format_timestamp(closed_at));
    }
    println!();

    Ok(())
}

/// Map an MBTI code byte to its string name.
fn mbti_code_to_name(code: u8) -> &'static str {
    match code {
        0 => "INTJ",
        1 => "INTP",
        2 => "ENTJ",
        3 => "ENTP",
        4 => "INFJ",
        5 => "INFP",
        6 => "ENFJ",
        7 => "ENFP",
        8 => "ISTJ",
        9 => "ISFJ",
        10 => "ESTJ",
        11 => "ESFJ",
        12 => "ISTP",
        13 => "ISFP",
        14 => "ESTP",
        15 => "ESFP",
        _ => "Unknown",
    }
}
