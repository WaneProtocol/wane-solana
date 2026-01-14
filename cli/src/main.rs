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
        #[arg(short, long)]
        size: f64,

        /// Current market price in USD
        #[arg(short, long)]
        price: f64,

        /// AI confidence score (0-100)
        #[arg(short, long, default_value = "70")]
        confidence: u8,

        /// Stop-loss price (optional, uses MBTI default if omitted)
        #[arg(long)]
        stop_loss: Option<f64>,

        /// Take-profit price (optional, uses MBTI default if omitted)
        #[arg(long)]
        take_profit: Option<f64>,

        /// x402 payment hash (hex-encoded 32 bytes)
        #[arg(long)]
        payment_hash: String,
    },

    /// Close an existing position
    Close {
        /// Position ID to close
        #[arg(short = 'i', long)]
        position_id: u64,

        /// Exit price in USD
        #[arg(short, long)]
        price: f64,

        /// Close reason: 0=manual, 1=stop-loss, 2=take-profit
        #[arg(short, long, default_value = "0")]
        reason: u8,
    },
}

#[derive(Subcommand)]
enum StatusAction {
    /// Show trading agent overview
    Agent,

    /// Show your account status and PnL
    Account,

    /// Show details of a specific position
    Position {
        /// Position ID
        #[arg(short = 'i', long)]
        position_id: u64,
    },
}

#[derive(Subcommand)]
enum ConfigAction {
    /// Show current configuration
    Show,

    /// Set configuration values
    Set {
        /// Solana RPC endpoint URL
        #[arg(long)]
        rpc_url: Option<String>,

        /// Path to wallet keypair file