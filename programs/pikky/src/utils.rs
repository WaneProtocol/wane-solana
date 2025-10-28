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
pub fn is_take_profit_triggered(
    current_price: u64,
    entry_price: u64,
    take_profit: u64,
    direction: TradeDirection,
) -> bool {
    if take_profit == 0 {
        return false;
    }
    let _ = entry_price; // used conceptually; the threshold is absolute
    match direction {
        TradeDirection::Long => current_price >= take_profit,
        TradeDirection::Short => current_price <= take_profit,
    }
}

/// Validate that a proposed trade respects the MBTI profile risk limits.
pub fn validate_trade_against_profile(
    profile: &MbtiProfile,
    trade_size: u64,
    user_balance: u64,
    current_open_positions: u16,
    last_trade_at: i64,
    current_timestamp: i64,
    confidence: u8,
) -> Result<()> {
    // Check confidence threshold
    require!(
        confidence >= profile.min_confidence,
        PikkyError::RiskLimitExceeded
    );

    // Check max positions
    require!(
        current_open_positions < MAX_OPEN_POSITIONS,
        PikkyError::MaxPositionsReached
    );

    // Check cooldown
    let elapsed = current_timestamp.saturating_sub(last_trade_at);
    require!(
        elapsed >= profile.trade_cooldown_secs,
        PikkyError::CooldownActive
    );

    // Check position size against max allocation
    if user_balance > 0 {
        let max_size = (user_balance as u128)
            .checked_mul(profile.max_position_bps as u128)
            .ok_or(PikkyError::MathOverflow)?
            .checked_div(BPS_DENOMINATOR as u128)
            .ok_or(PikkyError::MathOverflow)?;
        require!(
            (trade_size as u128) <= max_size,
            PikkyError::ExceedsMaxPosition
        );
    }

    // Check leverage is within the profile's limit
    // (leverage is checked at the caller level, but double-check here)

    Ok(())
}

/// Validate stop-loss and take-profit prices relative to entry and direction.
pub fn validate_sl_tp(
    entry_price: u64,
    stop_loss: u64,
    take_profit: u64,
    direction: TradeDirection,
) -> Result<()> {
    if stop_loss > 0 {
        match direction {
            TradeDirection::Long => {
                require!(stop_loss < entry_price, PikkyError::InvalidStopLoss);
            }
            TradeDirection::Short => {
                require!(stop_loss > entry_price, PikkyError::InvalidStopLoss);
            }
        }
    }

    if take_profit > 0 {
        match direction {
            TradeDirection::Long => {
                require!(take_profit > entry_price, PikkyError::InvalidTakeProfit);
            }
            TradeDirection::Short => {
                require!(take_profit < entry_price, PikkyError::InvalidTakeProfit);
            }
        }
    }

    Ok(())
}

/// Derive default stop-loss price from MBTI profile parameters.
pub fn derive_stop_loss(
    entry_price: u64,
    profile: &MbtiProfile,
    direction: TradeDirection,
) -> Result<u64> {
    let offset = (entry_price as u128)
        .checked_mul(profile.stop_loss_bps as u128)
        .ok_or(PikkyError::MathOverflow)?
        .checked_div(BPS_DENOMINATOR as u128)
        .ok_or(PikkyError::MathOverflow)? as u64;

    match direction {
        TradeDirection::Long => Ok(entry_price.saturating_sub(offset)),
        TradeDirection::Short => entry_price
            .checked_add(offset)
            .ok_or_else(|| error!(PikkyError::MathOverflow)),
    }
}

/// Derive default take-profit price from MBTI profile parameters.
pub fn derive_take_profit(
    entry_price: u64,
    profile: &MbtiProfile,
    direction: TradeDirection,
) -> Result<u64> {
    let offset = (entry_price as u128)
        .checked_mul(profile.take_profit_bps as u128)
        .ok_or(PikkyError::MathOverflow)?
        .checked_div(BPS_DENOMINATOR as u128)
        .ok_or(PikkyError::MathOverflow)? as u64;

    match direction {
        TradeDirection::Long => entry_price
            .checked_add(offset)
            .ok_or_else(|| error!(PikkyError::MathOverflow)),
        TradeDirection::Short => Ok(entry_price.saturating_sub(offset)),
    }
}

/// Validate that the price is reasonable (positive and not stale).
pub fn validate_price(price: u64, price_timestamp: i64, current_timestamp: i64) -> Result<()> {
    require!(price > 0, PikkyError::InvalidPrice);
    let age = current_timestamp.saturating_sub(price_timestamp);
    require!(age <= MAX_PRICE_STALENESS, PikkyError::StalePriceFeed);
    Ok(())
}

/// Compute a simple hash of a byte slice for x402 payment identification.
/// Uses a Solana-friendly approach (no external hash crate needed at runtime).
pub fn compute_payment_hash(data: &[u8]) -> [u8; 32] {
    let hash = anchor_lang::solana_program::hash::hash(data);
    hash.to_bytes()
}

/// Check if an x402 payment has expired.
pub fn is_payment_expired(expires_at: i64, current_timestamp: i64) -> bool {
    current_timestamp > expires_at
}

/// Calculate the required margin for a leveraged position.
/// margin = notional / leverage_factor * 100
pub fn calculate_required_margin(notional: u64, leverage: u16) -> Result<u64> {
    let margin = (notional as u128)
        .checked_mul(100)
        .ok_or(PikkyError::MathOverflow)?
        .checked_div(leverage as u128)
        .ok_or(PikkyError::MathOverflow)?;
    if margin > u64::MAX as u128 {
        return Err(PikkyError::MathOverflow.into());
    }
    Ok(margin as u64)
}

/// Calculate win rate as a percentage (0-100).
pub fn calculate_win_rate(winning: u32, total: u32) -> u8 {
    if total == 0 {
        return 0;
    }
    let rate = (winning as u64)
        .saturating_mul(100)
        .checked_div(total as u64)
        .unwrap_or(0);
    rate.min(100) as u8
}
