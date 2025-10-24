use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

use crate::state::{
    TradingAgent, UserAccount, TradePosition, X402PaymentRecord,
    TradeDirection, PositionStatus,
};
use crate::error::PikkyError;
use crate::utils::*;

/// Execute a new trade based on the user's MBTI strategy.
#[derive(Accounts)]
#[instruction(params: ExecuteTradeParams)]
pub struct ExecuteTrade<'info> {
    #[account(
        mut,
        seeds = [TRADING_AGENT_SEED, trading_agent.authority.as_ref()],
        bump = trading_agent.bump,
    )]
    pub trading_agent: Account<'info, TradingAgent>,

    #[account(
        mut,
        seeds = [USER_ACCOUNT_SEED, trading_agent.key().as_ref(), owner.key().as_ref()],
        bump = user_account.bump,
        has_one = owner @ PikkyError::Unauthorized,
        has_one = trading_agent,
    )]
    pub user_account: Account<'info, UserAccount>,

    #[account(
        init,
        payer = owner,
        space = TradePosition::LEN,
        seeds = [POSITION_SEED, user_account.key().as_ref(), &params.position_id.to_le_bytes()],
        bump,
    )]
    pub position: Account<'info, TradePosition>,

    /// The x402 payment record that authorizes this trade.
    #[account(
        mut,
        seeds = [X402_PAYMENT_SEED, user_account.key().as_ref(), &payment_record.payment_hash],
        bump = payment_record.bump,
        constraint = !payment_record.consumed @ PikkyError::X402PaymentAlreadyUsed,
        constraint = payment_record.user_account == user_account.key() @ PikkyError::X402PaymentInvalid,
    )]
    pub payment_record: Account<'info, X402PaymentRecord>,

    /// The agent's token vault for fee collection.