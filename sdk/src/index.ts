// wane-sdk: shared on-chain immune memory for AI agents on Solana.
//
// Two entry points on one antibody registry:
//   1. Bot devs (lightweight): `check(target)` before signing, `report(threat)` on a hit.
//      No custody, no migration, one call. Reading is immunity.
//   2. Personal agents (enforced): a Wane SESSION WALLET (vault) that screens every
//      outflow on-chain and reverts a flagged send before value moves.
//
// Pure @solana/web3.js, no Anchor runtime dependency. Instruction data is the
// 8-byte anchor discriminator + borsh, matching the deployed programs.

import {
  Connection,
  PublicKey,
  Keypair,
  SystemProgram,
  Transaction,
  TransactionInstruction,
  Signer,
} from "@solana/web3.js";
import { createHash } from "crypto";

export const REGISTRY_PROGRAM = new PublicKey("5Arj4zbFs5GigEGUSUb9hKNMYaPLqv1XgJXUcnGJ1wJH");
export const VAULT_PROGRAM = new PublicKey("5YK7gMzkjUvLaxfNisMdtjRK4UeAiJBCSonB3GgrtTYh");
const SPL_TOKEN = new PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA");

export enum ThreatKind {
  Address = 0,
  CallPattern = 1,
  Bytecode = 2,
  Semantic = 3,
}
export enum Status {
  None = 0,
  Active = 1,
  Challenged = 2,
  Revoked = 3,
}

export interface Antibody {
  id: bigint;
  kind: number;
  status: number;
  publisher: PublicKey;
  stake: bigint;
  mintedTs: bigint;
  corroborations: number;
  subject: Uint8Array;
  evidence: Uint8Array;
  challenger: PublicKey;
  challengeBond: bigint;
}

export interface Verdict {
  flagged: boolean;
  antibody: Antibody | null;
}

export class WaneBlockedError extends Error {
  constructor(public target: PublicKey) {
    super(`Wane: ${target.toBase58()} is a flagged threat (antibody)`);
    this.name = "WaneBlockedError";
  }
}

// ---- encoding helpers ----
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

// subject is a 32-byte key. For a Solana address use the raw pubkey bytes.
function subjectOf(target: PublicKey): Buffer {
  return Buffer.from(target.toBytes());
}

export function antibodyPda(kind: ThreatKind, subject: Buffer): PublicKey {
  return PublicKey.findProgramAddressSync(
    [Buffer.from("antibody"), Buffer.from([kind]), subject],
    REGISTRY_PROGRAM,
  )[0];
}
export function configPda(): PublicKey {
  return PublicKey.findProgramAddressSync([Buffer.from("config")], REGISTRY_PROGRAM)[0];
}
export function policyPda(owner: PublicKey): PublicKey {
  return PublicKey.findProgramAddressSync([Buffer.from("policy"), owner.toBuffer()], VAULT_PROGRAM)[0];
}
export function vaultPda(owner: PublicKey): PublicKey {
  return PublicKey.findProgramAddressSync([Buffer.from("vault"), owner.toBuffer()], VAULT_PROGRAM)[0];
}

function parseAntibody(data: Buffer): Antibody {
  let o = 8; // skip discriminator
  const id = data.readBigUInt64LE(o); o += 8;
  const kind = data[o]; o += 1;
  const status = data[o]; o += 1;
  const publisher = new PublicKey(data.subarray(o, o + 32)); o += 32;
  const stake = data.readBigUInt64LE(o); o += 8;
  const mintedTs = data.readBigInt64LE(o); o += 8;
  const corroborations = data.readUInt32LE(o); o += 4;
  const subject = Uint8Array.from(data.subarray(o, o + 32)); o += 32;
  const evidence = Uint8Array.from(data.subarray(o, o + 32)); o += 32;
  const challenger = new PublicKey(data.subarray(o, o + 32)); o += 32;
  const challengeBond = data.readBigUInt64LE(o); o += 8;
  return { id, kind, status, publisher, stake, mintedTs, corroborations, subject, evidence, challenger, challengeBond };
}

/**
 * Wane client. Construct with a Connection; pass a Signer for write calls.
 */
export class Wane {
  constructor(public connection: Connection) {}

  static devnet(): Wane {
    return new Wane(new Connection("https://api.devnet.solana.com", "confirmed"));
  }
  static mainnet(): Wane {
    return new Wane(new Connection("https://api.mainnet-beta.solana.com", "confirmed"));
  }

  // ---------- READ PATH (bot devs, free, no wallet): reading is immunity ----------

  /** Look up whether a target address carries an enforceable antibody. Free. */
  async checkAddress(target: PublicKey): Promise<Verdict> {
    return this.check(ThreatKind.Address, subjectOf(target));
  }

  async check(kind: ThreatKind, subject: Buffer): Promise<Verdict> {
    const pda = antibodyPda(kind, subject);
    const acc = await this.connection.getAccountInfo(pda);
    if (!acc) return { flagged: false, antibody: null };
    const ab = parseAntibody(Buffer.from(acc.data));
    // enforceable = not revoked. (full maturity/corrob gating mirrors the program;
    // genesis stake==0 and Challenged are always enforceable.)
    const flagged = ab.status !== Status.Revoked;
    return { flagged, antibody: ab };
  }

  /** Throw WaneBlockedError if the target is flagged. One-liner guard before signing. */
  async assertSafe(target: PublicKey): Promise<void> {
    const v = await this.checkAddress(target);
    if (v.flagged) throw new WaneBlockedError(target);
  }

  /** Total antibodies known to the registry. */
  async count(): Promise<bigint> {
    const acc = await this.connection.getAccountInfo(configPda());
    if (!acc) return 0n;
    // RegistryConfig: 8 disc + 5 pubkeys(160) + antibody_count u64
    return Buffer.from(acc.data).readBigUInt64LE(8 + 160);
  }

  // ---------- REPORT (mint an antibody so others are immune) ----------

  /** Report a new threat. Stakes $WANE (publisher_ata must hold it). */
  async reportIx(
    publisher: PublicKey,
    publisherAta: PublicKey,
    stakeVault: PublicKey,
    kind: ThreatKind,
    subject: Buffer,
    evidence: Buffer = Buffer.alloc(32),
  ): Promise<TransactionInstruction> {
    const data = Buffer.concat([disc("mint_antibody"), Buffer.from([kind]), subject, evidence]);
    return new TransactionInstruction({
      programId: REGISTRY_PROGRAM,
      keys: [
        { pubkey: publisher, isSigner: true, isWritable: true },
        { pubkey: configPda(), isSigner: false, isWritable: true },
        { pubkey: antibodyPda(kind, subject), isSigner: false, isWritable: true },
        { pubkey: publisherAta, isSigner: false, isWritable: true },
        { pubkey: stakeVault, isSigner: false, isWritable: true },
        { pubkey: SPL_TOKEN, isSigner: false, isWritable: false },
        { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
      ],
      data,
    });
  }
