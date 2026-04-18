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

fn disc(name: &str) -> [u8; 8] {
    let h = hash(format!("global:{name}").as_bytes());
    let mut d = [0u8; 8];
    d.copy_from_slice(&h.to_bytes()[..8]);
    d
}

macro_rules! check {
    ($cond:expr, $msg:expr) => {
        if !$cond {
            eprintln!("FAIL: {}", $msg);
            std::process::exit(1);
        }
    };
}

fn main() {
    let mut svm = LiteSVM::new();
    let reg = Pubkey::from_str(REGISTRY_ID).unwrap();
    let vault_pid = Pubkey::from_str(VAULT_ID).unwrap();
    // litesvm 0.6 (solana 2.2 runtime) cannot load v3 sBPF, so the e2e runs a v0
    // build of the SAME source from target/sbf-test. Execution semantics are
    // identical across sBPF versions; only the on-chain deploy gate differs.
    svm.add_program(reg, &std::fs::read("../target/sbf-test/wane_registry.so").unwrap());
    svm.add_program(vault_pid, &std::fs::read("../target/sbf-test/wane_vault.so").unwrap());
