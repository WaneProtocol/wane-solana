// Wane Solana e2e (bankrun). Loads both compiled programs and exercises:
// registry init -> seed genesis antibody -> vault enroll -> deposit ->
// CLEAN send PASSES -> FLAGGED send BLOCKED (reverts, no value moves).
//
// run: npx tsx tests/e2e.ts   (after `anchor build`)

import { start } from "solana-bankrun";
import {
  PublicKey,
  Keypair,
  SystemProgram,
  Transaction,
  TransactionInstruction,
  LAMPORTS_PER_SOL,
} from "@solana/web3.js";
import { createHash } from "crypto";
import { readFileSync } from "fs";

const REGISTRY_ID = new PublicKey("5Arj4zbFs5GigEGUSUb9hKNMYaPLqv1XgJXUcnGJ1wJH");
const VAULT_ID = new PublicKey("5YK7gMzkjUvLaxfNisMdtjRK4UeAiJBCSonB3GgrtTYh");

function disc(name: string): Buffer {
  return createHash("sha256").update(`global:${name}`).digest().subarray(0, 8);
}
const u64 = (n: bigint | number) => {
  const b = Buffer.alloc(8);
  b.writeBigUInt64LE(BigInt(n));
  return b;
};
const i64 = (n: bigint | number) => {
  const b = Buffer.alloc(8);
  b.writeBigInt64LE(BigInt(n));
  return b;
};
const u32 = (n: number) => {
  const b = Buffer.alloc(4);
  b.writeUInt32LE(n);
  return b;
};
