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
