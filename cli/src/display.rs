use colored::*;
use comfy_table::{Table, ContentArrangement, Cell, Attribute, Color as TColor};

/// Print the PIKKY ASCII banner.
pub fn print_banner() {
    let banner = r#"
 ____  ___ _  ___  ____   __
|  _ \|_ _| |/ / |/ /\ \ / /
| |_) || || ' /| ' /  \ V /
|  __/ | || . \| . \   | |
|_|   |___|_|\_\_|\_\  |_|
    x402 AI Trading Agent
"#;
    println!("{}", banner.green().bold());
}

/// Print a section header.
pub fn print_header(text: &str) {
    println!();
    println!("{}", "=".repeat(60).green());
    println!("  {}", text.white().bold());
    println!("{}", "=".repeat(60).green());
}

/// Print a success message.
pub fn print_success(msg: &str) {
    println!("{} {}", "[OK]".green().bold(), msg);
}

/// Print an error message.
pub fn print_error(msg: &str) {
    println!("{} {}", "[ERR]".red().bold(), msg);
}

/// Print a warning message.
pub fn print_warning(msg: &str) {
    println!("{} {}", "[WARN]".yellow().bold(), msg);
}

/// Print an info message.
pub fn print_info(msg: &str) {
    println!("{} {}", "[INFO]".cyan().bold(), msg);
}

/// Print a key-value pair with aligned formatting.
pub fn print_kv(key: &str, value: &str) {
    println!("  {:<24} {}", format!("{}:", key).dimmed(), value.white());
}

/// Print a key-value pair where the value is colored based on sign.
pub fn print_kv_pnl(key: &str, value: i64, decimals: u8) {
    let divisor = 10u64.pow(decimals as u32) as f64;
    let formatted = value as f64 / divisor;
    let color_val = if value > 0 {
        format!("+{:.2}", formatted).green()
    } else if value < 0 {
        format!("{:.2}", formatted).red()
    } else {
        format!("{:.2}", formatted).white()
    };
    println!("  {:<24} {}", format!("{}:", key).dimmed(), color_val);
}

/// Format a token amount with the given number of decimals.
pub fn format_amount(amount: u64, decimals: u8) -> String {
    let divisor = 10u64.pow(decimals as u32) as f64;
    format!("{:.2}", amount as f64 / divisor)
}

/// Format a price (scaled by 1e6).
pub fn format_price(price: u64) -> String {
    format!("${:.6}", price as f64 / 1_000_000.0)
}

/// Format a unix timestamp to a human-readable date.
pub fn format_timestamp(ts: i64) -> String {
    if ts == 0 {
        return "N/A".to_string();
    }
    chrono::DateTime::from_timestamp(ts, 0)
        .map(|dt| dt.format("%Y-%m-%d %H:%M:%S UTC").to_string())
        .unwrap_or_else(|| "Invalid".to_string())
}

/// Format a leverage value (100 = 1x).
pub fn format_leverage(leverage: u16) -> String {
    format!("{:.1}x", leverage as f64 / 100.0)
}

/// Display the agent status table.
pub fn display_agent_status(
    authority: &str,
    quote_mint: &str,
    fee_bps: u16,
    paused: bool,
    total_deposits: u64,
    total_withdrawals: u64,
    total_trades: u64,
    total_fees: u64,
    created_at: i64,
    last_activity: i64,
) {
    print_header("PIKKY Trading Agent Status");

    let status_str = if paused {
        "PAUSED".red().bold().to_string()
    } else {
        "ACTIVE".green().bold().to_string()
    };

    print_kv("Status", &status_str);
    print_kv("Authority", authority);
    print_kv("Quote Mint", quote_mint);
    print_kv("Fee", &format!("{} bps ({:.2}%)", fee_bps, fee_bps as f64 / 100.0));
    print_kv("Total Deposits", &format_amount(total_deposits, 6));
    print_kv("Total Withdrawals", &format_amount(total_withdrawals, 6));
    print_kv("Total Trades", &total_trades.to_string());
    print_kv("Fees Collected", &format_amount(total_fees, 6));
    print_kv("Created", &format_timestamp(created_at));
    print_kv("Last Activity", &format_timestamp(last_activity));
    println!();
}

/// Display user account info and PnL summary.
pub fn display_user_status(
    owner: &str,
    balance: u64,
    realized_pnl: i64,
    open_positions: u16,
    total_trades: u32,
    winning_trades: u32,
    mbti_name: &str,
    strategy_configured: bool,
    last_trade_at: i64,
    x402_payments: u64,
) {
    print_header("User Account Status");

    let win_rate = if total_trades > 0 {
        format!(
            "{:.1}% ({}/{})",
            winning_trades as f64 / total_trades as f64 * 100.0,
            winning_trades,
            total_trades,
        )
    } else {
        "N/A".to_string()
    };

    print_kv("Owner", owner);
    print_kv("Balance", &format!("{} USDC", format_amount(balance, 6)));
    print_kv_pnl("Realized PnL", realized_pnl, 6);
    print_kv("Open Positions", &open_positions.to_string());
    print_kv("Win Rate", &win_rate);
    print_kv(
        "Strategy",
        &if strategy_configured {
            format!("{} (active)", mbti_name).green().to_string()
        } else {
            "Not configured".yellow().to_string()
        },
    );
    print_kv("Last Trade", &format_timestamp(last_trade_at));
    print_kv("x402 Payments", &format_amount(x402_payments, 6));
    println!();
}

/// Display a table of open positions.
pub fn display_positions_table(
    positions: &[(u64, &str, &str, u64, u64, u16, u64, u64, i64, &str)],
) {
    print_header("Open Positions");

    if positions.is_empty() {
        print_info("No open positions.");
        return;
    }

    let mut table = Table::new();
    table.set_content_arrangement(ContentArrangement::Dynamic);
    table.set_header(vec![
        Cell::new("ID").add_attribute(Attribute::Bold).fg(TColor::Green),
        Cell::new("Direction").add_attribute(Attribute::Bold).fg(TColor::Green),
        Cell::new("Asset").add_attribute(Attribute::Bold).fg(TColor::Green),
        Cell::new("Size").add_attribute(Attribute::Bold).fg(TColor::Green),
        Cell::new("Entry").add_attribute(Attribute::Bold).fg(TColor::Green),
        Cell::new("Leverage").add_attribute(Attribute::Bold).fg(TColor::Green),
        Cell::new("SL").add_attribute(Attribute::Bold).fg(TColor::Green),
        Cell::new("TP").add_attribute(Attribute::Bold).fg(TColor::Green),
        Cell::new("Opened").add_attribute(Attribute::Bold).fg(TColor::Green),
        Cell::new("MBTI").add_attribute(Attribute::Bold).fg(TColor::Green),
    ]);

    for (id, direction, asset, size, entry, leverage, sl, tp, opened, mbti) in positions {
        table.add_row(vec![
            Cell::new(id.to_string()),
            Cell::new(*direction),
            Cell::new(*asset),
            Cell::new(format_amount(*size, 6)),
            Cell::new(format_price(*entry)),
            Cell::new(format_leverage(*leverage)),
            Cell::new(format_price(*sl)),
            Cell::new(format_price(*tp)),
            Cell::new(format_timestamp(*opened)),
            Cell::new(*mbti),
        ]);
    }

    println!("{table}");
    println!();
}

/// Display the MBTI strategy profile details.
pub fn display_strategy(
    mbti_name: &str,
    max_position_bps: u16,
    max_drawdown_bps: u16,
    cooldown_secs: i64,
    leverage: u16,
    slippage_bps: u16,
    trend_following: bool,
    min_confidence: u8,
    take_profit_bps: u16,
    stop_loss_bps: u16,
) {
    print_header(&format!("MBTI Strategy: {}", mbti_name));

    let style = if trend_following {
        "Trend Following"
    } else {
        "Mean Reversion"
    };

    print_kv("Style", style);
    print_kv(
        "Max Position Size",
        &format!("{}% of portfolio", max_position_bps as f64 / 100.0),
    );
    print_kv(
        "Max Drawdown",
        &format!("{}%", max_drawdown_bps as f64 / 100.0),
    );
    print_kv("Trade Cooldown", &format_cooldown(cooldown_secs));
    print_kv("Leverage", &format_leverage(leverage));
    print_kv(
        "Slippage Tolerance",
        &format!("{}%", slippage_bps as f64 / 100.0),
    );
    print_kv("Min Confidence", &format!("{}%", min_confidence));
    print_kv(
        "Take Profit",
        &format!("{}% from entry", take_profit_bps as f64 / 100.0),
    );
    print_kv(
        "Stop Loss",
        &format!("{}% from entry", stop_loss_bps as f64 / 100.0),
    );
    println!();
}

/// Format a cooldown duration in human-readable form.
fn format_cooldown(secs: i64) -> String {
    if secs >= 86400 {
        format!("{}d", secs / 86400)
    } else if secs >= 3600 {
        format!("{}h", secs / 3600)
    } else if secs >= 60 {
        format!("{}m", secs / 60)
    } else {
        format!("{}s", secs)
    }
}

/// Display a trade execution confirmation.
pub fn display_trade_confirmation(
    position_id: u64,
    direction: &str,
    size: u64,
    price: u64,
    leverage: u16,
    stop_loss: u64,
    take_profit: u64,
    fee: u64,
    mbti: &str,
    confidence: u8,
    tx_signature: &str,
) {
    print_header("Trade Executed");

    print_kv("Position ID", &format!("#{}", position_id));
    print_kv("Direction", direction);
    print_kv("Size", &format!("{} USDC", format_amount(size, 6)));
    print_kv("Entry Price", &format_price(price));
    print_kv("Leverage", &format_leverage(leverage));
    print_kv("Stop Loss", &format_price(stop_loss));
    print_kv("Take Profit", &format_price(take_profit));
    print_kv("Fee", &format!("{} USDC", format_amount(fee, 6)));
    print_kv("Strategy", mbti);
    print_kv("Confidence", &format!("{}%", confidence));
    print_kv("Transaction", tx_signature);
    println!();
}

/// Display deposit/withdraw confirmation.
pub fn display_transfer_confirmation(action: &str, amount: u64, new_balance: u64, tx_sig: &str) {
    print_header(&format!("{} Confirmed", action));
    print_kv("Amount", &format!("{} USDC", format_amount(amount, 6)));
    print_kv("New Balance", &format!("{} USDC", format_amount(new_balance, 6)));
    print_kv("Transaction", tx_sig);
    println!();
}
