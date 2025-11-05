import { PublicKey, Connection, TransactionSignature } from "@solana/web3.js";
import * as nacl from "tweetnacl";
import * as bs58 from "bs58";
import { LAMPORTS_PER_SOL, PIKKY_PROGRAM_ID } from "./types";

export function solToLamports(sol: number): number {
  return Math.round(sol * LAMPORTS_PER_SOL);
}

export function lamportsToSol(lamports: number): number {
  return lamports / LAMPORTS_PER_SOL;
}

export function bpsToDecimal(bps: number): number {
  return bps / 10_000;
}

export function decimalToBps(decimal: number): number {
  return Math.round(decimal * 10_000);
}

export function calculateFee(amount: number, feeBps: number): number {
  return Math.floor((amount * feeBps) / 10_000);
}

export async function deriveUserAccountPDA(
  userPubkey: PublicKey,
  programId?: PublicKey
): Promise<[PublicKey, number]> {
  const pid = programId ?? new PublicKey(PIKKY_PROGRAM_ID);
  return PublicKey.findProgramAddressSync(
    [Buffer.from("user_account"), userPubkey.toBuffer()],
    pid
  );
}

export async function deriveTradeVaultPDA(
  userPubkey: PublicKey,
  tradeId: string,
  programId?: PublicKey
): Promise<[PublicKey, number]> {
  const pid = programId ?? new PublicKey(PIKKY_PROGRAM_ID);
  return PublicKey.findProgramAddressSync(
    [
      Buffer.from("trade_vault"),
      userPubkey.toBuffer(),
      Buffer.from(tradeId),
    ],
    pid
  );
}

export async function deriveProtocolTreasuryPDA(
  programId?: PublicKey
): Promise<[PublicKey, number]> {
  const pid = programId ?? new PublicKey(PIKKY_PROGRAM_ID);
  return PublicKey.findProgramAddressSync(
    [Buffer.from("protocol_treasury")],
    pid
  );
}

export async function deriveMbtiStrategyPDA(
  mbtiType: string,
  programId?: PublicKey
): Promise<[PublicKey, number]> {
  const pid = programId ?? new PublicKey(PIKKY_PROGRAM_ID);
  return PublicKey.findProgramAddressSync(
    [Buffer.from("mbti_strategy"), Buffer.from(mbtiType)],
    pid
  );
}
