// Wane Solana FULL e2e (litesvm, run under WSL/Linux).
// Covers the hardened programs end to end on a real SBF runtime:
//   $WANE mint, registry init w/ real stake vault, genesis seed, staked
//   mint_antibody, corroborate, challenge -> resolve(slash), claim,
//   vault enroll/deposit, CLEAN send PASS, FLAGGED send BLOCK, per-tx cap BLOCK,
//   BYPASS attempt (wrong antibody account) MUST FAIL, update_policy, withdraw,
//   update_config, 2-step governor transfer, registry pause.
// run: cargo run

use anchor_lang::solana_program::hash::hash;
use litesvm::LiteSVM;
use litesvm_token::{CreateAssociatedTokenAccount, CreateMint, MintTo};
use solana_sdk::{
    instruction::{AccountMeta, Instruction},
    native_token::LAMPORTS_PER_SOL,
    pubkey::Pubkey,
    signature::{Keypair, Signer},
    system_program,
    transaction::Transaction,
};
use spl_associated_token_account::get_associated_token_address;
use std::str::FromStr;

const REGISTRY_ID: &str = "5Arj4zbFs5GigEGUSUb9hKNMYaPLqv1XgJXUcnGJ1wJH";
const VAULT_ID: &str = "5YK7gMzkjUvLaxfNisMdtjRK4UeAiJBCSonB3GgrtTYh";
const WANE: u64 = 1_000_000_000; // 9 decimals, 1 WANE
const KIND_ADDRESS: u8 = 0; // ThreatKind.Address (matches SDK + vault binding)
