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

export function x402PaymentGate(
  connection: Connection,
  recipientAddress: string,
  feeOverride?: number
) {
  startCacheCleanup();

  return async (
    req: X402VerifiedRequest,
    res: Response,
    next: NextFunction
  ) => {
    const requiredFee =
      feeOverride ?? TRADE_FEES[req.path] ?? 0.001;

    const paymentHeader = extractPaymentHeaders(req);

    if (!paymentHeader) {
      const nonce = generateNonce();
      const expiresAt = Date.now() + PAYMENT_TTL_MS;

      const paymentResponse: PaymentRequiredResponse = {
        error: "Payment Required",
        message: `This endpoint requires a payment of ${requiredFee} SOL via x402 protocol`,
        paymentAmount: requiredFee,
        recipientAddress,
        nonce,
        expiresAt,
        payload: buildPaymentPayload(req),
        network: "solana",
        token: "SOL",
        version: X402_VERSION,
      };

      res
        .status(402)
        .set({
          "X-Payment-Amount": requiredFee.toString(),
          "X-Payment-Recipient": recipientAddress,
          "X-Payment-Expiry": expiresAt.toString(),
          "X-Payment-Nonce": nonce,
          "X-Payment-Network": "solana",
          "X-Payment-Token": "SOL",
          "X-Payment-Version": X402_VERSION,
          "WWW-Authenticate": `${X402_SCHEME} realm="pikky-api"`,
        })
        .json(paymentResponse);
      return;
    }

    const txSignature =
      paymentHeader.signature ||
      (req.headers["x-payment-tx"] as string);

    if (!txSignature) {
      const errorResponse: ErrorResponse = {
        error: "Payment Invalid",
        code: "X402_NO_TX",
        message: "Payment header present but no transaction signature provided",
        timestamp: Date.now(),
      };
      res.status(400).json(errorResponse);
      return;
    }

    const cached = PROCESSED_PAYMENTS.get(txSignature);
    if (cached) {
      if (cached.amount >= requiredFee) {
        req.x402Payment = {
          valid: true,
          txSignature: cached.txSignature,
          amount: cached.amount,
          payer: cached.payer,
          recipient: recipientAddress,
          confirmedAt: cached.processedAt,
          blockSlot: 0,
        };
        next();
        return;
      }
    }

    const expiryTime = parseInt(paymentHeader.expiry, 10);
    if (expiryTime > 0 && Date.now() > expiryTime) {
      const errorResponse: ErrorResponse = {
        error: "Payment Expired",
        code: "X402_EXPIRED",
        message: "Payment has expired. Please request a new payment.",
        timestamp: Date.now(),
      };
      res.status(410).json(errorResponse);
      return;
    }

    try {
      const receipt = await verifyPaymentOnChain(
        connection,
        txSignature,
        requiredFee,
        recipientAddress
      );

      PROCESSED_PAYMENTS.set(txSignature, {
        txSignature: receipt.txSignature,
        amount: receipt.amount,
        payer: receipt.payer,
        processedAt: Date.now(),
      });

      req.x402Payment = receipt;
      next();
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      const errorResponse: ErrorResponse = {
        error: "Payment Verification Failed",
        code: "X402_VERIFICATION_FAILED",
        message: errorMessage,
        timestamp: Date.now(),
      };
      res.status(402).json(errorResponse);
    }
  };
}

function extractPaymentHeaders(req: Request): X402Headers | null {
  const scheme = req.headers["x-payment-scheme"] as string | undefined;
  const txSig =
    (req.headers["x-payment-signature"] as string) ||
    (req.headers["x-payment-tx"] as string);

  if (scheme && txSig) {
    return {
      scheme: scheme || X402_SCHEME,
      token: (req.headers["x-payment-token"] as string) || "SOL",
      amount: (req.headers["x-payment-amount"] as string) || "0",
      payer: (req.headers["x-payment-payer"] as string) || "",
      recipient: (req.headers["x-payment-recipient"] as string) || "",
      signature: txSig,
      nonce: (req.headers["x-payment-nonce"] as string) || "",
      expiry: (req.headers["x-payment-expiry"] as string) || "0",
    };
  }

  const authHeader = req.headers["authorization"];
  if (authHeader && authHeader.startsWith(X402_SCHEME)) {
    const encoded = authHeader.slice(X402_SCHEME.length + 1);
    try {
      const decoded = JSON.parse(
        Buffer.from(encoded, "base64").toString("utf-8")
      );
      return {
        scheme: decoded.scheme || X402_SCHEME,
        token: decoded.token || "SOL",
        amount: decoded.amount || "0",
        payer: decoded.payer || "",
        recipient: decoded.recipient || "",
        signature:
          (req.headers["x-payment-tx"] as string) || decoded.signature || "",
        nonce: decoded.nonce || "",
        expiry: decoded.expiry || "0",
      };
    } catch {
      return null;
    }
  }

  return null;
}

async function verifyPaymentOnChain(
  connection: Connection,
  txSignature: string,
  expectedAmount: number,
  expectedRecipient: string
): Promise<{
  valid: boolean;
  txSignature: string;
  amount: number;
  payer: string;
  recipient: string;
  confirmedAt: number;
  blockSlot: number;
}> {
  let txInfo;
  let attempts = 0;
  const maxAttempts = 5;
  const retryDelay = 1500;

  while (attempts < maxAttempts) {
    txInfo = await connection.getTransaction(txSignature, {
      commitment: "confirmed",
      maxSupportedTransactionVersion: 0,
    });

    if (txInfo) break;
    attempts++;
    if (attempts < maxAttempts) {
      await new Promise((r) => setTimeout(r, retryDelay));
    }
  }

  if (!txInfo) {
    throw new Error(
      `Transaction ${txSignature} not found after ${maxAttempts} attempts`
    );
  }

  if (txInfo.meta?.err) {
    throw new Error(
      `Transaction failed on-chain: ${JSON.stringify(txInfo.meta.err)}`
    );
  }

  const preBalances = txInfo.meta?.preBalances ?? [];
  const postBalances = txInfo.meta?.postBalances ?? [];
  const accountKeys =
    txInfo.transaction.message.getAccountKeys().staticAccountKeys;

  let payerAddress = "";
  let recipientReceived = 0;
  let recipientFound = false;

  for (let i = 0; i < accountKeys.length; i++) {
    const key = accountKeys[i].toBase58();
    const delta = (postBalances[i] ?? 0) - (preBalances[i] ?? 0);

    if (key === expectedRecipient && delta > 0) {
      recipientFound = true;
      recipientReceived = delta / 1_000_000_000;
    }

    if (delta < 0 && payerAddress === "") {
      payerAddress = key;
    }
  }

  if (!recipientFound) {
    throw new Error(
      `Expected recipient ${expectedRecipient} did not receive funds in transaction`
    );
  }

  if (recipientReceived < expectedAmount * 0.999) {
    throw new Error(
      `Insufficient payment: expected ${expectedAmount} SOL, received ${recipientReceived.toFixed(9)} SOL`
    );
  }

  return {
    valid: true,
    txSignature,
    amount: recipientReceived,
    payer: payerAddress,
    recipient: expectedRecipient,
    confirmedAt: (txInfo.blockTime ?? 0) * 1000,
    blockSlot: txInfo.slot,
  };
}

function generateNonce(): string {
  const chars =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let nonce = "";
  for (let i = 0; i < 32; i++) {
    nonce += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return nonce;
}

function buildPaymentPayload(req: Request): string {
  return JSON.stringify({
    method: req.method,
    path: req.path,
    timestamp: Date.now(),
    bodyHash: req.body
      ? require("crypto")
          .createHash("sha256")
          .update(JSON.stringify(req.body))
          .digest("hex")
          .slice(0, 16)
      : null,
  });
}
