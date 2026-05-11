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

function assert(cond: boolean, msg: string) {
  if (!cond) {
    console.error("ASSERT FAILED:", msg);
    process.exit(1);
  }
}

async function main() {
  const ctx = await start(
    [
      { name: "wane_registry", programId: REGISTRY_ID },
      { name: "wane_vault", programId: VAULT_ID },
    ],
    [],
  );
  const client = ctx.banksClient;
  const gov = ctx.payer;

  const owner = Keypair.generate();
  // fund owner from gov
  await sendTx(
    client,
    [SystemProgram.transfer({ fromPubkey: gov.publicKey, toPubkey: owner.publicKey, lamports: 50 * LAMPORTS_PER_SOL })],
    gov,
    [gov],
  );

  // ---------- 1. registry init_config ----------
  const [cfg] = PublicKey.findProgramAddressSync([Buffer.from("config")], REGISTRY_ID);
  const fakeMint = Keypair.generate().publicKey;
  const fakeVault = Keypair.generate().publicKey;
  const initData = Buffer.concat([
    disc("init_config"),
    gov.publicKey.toBuffer(), // treasury
    u64(100), // mint_stake
    u64(200), // challenge_stake
    i64(259200), // maturity
    i64(3600), // enforce_window
    u32(2), // enforce_corrobs
  ]);
  await sendTx(
    client,
    [
      new TransactionInstruction({
        programId: REGISTRY_ID,
        keys: [
          { pubkey: gov.publicKey, isSigner: true, isWritable: true },
          { pubkey: cfg, isSigner: false, isWritable: true },
          { pubkey: fakeMint, isSigner: false, isWritable: false },
          { pubkey: fakeVault, isSigner: false, isWritable: false },
          { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
        ],
        data: initData,
      }),
    ],
    gov,
    [gov],
  );
  console.log("[1] registry init_config OK");

  // ---------- 2. seed genesis antibody for a known-bad destination ----------
  const drainer = Keypair.generate().publicKey;
  const kind = 1; // Address
  const subject = drainer.toBuffer(); // 32 bytes
  const [antibodyBad] = PublicKey.findProgramAddressSync(
    [Buffer.from("antibody"), Buffer.from([kind]), subject],
    REGISTRY_ID,
  );
  const seedData = Buffer.concat([disc("seed_genesis"), Buffer.from([kind]), subject]);
  await sendTx(
    client,
    [
      new TransactionInstruction({
        programId: REGISTRY_ID,
        keys: [
          { pubkey: gov.publicKey, isSigner: true, isWritable: true },
          { pubkey: cfg, isSigner: false, isWritable: true },
          { pubkey: antibodyBad, isSigner: false, isWritable: true },
          { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
        ],
        data: seedData,
      }),
    ],
    gov,
    [gov],
  );
  console.log(`[2] genesis antibody seeded for drainer ${drainer.toBase58()}`);

  // ---------- 3. vault enroll ----------
  const [policy] = PublicKey.findProgramAddressSync(
    [Buffer.from("policy"), owner.publicKey.toBuffer()],
    VAULT_ID,
  );
  const [vault] = PublicKey.findProgramAddressSync(
    [Buffer.from("vault"), owner.publicKey.toBuffer()],
    VAULT_ID,
  );
  const enrollData = Buffer.concat([
    disc("enroll"),
    Buffer.from([1]), // block_kinds K_ADDRESS
    u32(0), // min_corrobs
    u64(5 * LAMPORTS_PER_SOL), // per_tx_cap
    u64(0), // daily_cap
    i64(0), // expires_at
  ]);
  await sendTx(
    client,
    [
      new TransactionInstruction({
        programId: VAULT_ID,
        keys: [
          { pubkey: owner.publicKey, isSigner: true, isWritable: true },
          { pubkey: policy, isSigner: false, isWritable: true },
          { pubkey: vault, isSigner: false, isWritable: true },
          { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
        ],
        data: enrollData,
      }),
    ],
    owner,
    [owner],
  );
  console.log("[3] vault enroll OK");

  // ---------- 4. deposit 10 SOL ----------
  const depData = Buffer.concat([disc("deposit"), u64(10 * LAMPORTS_PER_SOL)]);
  await sendTx(
    client,
    [
      new TransactionInstruction({
        programId: VAULT_ID,
        keys: [
          { pubkey: owner.publicKey, isSigner: true, isWritable: true },
          { pubkey: vault, isSigner: false, isWritable: true },
          { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
        ],
        data: depData,
      }),
    ],
    owner,
    [owner],
  );
  const vbal = await client.getBalance(vault);
  console.log(`[4] deposit OK, vault balance = ${Number(vbal) / LAMPORTS_PER_SOL} SOL`);

  // ---------- 5. CLEAN send -> PASS ----------
  const cleanDest = Keypair.generate().publicKey;
  const amt = 1 * LAMPORTS_PER_SOL;
  const rClean = await tryExecute(client, owner, policy, vault, cleanDest, cfg, null, amt);
  assert(rClean.ok, `clean send must pass: ${rClean.err}`);
  const cleanBal = await client.getBalance(cleanDest);
  assert(Number(cleanBal) === amt, `clean dest must receive ${amt}, got ${cleanBal}`);
  console.log(`[5] CLEAN send PASSED, dest received ${Number(cleanBal) / LAMPORTS_PER_SOL} SOL`);

  // ---------- 6. FLAGGED send -> BLOCK ----------
  const before = await client.getBalance(drainer).catch(() => 0n);
  const rFlag = await tryExecute(client, owner, policy, vault, drainer, cfg, antibodyBad, amt);
  assert(!rFlag.ok, "flagged send MUST be blocked but it passed");
  const after = await client.getBalance(drainer).catch(() => 0n);
  assert(Number(before) === Number(after), "no value may move to a flagged target");
  console.log(`[6] FLAGGED send BLOCKED (drainer balance unchanged). reason: ${rFlag.err}`);
