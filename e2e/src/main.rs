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

    let gov = Keypair::new();
    let gov2 = Keypair::new();
    let owner = Keypair::new();
    let publisher = Keypair::new();
    let challenger = Keypair::new();
    for k in [&gov, &gov2, &owner, &publisher, &challenger] {
        svm.airdrop(&k.pubkey(), 1000 * LAMPORTS_PER_SOL).unwrap();
    }

    // ---------- 0. $WANE SPL mint, gov is mint authority ----------
    let wane_mint = CreateMint::new(&mut svm, &gov).decimals(9).send().unwrap();
    println!("[0] $WANE SPL mint: {}", wane_mint);

    let (cfg, _) = Pubkey::find_program_address(&[b"config"], &reg);
    let stake_vault = get_associated_token_address(&cfg, &wane_mint);
    CreateAssociatedTokenAccount::new(&mut svm, &gov, &wane_mint).owner(&cfg).send().unwrap();
    let pub_ata = CreateAssociatedTokenAccount::new(&mut svm, &publisher, &wane_mint).send().unwrap();
    let chal_ata = CreateAssociatedTokenAccount::new(&mut svm, &challenger, &wane_mint).send().unwrap();
    MintTo::new(&mut svm, &gov, &wane_mint, &pub_ata, 1000 * WANE).send().unwrap();
    MintTo::new(&mut svm, &gov, &wane_mint, &chal_ata, 1000 * WANE).send().unwrap();

    // ---------- 1. registry init_config (real mint + stake vault) ----------
    let mut data = disc("init_config").to_vec();
    data.extend_from_slice(gov.pubkey().as_ref());
    data.extend_from_slice(&(100 * WANE).to_le_bytes());
    data.extend_from_slice(&(200 * WANE).to_le_bytes());
    data.extend_from_slice(&259200i64.to_le_bytes());
    data.extend_from_slice(&3600i64.to_le_bytes());
    data.extend_from_slice(&2u32.to_le_bytes());
    send(&mut svm, Instruction {
        program_id: reg,
        accounts: vec![
            AccountMeta::new(gov.pubkey(), true),
            AccountMeta::new(cfg, false),
            AccountMeta::new_readonly(wane_mint, false),
            AccountMeta::new_readonly(stake_vault, false),
            AccountMeta::new_readonly(system_program::ID, false),
        ],
        data,
    }, &gov).expect("init_config");
    println!("[1] registry init_config OK (real $WANE stake vault)");

    // ---------- 2. genesis antibody for a drainer (kind 0) ----------
    let drainer = Pubkey::new_unique();
    let subject = drainer.to_bytes();
    let antibody_bad = antibody_pda(&reg, KIND_ADDRESS, &subject);
    let mut data = disc("seed_genesis").to_vec();
    data.push(KIND_ADDRESS);
    data.extend_from_slice(&subject);
    send(&mut svm, Instruction {
        program_id: reg,
        accounts: vec![
            AccountMeta::new(gov.pubkey(), true),
            AccountMeta::new(cfg, false),
            AccountMeta::new(antibody_bad, false),
            AccountMeta::new_readonly(system_program::ID, false),
        ],
        data,
    }, &gov).expect("seed_genesis");
    println!("[2] genesis antibody seeded (drainer, kind 0)");

    // ---------- 3. STAKED mint_antibody (publisher stakes 100 WANE) ----------
    let badguy = Pubkey::new_unique();
    let subj2 = badguy.to_bytes();
    let antibody_staked = antibody_pda(&reg, KIND_ADDRESS, &subj2);
    let bal_before = token_bal(&svm, &pub_ata);
    let mut data = disc("mint_antibody").to_vec();
    data.push(KIND_ADDRESS);
    data.extend_from_slice(&subj2);
    data.extend_from_slice(&[0u8; 32]);
    send(&mut svm, Instruction {
        program_id: reg,
        accounts: vec![
            AccountMeta::new(publisher.pubkey(), true),
            AccountMeta::new(cfg, false),
            AccountMeta::new(antibody_staked, false),
            AccountMeta::new(pub_ata, false),
            AccountMeta::new(stake_vault, false),
            AccountMeta::new_readonly(spl_token::ID, false),
            AccountMeta::new_readonly(system_program::ID, false),
        ],
        data,
    }, &publisher).expect("mint_antibody");
    check!(bal_before - token_bal(&svm, &pub_ata) == 100 * WANE, "publisher stakes 100 WANE");
    check!(token_bal(&svm, &stake_vault) == 100 * WANE, "vault holds 100 WANE");
    println!("[3] STAKED mint_antibody OK");

    // ---------- 4. challenge (200 WANE bond) ----------
    send(&mut svm, Instruction {
        program_id: reg,
        accounts: vec![
            AccountMeta::new(challenger.pubkey(), true),
            AccountMeta::new(cfg, false),
            AccountMeta::new(antibody_staked, false),
            AccountMeta::new(chal_ata, false),
            AccountMeta::new(stake_vault, false),
            AccountMeta::new_readonly(spl_token::ID, false),
        ],
        data: disc("challenge").to_vec(),
    }, &challenger).expect("challenge");
    check!(token_bal(&svm, &stake_vault) == 300 * WANE, "vault=300");
    println!("[4] challenge OK (vault=300)");
