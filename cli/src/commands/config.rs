use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};
use solana_client::rpc_client::RpcClient;
use solana_sdk::{
    commitment_config::CommitmentConfig,
    instruction::{AccountMeta, Instruction},
    pubkey::Pubkey,
    signature::{Keypair, Signer, read_keypair_file},
    transaction::Transaction,
    system_program,
};
use std::fs;
use std::path::PathBuf;
use std::str::FromStr;

use crate::commands::trade::{derive_agent_pda, derive_user_pda};
use crate::display;

/// Persistent CLI configuration stored on disk.
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct PikkyConfig {
    /// Solana RPC endpoint URL
    pub rpc_url: String,
    /// Path to the wallet keypair file
    pub keypair_path: String,
    /// The PIKKY program ID
    pub program_id: String,
    /// The agent authority pubkey (needed to derive PDAs)
    pub authority: String,
    /// Default MBTI type code (0-15)
    pub default_mbti: u8,
    /// Commitment level
    pub commitment: String,
}

impl Default for PikkyConfig {
    fn default() -> Self {
        Self {
            rpc_url: "https://api.devnet.solana.com".to_string(),
            keypair_path: "~/.config/solana/id.json".to_string(),
            program_id: "PiKKYagent1111111111111111111111111111111111".to_string(),
            authority: String::new(),
            default_mbti: 8, // ISTJ default
            commitment: "confirmed".to_string(),
        }
    }
}

impl PikkyConfig {
    /// Get the config file path.
    pub fn config_path() -> PathBuf {
        let home = dirs::home_dir().unwrap_or_else(|| PathBuf::from("."));
        home.join(".config").join("pikky").join("config.toml")
    }

    /// Load config from disk, or return default.