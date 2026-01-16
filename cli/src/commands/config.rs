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
    pub fn load() -> Result<Self> {
        let path = Self::config_path();
        if path.exists() {
            let content = fs::read_to_string(&path)
                .context("Failed to read config file")?;
            let config: PikkyConfig = toml::from_str(&content)
                .context("Failed to parse config file")?;
            Ok(config)
        } else {
            Ok(Self::default())
        }
    }

    /// Save config to disk.
    pub fn save(&self) -> Result<()> {
        let path = Self::config_path();
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        let content = toml::to_string_pretty(self)?;
        fs::write(&path, content)?;
        Ok(())
    }

    /// Resolve the keypair path (expand ~).
    pub fn resolve_keypair_path(&self) -> PathBuf {
        let expanded = if self.keypair_path.starts_with('~') {
            let home = dirs::home_dir().unwrap_or_else(|| PathBuf::from("."));
            home.join(&self.keypair_path[2..])
        } else {
            PathBuf::from(&self.keypair_path)
        };
        expanded
    }

    /// Load the keypair from the configured path.
    pub fn load_keypair(&self) -> Result<Keypair> {
        let path = self.resolve_keypair_path();
        let path_str = path.to_string_lossy().to_string();
        read_keypair_file(&path_str)
            .map_err(|e| anyhow::anyhow!("Failed to read keypair from {}: {}", path_str, e))
    }

    /// Parse the program ID.
    pub fn program_id(&self) -> Result<Pubkey> {
        Pubkey::from_str(&self.program_id)
            .context("Invalid program ID in config")
    }

    /// Parse the authority pubkey.
    pub fn authority(&self) -> Result<Pubkey> {
        if self.authority.is_empty() {
            bail!("Authority not set in config. Run 'pikky config set --authority <PUBKEY>'");
        }
        Pubkey::from_str(&self.authority)
            .context("Invalid authority pubkey in config")
    }
}

/// Set a configuration value.
pub fn set_config(
    rpc_url: Option<String>,
    keypair_path: Option<String>,
    program_id: Option<String>,
    authority: Option<String>,
    default_mbti: Option<u8>,
    commitment: Option<String>,
) -> Result<()> {
    let mut config = PikkyConfig::load()?;

    if let Some(url) = rpc_url {
        config.rpc_url = url;
        display::print_success(&format!("RPC URL set to: {}", config.rpc_url));
    }

    if let Some(path) = keypair_path {
        config.keypair_path = path;
        display::print_success(&format!("Keypair path set to: {}", config.keypair_path));
    }

    if let Some(pid) = program_id {
        // Validate it's a valid pubkey
        Pubkey::from_str(&pid).context("Invalid program ID")?;
        config.program_id = pid;
        display::print_success(&format!("Program ID set to: {}", config.program_id));
    }

    if let Some(auth) = authority {
        Pubkey::from_str(&auth).context("Invalid authority pubkey")?;
        config.authority = auth;
        display::print_success(&format!("Authority set to: {}", config.authority));
    }

    if let Some(mbti) = default_mbti {
        if mbti > 15 {
            bail!("MBTI code must be 0-15");
        }
        config.default_mbti = mbti;
        display::print_success(&format!("Default MBTI set to code: {}", mbti));
    }

    if let Some(c) = commitment {
        match c.as_str() {
            "processed" | "confirmed" | "finalized" => {
                config.commitment = c;
                display::print_success(&format!("Commitment set to: {}", config.commitment));
            }
            _ => bail!("Invalid commitment: use processed, confirmed, or finalized"),
        }
    }

    config.save()?;
    Ok(())
}

/// Display current configuration.
pub fn show_config() -> Result<()> {
    let config = PikkyConfig::load()?;

    display::print_header("PIKKY Configuration");
    display::print_kv("Config File", &PikkyConfig::config_path().to_string_lossy());
    display::print_kv("RPC URL", &config.rpc_url);
    display::print_kv("Keypair", &config.keypair_path);
    display::print_kv("Program ID", &config.program_id);
    display::print_kv(
        "Authority",
        if config.authority.is_empty() {
            "(not set)"
        } else {
            &config.authority
        },
    );
    display::print_kv("Default MBTI", &format!("code {}", config.default_mbti));
    display::print_kv("Commitment", &config.commitment);

    // Try to load and show wallet pubkey
    match config.load_keypair() {
        Ok(kp) => display::print_kv("Wallet", &kp.pubkey().to_string()),
        Err(_) => display::print_kv("Wallet", "(keypair not found)"),
    }

    println!();
    Ok(())
}

/// Initialize the user's on-chain account.
pub fn init_user_account(
    rpc_url: &str,
    program_id: &Pubkey,
    keypair: &Keypair,
    authority: &Pubkey,
) -> Result<()> {
    let client = RpcClient::new_with_commitment(rpc_url, CommitmentConfig::confirmed());
    let (agent_pda, _) = derive_agent_pda(program_id, authority);
    let (user_pda, _) = derive_user_pda(program_id, &agent_pda, &keypair.pubkey());

    // Check if already exists
    if client.get_account_data(&user_pda).is_ok() {
        display::print_warning("User account already exists.");
        return Ok(());
    }

    let mut ix_data = Vec::new();
    let discriminator = anchor_lang::solana_program::hash::hash(b"global:initialize_user");
    ix_data.extend_from_slice(&discriminator.to_bytes()[..8]);

    let accounts = vec![
        AccountMeta::new_readonly(agent_pda, false),
        AccountMeta::new(user_pda, false),
        AccountMeta::new(keypair.pubkey(), true),
        AccountMeta::new_readonly(system_program::id(), false),
    ];

    let ix = Instruction {
        program_id: *program_id,
        accounts,
        data: ix_data,
    };

    let recent_blockhash = client.get_latest_blockhash()?;
    let tx = Transaction::new_signed_with_payer(
        &[ix],
        Some(&keypair.pubkey()),
        &[keypair],
        recent_blockhash,
    );

    let sig = client.send_and_confirm_transaction(&tx)?;
    display::print_success(&format!(
        "User account initialized. PDA: {}, Tx: {}",
        user_pda, sig,
    ));

    Ok(())
}

/// Set the MBTI trading strategy on-chain.
pub fn set_strategy_on_chain(
    rpc_url: &str,
    program_id: &Pubkey,
    keypair: &Keypair,
    authority: &Pubkey,
    mbti_code: u8,
    use_custom: bool,
    custom_leverage: Option<u16>,
    custom_max_position: Option<u16>,
    custom_cooldown: Option<i64>,
    custom_confidence: Option<u8>,
) -> Result<()> {
    if mbti_code > 15 {
        bail!("MBTI code must be 0-15");
    }

    let client = RpcClient::new_with_commitment(rpc_url, CommitmentConfig::confirmed());
    let (agent_pda, _) = derive_agent_pda(program_id, authority);
    let (user_pda, _) = derive_user_pda(program_id, &agent_pda, &keypair.pubkey());

    let mut ix_data = Vec::new();
    let discriminator = anchor_lang::solana_program::hash::hash(b"global:set_strategy");
    ix_data.extend_from_slice(&discriminator.to_bytes()[..8]);

    // Serialize SetStrategyParams manually
    ix_data.push(mbti_code);
    ix_data.push(if use_custom { 1 } else { 0 });

    // Option<u16> serialization (borsh): 0 = None, 1 + value = Some
    fn push_option_u16(buf: &mut Vec<u8>, val: Option<u16>) {
        match val {
            Some(v) => {
                buf.push(1);
                buf.extend_from_slice(&v.to_le_bytes());
            }
            None => buf.push(0),
        }
    }

    fn push_option_i64(buf: &mut Vec<u8>, val: Option<i64>) {
        match val {
            Some(v) => {
                buf.push(1);
                buf.extend_from_slice(&v.to_le_bytes());
            }
            None => buf.push(0),
        }
    }

    fn push_option_u8(buf: &mut Vec<u8>, val: Option<u8>) {
        match val {
            Some(v) => {
                buf.push(1);
                buf.push(v);
            }
            None => buf.push(0),
        }
    }

    push_option_u16(&mut ix_data, custom_max_position); // custom_max_position_bps
    push_option_u16(&mut ix_data, None);                // custom_max_drawdown_bps
    push_option_i64(&mut ix_data, custom_cooldown);     // custom_cooldown_secs
    push_option_u16(&mut ix_data, custom_leverage);     // custom_leverage
    push_option_u16(&mut ix_data, None);                // custom_slippage_bps
    push_option_u8(&mut ix_data, custom_confidence);    // custom_min_confidence
    push_option_u16(&mut ix_data, None);                // custom_take_profit_bps
    push_option_u16(&mut ix_data, None);                // custom_stop_loss_bps

    let accounts = vec![
        AccountMeta::new_readonly(agent_pda, false),
        AccountMeta::new(user_pda, false),
        AccountMeta::new_readonly(keypair.pubkey(), true),
    ];

    let ix = Instruction {
        program_id: *program_id,
        accounts,
        data: ix_data,
    };

    let recent_blockhash = client.get_latest_blockhash()?;
    let tx = Transaction::new_signed_with_payer(
        &[ix],
        Some(&keypair.pubkey()),
        &[keypair],
        recent_blockhash,
    );

    let sig = client.send_and_confirm_transaction(&tx)?;

    let mbti_names = [
        "INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP",
    ];
    let name = mbti_names.get(mbti_code as usize).unwrap_or(&"Unknown");

    display::print_success(&format!(
        "Strategy set to {} (code {}). Tx: {}",
        name, mbti_code, sig,
    ));

    Ok(())
}

/// Print the MBTI type reference table.
pub fn print_mbti_reference() {
    display::print_header("MBTI Trading Archetypes");

    let types = [
        (0, "INTJ", "The Architect", "Systematic trend-following, low frequency, high conviction"),
        (1, "INTP", "The Logician", "Mean-reversion quant, statistical arbitrage"),
        (2, "ENTJ", "The Commander", "Aggressive momentum, high leverage"),
        (3, "ENTP", "The Debater", "Contrarian plays, volatility harvesting"),
        (4, "INFJ", "The Advocate", "ESG-weighted, long-horizon value"),
        (5, "INFP", "The Mediator", "Sentiment-driven, narrative trading"),
        (6, "ENFJ", "The Protagonist", "Social-signal copy trading"),
        (7, "ENFP", "The Campaigner", "Hype-cycle momentum, meme awareness"),
        (8, "ISTJ", "The Logistician", "Conservative DCA, blue-chip only"),
        (9, "ISFJ", "The Defender", "Capital preservation, hedged positions"),
        (10, "ESTJ", "The Executive", "Rule-based breakout trading"),
        (11, "ESFJ", "The Consul", "Community-consensus following"),
        (12, "ISTP", "The Virtuoso", "Scalping, high-frequency micro trades"),
        (13, "ISFP", "The Adventurer", "Artistic pattern recognition, chart-based"),
        (14, "ESTP", "The Entrepreneur", "Event-driven, news trading"),
        (15, "ESFP", "The Entertainer", "FOMO plays, social momentum"),
    ];

    for (code, name, archetype, desc) in &types {
        println!(
            "  {:>2}  {:<6} {:<20} {}",
            code, name, archetype, desc,
        );
    }
    println!();
}
