import express, { Request, Response, NextFunction } from "express";
import cors from "cors";
import helmet from "helmet";
import morgan from "morgan";
import { Connection, Keypair, PublicKey } from "@solana/web3.js";
import * as bs58 from "bs58";
import { createHealthRouter } from "./routes/health";
import { createStatusRouter } from "./routes/status";
import { createTradeRouter } from "./routes/trade";
import { ErrorResponse, API_VERSION } from "./types";

interface ServerConfig {
  port: number;
  host: string;
  solanaRpcUrl: string;
  programId: string;
  serverPrivateKey: string;
  recipientAddress: string;
  corsOrigins: string[];
  rateLimitWindowMs: number;
  rateLimitMaxRequests: number;
}

function loadConfig(): ServerConfig {
  return {
    port: parseInt(process.env.PORT ?? "3402", 10),
    host: process.env.HOST ?? "0.0.0.0",
    solanaRpcUrl:
      process.env.SOLANA_RPC_URL ?? "https://api.mainnet-beta.solana.com",
    programId:
      process.env.PROGRAM_ID ??
      "PiKKYaGE7R9Bz5N3uqT2vJkF8mHdCeqLzAo1111111",
    serverPrivateKey: process.env.SERVER_PRIVATE_KEY ?? "",
    recipientAddress: process.env.RECIPIENT_ADDRESS ?? "",
    corsOrigins: (process.env.CORS_ORIGINS ?? "*").split(","),
    rateLimitWindowMs: parseInt(
      process.env.RATE_LIMIT_WINDOW_MS ?? "60000",
      10
    ),
    rateLimitMaxRequests: parseInt(
      process.env.RATE_LIMIT_MAX_REQUESTS ?? "60",
      10
    ),
  };
}
