use anchor_lang::prelude::*;
use crate::error::PikkyError;
use crate::state::{MbtiProfile, TradeDirection};

/// Price precision multiplier (1e6) for fixed-point arithmetic.
pub const PRICE_PRECISION: u64 = 1_000_000;

/// Basis points denominator.
pub const BPS_DENOMINATOR: u64 = 10_000;

/// Maximum leverage allowed (5x = 500).
pub const MAX_LEVERAGE: u16 = 500;

/// Minimum trade size in quote token base units (0.01 USDC with 6 decimals).
pub const MIN_TRADE_SIZE: u64 = 10_000;

/// Maximum number of concurrent open positions per user.
pub const MAX_OPEN_POSITIONS: u16 = 20;

/// Maximum staleness for price feed in seconds.
pub const MAX_PRICE_STALENESS: i64 = 120;

/// Seeds for PDA derivation.
pub const TRADING_AGENT_SEED: &[u8] = b"trading_agent";
pub const USER_ACCOUNT_SEED: &[u8] = b"user_account";
pub const POSITION_SEED: &[u8] = b"position";
pub const X402_PAYMENT_SEED: &[u8] = b"x402_payment";
pub const VAULT_SEED: &[u8] = b"vault";

/// Calculate the notional value of a position given size and price.
/// Returns the value in quote token units.
///
/// notional = (size * price) / PRICE_PRECISION
pub fn calculate_notional(size: u64, price: u64) -> Result<u64> {
    let product = (size as u128)
        .checked_mul(price as u128)
        .ok_or(PikkyError::MathOverflow)?;
    let notional = product
        .checked_div(PRICE_PRECISION as u128)
        .ok_or(PikkyError::MathOverflow)?;
    if notional > u64::MAX as u128 {
        return Err(PikkyError::MathOverflow.into());
    }
    Ok(notional as u64)
}

/// Calculate the leveraged notional value.
/// leverage_factor is in units of 100 (100 = 1x, 200 = 2x, etc.)
pub fn calculate_leveraged_notional(size: u64, price: u64, leverage: u16) -> Result<u64> {
    let base_notional = calculate_notional(size, price)?;
    let leveraged = (base_notional as u128)
        .checked_mul(leverage as u128)
        .ok_or(PikkyError::MathOverflow)?
        .checked_div(100)
        .ok_or(PikkyError::MathOverflow)?;
    if leveraged > u64::MAX as u128 {
        return Err(PikkyError::MathOverflow.into());
    }
    Ok(leveraged as u64)
}

/// Calculate PnL for a position given entry and exit prices.
/// Returns signed PnL in quote token units.
pub fn calculate_pnl(
    size: u64,
    entry_price: u64,
    exit_price: u64,
    leverage: u16,
    direction: TradeDirection,
) -> Result<i64> {
    let entry_notional = calculate_notional(size, entry_price)?;
    let exit_notional = calculate_notional(size, exit_price)?;

    let raw_pnl: i64 = match direction {
        TradeDirection::Long => {
            (exit_notional as i64)
                .checked_sub(entry_notional as i64)
                .ok_or(PikkyError::MathOverflow)?
        }
        TradeDirection::Short => {
            (entry_notional as i64)
                .checked_sub(exit_notional as i64)
                .ok_or(PikkyError::MathOverflow)?
        }
    };

    // Apply leverage to PnL
    let leveraged_pnl = (raw_pnl as i128)
        .checked_mul(leverage as i128)
        .ok_or(PikkyError::MathOverflow)?
        .checked_div(100)
        .ok_or(PikkyError::MathOverflow)?;

    if leveraged_pnl > i64::MAX as i128 || leveraged_pnl < i64::MIN as i128 {
        return Err(PikkyError::MathOverflow.into());
    }
    Ok(leveraged_pnl as i64)
}

/// Calculate protocol fee from a trade's notional value.
pub fn calculate_fee(notional: u64, fee_bps: u16) -> Result<u64> {
    let fee = (notional as u128)
        .checked_mul(fee_bps as u128)
        .ok_or(PikkyError::MathOverflow)?
        .checked_div(BPS_DENOMINATOR as u128)
        .ok_or(PikkyError::MathOverflow)?;
    Ok(fee as u64)
}

/// Check whether a position's stop-loss has been triggered.
pub fn is_stop_loss_triggered(
    current_price: u64,
    entry_price: u64,
    stop_loss: u64,
    direction: TradeDirection,
) -> bool {
    if stop_loss == 0 {
        return false;
    }
    match direction {
        TradeDirection::Long => current_price <= stop_loss,
        TradeDirection::Short => current_price >= stop_loss,
    }
}

/// Check whether a position's take-profit has been triggered.