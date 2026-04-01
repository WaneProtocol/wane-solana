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
