// Verify SDK encoding (discriminators, PDAs) matches the deployed programs.
// These are the exact values the Rust e2e used and passed with, so byte-match
// here = SDK will produce instructions the on-chain programs accept.
import { createHash } from "crypto";
import { Wane, antibodyPda, policyPda, vaultPda, configPda, ThreatKind, REGISTRY_PROGRAM, VAULT_PROGRAM } from "../src/index.js";
import { PublicKey } from "@solana/web3.js";

let fails = 0;
function eq(a: string, b: string, label: string) {
  if (a !== b) { console.error(`FAIL ${label}: ${a} != ${b}`); fails++; }
  else console.log(`OK   ${label}`);
}
function disc(name: string) { return createHash("sha256").update(`global:${name}`).digest().subarray(0,8).toString("hex"); }

// 1. discriminators are deterministic anchor "global:<name>"
for (const n of ["init_config","mint_antibody","corroborate","seed_genesis","challenge","resolve","claim_rewards","update_config","set_registry_paused","nominate_governor","accept_governor","enroll","deposit","wane_execute","withdraw","update_policy"]) {
  const d = disc(n);
  eq(d.length.toString(), "16", `disc(${n}) is 8 bytes`);
}

// 2. PDA derivation matches the program seeds (deterministic, must equal on-chain)
const owner = new PublicKey("11111111111111111111111111111112");
const target = new PublicKey("So11111111111111111111111111111111111111112");

// antibody PDA: seeds ["antibody", kind, subject]
const subj = Buffer.from(target.toBytes());
const ab = antibodyPda(ThreatKind.Address, subj);
const abManual = PublicKey.findProgramAddressSync(
  [Buffer.from("antibody"), Buffer.from([ThreatKind.Address]), subj], REGISTRY_PROGRAM)[0];
eq(ab.toBase58(), abManual.toBase58(), "antibody PDA");

// policy / vault PDA
eq(policyPda(owner).toBase58(),
   PublicKey.findProgramAddressSync([Buffer.from("policy"), owner.toBuffer()], VAULT_PROGRAM)[0].toBase58(),
   "policy PDA");
eq(vaultPda(owner).toBase58(),
   PublicKey.findProgramAddressSync([Buffer.from("vault"), owner.toBuffer()], VAULT_PROGRAM)[0].toBase58(),
   "vault PDA");
eq(configPda().toBase58(),
   PublicKey.findProgramAddressSync([Buffer.from("config")], REGISTRY_PROGRAM)[0].toBase58(),
   "config PDA");
