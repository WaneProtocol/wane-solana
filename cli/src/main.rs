use anyhow::Result;
use clap::{Parser, Subcommand};
use solana_sdk::signature::Signer;

mod commands;
mod display;

use commands::config::PikkyConfig;

#[derive(Parser)]
#[command(
    name = "pikky",
    version = "0.1.0",
    about = "PIKKY - x402 AI Trading Agent CLI for Solana",
    long_about = "Interact with the PIKKY on-chain trading agent.\nMBTI-based trading strategies powered by x402 payments."
)]
struct Cli {
    /// Override the Solana RPC URL
    #[arg(long, env = "PIKKY_RPC_URL")]
    rpc_url: Option<String>,

    /// Override the wallet keypair path
    #[arg(long, env = "PIKKY_KEYPAIR")]
    keypair: Option<String>,

    /// Override the program ID
    #[arg(long, env = "PIKKY_PROGRAM_ID")]
    program_id: Option<String>,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Execute trades on the PIKKY agent
    Trade {
        #[command(subcommand)]
        action: TradeAction,
    },

    /// Check account status, positions, and PnL
    Status {
        #[command(subcommand)]
        action: StatusAction,
    },

    /// Manage configuration and on-chain settings
    Config {
        #[command(subcommand)]
        action: ConfigAction,
    },

    /// Deposit tokens into your trading account
    Deposit {
        /// Amount in USDC to deposit
        #[arg(short, long)]
        amount: f64,
    },

    /// Withdraw tokens from your trading account
    Withdraw {
        /// Amount in USDC to withdraw (omit for full balance)
        #[arg(short, long)]
        amount: Option<f64>,
    },
}

#[derive(Subcommand)]
enum TradeAction {
    /// Open a new position
    Open {
        /// Base asset mint address
        #[arg(short, long)]
        mint: String,

        /// Trade direction: LONG or SHORT
        #[arg(short, long)]
        direction: String,

        /// Trade size in USDC