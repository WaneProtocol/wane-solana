use anchor_lang::prelude::*;

pub mod error;
pub mod instructions;
pub mod state;
pub mod utils;

use instructions::*;

declare_id!("PiKKYagent1111111111111111111111111111111111");

#[program]
pub mod pikky {
    use super::*;

    /// Initialize a new PIKKY trading agent with the given configuration.
    pub fn initialize_agent(
        ctx: Context<InitializeAgent>,
        params: InitializeAgentParams,
    ) -> Result<()> {
        instructions::initialize::handler_initialize_agent(ctx, params)
    }

    /// Create a new user account under the trading agent.
    pub fn initialize_user(ctx: Context<InitializeUser>) -> Result<()> {
        instructions::initialize::handler_initialize_user(ctx)
    }

    /// Pause or unpause the trading agent (authority only).
    pub fn toggle_pause(ctx: Context<TogglePause>) -> Result<()> {
        instructions::initialize::handler_toggle_pause(ctx)
    }

    /// Deposit quote tokens into the user's trading balance.
    pub fn deposit(ctx: Context<Deposit>, params: DepositParams) -> Result<()> {
        instructions::deposit::handler_deposit(ctx, params)
    }

    /// Make an x402 payment to authorize trading operations.
    pub fn x402_deposit(ctx: Context<X402Deposit>, params: X402DepositParams) -> Result<()> {
        instructions::deposit::handler_x402_deposit(ctx, params)
    }

    /// Execute a trade based on the user's MBTI-derived strategy.
    pub fn execute_trade(
        ctx: Context<ExecuteTrade>,
        params: ExecuteTradeParams,
    ) -> Result<()> {
        instructions::execute_trade::handler_execute_trade(ctx, params)
    }

    /// Close an existing open position at the given exit price.
    pub fn close_position(
        ctx: Context<ClosePosition>,
        params: ClosePositionParams,
    ) -> Result<()> {
        instructions::execute_trade::handler_close_position(ctx, params)
    }

    /// Withdraw funds from the user's trading balance.
    pub fn withdraw(ctx: Context<Withdraw>, params: WithdrawParams) -> Result<()> {
        instructions::withdraw::handler_withdraw(ctx, params)
    }

    /// Emergency withdrawal by agent authority.
    pub fn emergency_withdraw(ctx: Context<EmergencyWithdraw>) -> Result<()> {
        instructions::withdraw::handler_emergency_withdraw(ctx)
    }

    /// Set or update the user's MBTI trading strategy.
    pub fn set_strategy(ctx: Context<SetStrategy>, params: SetStrategyParams) -> Result<()> {
        instructions::set_strategy::handler_set_strategy(ctx, params)
    }

    /// Update the agent's fee configuration (authority only).
    pub fn update_fees(ctx: Context<UpdateFees>, params: UpdateFeesParams) -> Result<()> {
        instructions::set_strategy::handler_update_fees(ctx, params)
    }
}

