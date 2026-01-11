import { Request, Response, NextFunction } from "express";
import { PublicKey } from "@solana/web3.js";
import * as nacl from "tweetnacl";
import * as bs58 from "bs58";
import { AuthenticatedRequest, ErrorResponse } from "../types";

const SIGNATURE_MAX_AGE_MS = 300_000; // 5 minutes
const NONCE_CACHE = new Map<string, number>();
const NONCE_CLEANUP_INTERVAL = 60_000;

let cleanupTimer: NodeJS.Timer | null = null;

function startNonceCleanup(): void {
  if (cleanupTimer) return;
  cleanupTimer = setInterval(() => {
    const now = Date.now();
    for (const [nonce, timestamp] of NONCE_CACHE.entries()) {
      if (now - timestamp > SIGNATURE_MAX_AGE_MS * 2) {
        NONCE_CACHE.delete(nonce);
      }
    }
  }, NONCE_CLEANUP_INTERVAL);
}

export function walletAuth() {
  startNonceCleanup();

  return (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    const authHeader = req.headers["authorization"];

    if (!authHeader || !authHeader.startsWith("Solana ")) {
      const errorResponse: ErrorResponse = {
        error: "Unauthorized",
        code: "AUTH_MISSING",
        message:
          'Missing or invalid Authorization header. Expected format: "Solana <base58-encoded-payload>"',
        timestamp: Date.now(),
      };
      res.status(401).json(errorResponse);
      return;
    }

    const encodedPayload = authHeader.slice(7);

    let payload: AuthPayload;
    try {
      const decoded = Buffer.from(
        bs58.default.decode(encodedPayload)
      ).toString("utf-8");
      payload = JSON.parse(decoded) as AuthPayload;
    } catch {
      const errorResponse: ErrorResponse = {
        error: "Unauthorized",
        code: "AUTH_INVALID_PAYLOAD",
        message: "Could not decode authorization payload",
        timestamp: Date.now(),
      };
      res.status(401).json(errorResponse);
      return;
    }

    if (
      !payload.walletAddress ||
      !payload.signature ||
      !payload.message ||
      !payload.timestamp
    ) {
      const errorResponse: ErrorResponse = {
        error: "Unauthorized",
        code: "AUTH_INCOMPLETE",
        message:
          "Authorization payload must include walletAddress, signature, message, and timestamp",
        timestamp: Date.now(),
      };
      res.status(401).json(errorResponse);
      return;
    }

    const age = Date.now() - payload.timestamp;
    if (age > SIGNATURE_MAX_AGE_MS || age < -30_000) {
      const errorResponse: ErrorResponse = {
        error: "Unauthorized",
        code: "AUTH_EXPIRED",
        message: "Authorization signature has expired",
        timestamp: Date.now(),
      };
      res.status(401).json(errorResponse);
      return;
    }

    if (payload.nonce) {
      if (NONCE_CACHE.has(payload.nonce)) {
        const errorResponse: ErrorResponse = {
          error: "Unauthorized",
          code: "AUTH_NONCE_REUSED",
          message: "Nonce has already been used",
          timestamp: Date.now(),
        };
        res.status(401).json(errorResponse);
        return;
      }
      NONCE_CACHE.set(payload.nonce, Date.now());
    }

    let publicKeyBytes: Uint8Array;
    try {
      const pubkey = new PublicKey(payload.walletAddress);
      publicKeyBytes = pubkey.toBytes();
    } catch {
      const errorResponse: ErrorResponse = {
        error: "Unauthorized",
        code: "AUTH_INVALID_WALLET",
        message: "Invalid wallet address",
        timestamp: Date.now(),
      };
      res.status(401).json(errorResponse);
      return;
    }

    let signatureBytes: Uint8Array;
    try {
      signatureBytes = bs58.default.decode(payload.signature);
    } catch {
      const errorResponse: ErrorResponse = {
        error: "Unauthorized",
        code: "AUTH_INVALID_SIGNATURE",
        message: "Could not decode signature",
        timestamp: Date.now(),
      };
      res.status(401).json(errorResponse);
      return;
    }

    const messageBytes = new TextEncoder().encode(payload.message);
    const valid = nacl.sign.detached.verify(
      messageBytes,
      signatureBytes,
      publicKeyBytes
    );

    if (!valid) {
      const errorResponse: ErrorResponse = {
        error: "Unauthorized",
        code: "AUTH_SIGNATURE_INVALID",
        message: "Wallet signature verification failed",
        timestamp: Date.now(),
      };
      res.status(401).json(errorResponse);
      return;
    }

    const expectedMessage = buildExpectedMessage(
      payload.walletAddress,
      payload.timestamp,
      payload.nonce
    );
    if (payload.message !== expectedMessage) {
      const errorResponse: ErrorResponse = {
        error: "Unauthorized",
        code: "AUTH_MESSAGE_MISMATCH",
        message: "Signed message does not match expected format",
        timestamp: Date.now(),
      };
      res.status(401).json(errorResponse);
      return;
    }

    req.walletAddress = payload.walletAddress;
    req.walletPublicKey = publicKeyBytes;
    next();
  };
}

export function optionalWalletAuth() {
  return (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    const authHeader = req.headers["authorization"];

    if (!authHeader || !authHeader.startsWith("Solana ")) {
      next();
      return;
    }

    walletAuth()(req, res, next);
  };
}

function buildExpectedMessage(
  walletAddress: string,
  timestamp: number,
  nonce?: string
): string {
  const parts = [
    "PIKKY Authentication",
    `Wallet: ${walletAddress}`,
    `Timestamp: ${timestamp}`,
  ];
  if (nonce) {
    parts.push(`Nonce: ${nonce}`);
  }
  return parts.join("\n");
}

export function generateAuthMessage(
  walletAddress: string,
  nonce?: string
): { message: string; timestamp: number } {
  const timestamp = Date.now();
  const message = buildExpectedMessage(walletAddress, timestamp, nonce);
  return { message, timestamp };
}

interface AuthPayload {
  walletAddress: string;
  signature: string;
  message: string;
  timestamp: number;
  nonce?: string;
}
