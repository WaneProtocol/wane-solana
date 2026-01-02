import { Request, Response, NextFunction } from "express";
import { Connection, PublicKey } from "@solana/web3.js";
import {
  X402VerifiedRequest,
  PaymentRequiredResponse,
  ErrorResponse,
  TRADE_FEES,
} from "../types";

const X402_VERSION = "1.0";
const X402_SCHEME = "x402-sol";
const PAYMENT_TTL_MS = 300_000;
const PROCESSED_PAYMENTS = new Map<string, ProcessedPayment>();
const PAYMENT_CACHE_TTL = 600_000;

interface ProcessedPayment {
  txSignature: string;
  amount: number;
  payer: string;
  processedAt: number;
}

interface X402Headers {
  scheme: string;
  token: string;
  amount: string;
  payer: string;
  recipient: string;
  signature: string;
  nonce: string;
  expiry: string;
}

let cacheCleanupTimer: NodeJS.Timer | null = null;

function startCacheCleanup(): void {
  if (cacheCleanupTimer) return;
  cacheCleanupTimer = setInterval(() => {
    const now = Date.now();
    for (const [key, val] of PROCESSED_PAYMENTS.entries()) {
      if (now - val.processedAt > PAYMENT_CACHE_TTL) {
        PROCESSED_PAYMENTS.delete(key);
      }
    }
  }, 60_000);
}
