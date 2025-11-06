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

export function signMessage(
  message: Uint8Array,
  secretKey: Uint8Array
): Uint8Array {
  return nacl.sign.detached(message, secretKey);
}

export function verifySignature(
  message: Uint8Array,
  signature: Uint8Array,
  publicKey: Uint8Array
): boolean {
  return nacl.sign.detached.verify(message, signature, publicKey);
}

export function encodeSignature(signature: Uint8Array): string {
  return bs58.default.encode(signature);
}

export function decodeSignature(encoded: string): Uint8Array {
  return bs58.default.decode(encoded);
}

export function generateNonce(): string {
  const bytes = nacl.randomBytes(32);
  return bs58.default.encode(bytes);
}

export function isValidPublicKey(address: string): boolean {
  try {
    new PublicKey(address);
    return true;
  } catch {
    return false;
  }
}

export function shortenAddress(address: string, chars: number = 4): string {
  return `${address.slice(0, chars)}...${address.slice(-chars)}`;
}

export function generateTradeId(): string {
  const timestamp = Date.now().toString(36);
  const random = Math.random().toString(36).substring(2, 10);
  return `trade_${timestamp}_${random}`;
}

export async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  delayMs: number = 1000,
  backoffMultiplier: number = 2
): Promise<T> {
  let lastError: Error | null = null;
  let currentDelay = delayMs;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      if (attempt === maxRetries) {
        break;
      }

      const jitter = Math.random() * currentDelay * 0.1;
      await sleep(currentDelay + jitter);
      currentDelay *= backoffMultiplier;
    }
  }

  throw new PikkyError(
    `Operation failed after ${maxRetries + 1} attempts: ${lastError?.message}`,
    "RETRY_EXHAUSTED",
    lastError
  );
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function confirmTransaction(
  connection: Connection,
  signature: TransactionSignature,
  commitment: "processed" | "confirmed" | "finalized" = "confirmed",
  timeoutMs: number = 30_000
): Promise<boolean> {
  const startTime = Date.now();

  while (Date.now() - startTime < timeoutMs) {
    const status = await connection.getSignatureStatus(signature);

    if (status.value !== null) {
      if (status.value.err) {
        throw new PikkyError(
          `Transaction failed: ${JSON.stringify(status.value.err)}`,
          "TX_FAILED"
        );
      }

      const confirmationStatus = status.value.confirmationStatus;
      const commitmentLevels = ["processed", "confirmed", "finalized"];
      const targetLevel = commitmentLevels.indexOf(commitment);
      const currentLevel = commitmentLevels.indexOf(
        confirmationStatus ?? "processed"
      );

      if (currentLevel >= targetLevel) {
        return true;
      }
    }

    await sleep(500);
  }

  throw new PikkyError(
    `Transaction confirmation timeout after ${timeoutMs}ms`,
    "TX_TIMEOUT"
  );
}

export function calculatePnL(
  entryPrice: number,
  currentPrice: number,
  size: number,
  leverage: number,
  isLong: boolean
): number {
  const priceDelta = currentPrice - entryPrice;
  const direction = isLong ? 1 : -1;
  return (priceDelta / entryPrice) * size * leverage * direction;
}

export function calculateLiquidationPrice(
  entryPrice: number,
  leverage: number,
  isLong: boolean,
  maintenanceMarginRate: number = 0.05
): number {
  const marginRate = 1 / leverage;
  if (isLong) {
    return entryPrice * (1 - marginRate + maintenanceMarginRate);
  }
  return entryPrice * (1 + marginRate - maintenanceMarginRate);
}

export function calculatePositionValue(
  size: number,
  price: number,
  leverage: number
): number {
  return size * price * leverage;
}

export function calculateMarginRequired(
  size: number,
  price: number,
  leverage: number
): number {
  return (size * price) / leverage;
}

export function formatSol(lamports: number): string {
  return `${lamportsToSol(lamports).toFixed(9)} SOL`;
}

export function formatUsd(amount: number): string {
  return `$${amount.toFixed(2)}`;
}

export function calculateSharpeRatio(
  returns: number[],
  riskFreeRate: number = 0
): number {
  if (returns.length < 2) return 0;

  const avgReturn =
    returns.reduce((sum, r) => sum + r, 0) / returns.length;
  const excessReturn = avgReturn - riskFreeRate;
  const variance =
    returns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) /
    (returns.length - 1);
  const stdDev = Math.sqrt(variance);

  if (stdDev === 0) return 0;
  return excessReturn / stdDev;
}

export function calculateMaxDrawdown(equityCurve: number[]): number {
  if (equityCurve.length < 2) return 0;

  let maxDrawdown = 0;
  let peak = equityCurve[0];

  for (const value of equityCurve) {
    if (value > peak) {
      peak = value;
    }
    const drawdown = (peak - value) / peak;
    if (drawdown > maxDrawdown) {
      maxDrawdown = drawdown;
    }
  }

  return maxDrawdown;
}

export class PikkyError extends Error {
  public readonly code: string;
  public readonly cause: Error | null;

  constructor(message: string, code: string, cause?: Error | null) {
    super(message);
    this.name = "PikkyError";
    this.code = code;
    this.cause = cause ?? null;
  }

  toJSON() {
    return {
      name: this.name,
      message: this.message,
      code: this.code,
    };
  }
}
