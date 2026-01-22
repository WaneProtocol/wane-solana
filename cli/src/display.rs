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