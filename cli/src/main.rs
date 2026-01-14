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
        #[arg(long)]
        keypair: Option<String>,

        /// PIKKY program ID
        #[arg(long)]
        program_id: Option<String>,

        /// Agent authority pubkey
        #[arg(long)]
        authority: Option<String>,

        /// Default MBTI type code (0-15)
        #[arg(long)]
        mbti: Option<u8>,

        /// Transaction commitment level
        #[arg(long)]
        commitment: Option<String>,
    },

    /// Initialize your on-chain user account
    InitUser,

    /// Set your MBTI trading strategy on-chain
    SetStrategy {
        /// MBTI type code (0-15)
        #[arg(short, long)]
        mbti: u8,

        /// Use custom parameter overrides
        #[arg(long, default_value = "false")]
        custom: bool,

        /// Custom leverage (100 = 1x, max 500 = 5x)
        #[arg(long)]
        leverage: Option<u16>,

        /// Custom max position size in basis points
        #[arg(long)]
        max_position: Option<u16>,

        /// Custom cooldown in seconds
        #[arg(long)]
        cooldown: Option<i64>,

        /// Custom minimum confidence (0-100)
        #[arg(long)]
        min_confidence: Option<u8>,
    },

    /// Show MBTI type reference table
    MbtiTypes,
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    // Load base config, apply CLI overrides
    let mut config = PikkyConfig::load()?;

    if let Some(url) = &cli.rpc_url {
        config.rpc_url = url.clone();
    }
    if let Some(kp) = &cli.keypair {
        config.keypair_path = kp.clone();
    }
    if let Some(pid) = &cli.program_id {
        config.program_id = pid.clone();
    }

    match cli.command {
        Commands::Trade { action } => {
            let keypair = config.load_keypair()?;
            let program_id = config.program_id()?;
            let authority = config.authority()?;

            match action {
                TradeAction::Open {
                    mint,
                    direction,
                    size,
                    price,
                    confidence,
                    stop_loss,
                    take_profit,
                    payment_hash,
                } => {
                    display::print_banner();
                    let hash_bytes = parse_hex_hash(&payment_hash)?;
                    commands::trade::execute_open_trade(
                        &config.rpc_url,
                        &program_id,
                        &keypair,
                        &authority,
                        &mint,
                        &direction,
                        size,
                        price,
                        confidence,
                        stop_loss,
                        take_profit,
                        hash_bytes,
                    )?;
                }
                TradeAction::Close {
                    position_id,
                    price,
                    reason,
                } => {
                    display::print_banner();
                    commands::trade::execute_close_position(
                        &config.rpc_url,
                        &program_id,
                        &keypair,
                        &authority,
                        position_id,
                        price,
                        reason,
                    )?;
                }
            }
        }

        Commands::Status { action } => {
            let program_id = config.program_id()?;
            let authority = config.authority()?;

            match action {
                StatusAction::Agent => {
                    display::print_banner();
                    commands::status::show_agent_status(
                        &config.rpc_url,
                        &program_id,
                        &authority,
                    )?;
                }
                StatusAction::Account => {
                    display::print_banner();
                    let keypair = config.load_keypair()?;
                    commands::status::show_user_status(
                        &config.rpc_url,
                        &program_id,
                        &keypair,
                        &authority,
                    )?;
                }
                StatusAction::Position { position_id } => {
                    display::print_banner();
                    let keypair = config.load_keypair()?;
                    commands::status::show_position(
                        &config.rpc_url,
                        &program_id,
                        &keypair,
                        &authority,
                        position_id,
                    )?;
                }
            }
        }

        Commands::Config { action } => match action {
            ConfigAction::Show => {
                display::print_banner();
                commands::config::show_config()?;
            }
            ConfigAction::Set {
                rpc_url,
                keypair,
                program_id,
                authority,
                mbti,
                commitment,
            } => {
                commands::config::set_config(
                    rpc_url, keypair, program_id, authority, mbti, commitment,
                )?;
            }
            ConfigAction::InitUser => {
                display::print_banner();
                let keypair = config.load_keypair()?;
                let program_id = config.program_id()?;
                let authority = config.authority()?;
                display::print_info(&format!("Initializing user account for {}", keypair.pubkey()));
                commands::config::init_user_account(
                    &config.rpc_url,
                    &program_id,
                    &keypair,
                    &authority,
                )?;
            }
            ConfigAction::SetStrategy {
                mbti,
                custom,
                leverage,
                max_position,
                cooldown,
                min_confidence,
            } => {
                display::print_banner();
                let keypair = config.load_keypair()?;
                let program_id = config.program_id()?;
                let authority = config.authority()?;
                commands::config::set_strategy_on_chain(
                    &config.rpc_url,
                    &program_id,
                    &keypair,
                    &authority,
                    mbti,
                    custom,
                    leverage,
                    max_position,
                    cooldown,
                    min_confidence,
                )?;
            }
            ConfigAction::MbtiTypes => {
                display::print_banner();
                commands::config::print_mbti_reference();
            }
        },

        Commands::Deposit { amount } => {
            display::print_banner();
            let keypair = config.load_keypair()?;
            let program_id = config.program_id()?;
            let authority = config.authority()?;
            display::print_info(&format!("Depositing {} USDC...", amount));
            commands::trade::execute_deposit(
                &config.rpc_url,
                &program_id,
                &keypair,
                &authority,
                amount,
            )?;
        }

        Commands::Withdraw { amount } => {
            display::print_banner();
            let keypair = config.load_keypair()?;
            let program_id = config.program_id()?;
            let authority = config.authority()?;
            let label = amount
                .map(|a| format!("{} USDC", a))
                .unwrap_or_else(|| "all funds".to_string());
            display::print_info(&format!("Withdrawing {}...", label));
            commands::trade::execute_withdraw(
                &config.rpc_url,
                &program_id,
                &keypair,
                &authority,
                amount,
            )?;
        }
    }

    Ok(())
}

/// Parse a hex-encoded string into a 32-byte array.
fn parse_hex_hash(hex: &str) -> Result<[u8; 32]> {
    let hex = hex.strip_prefix("0x").unwrap_or(hex);
    if hex.len() != 64 {
        anyhow::bail!("Payment hash must be exactly 64 hex characters (32 bytes)");
    }

    let mut bytes = [0u8; 32];
    for i in 0..32 {
        bytes[i] = u8::from_str_radix(&hex[i * 2..i * 2 + 2], 16)
            .map_err(|_| anyhow::anyhow!("Invalid hex character in payment hash"))?;
    }
    Ok(bytes)
}
