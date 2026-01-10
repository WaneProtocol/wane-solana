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

function createServerKeypair(privateKeyStr: string): Keypair {
  if (!privateKeyStr) {
    console.warn(
      "WARNING: No SERVER_PRIVATE_KEY set. Generating ephemeral keypair. DO NOT use in production."
    );
    return Keypair.generate();
  }

  try {
    const decoded = bs58.default.decode(privateKeyStr);
    return Keypair.fromSecretKey(decoded);
  } catch {
    try {
      const jsonArray = JSON.parse(privateKeyStr);
      return Keypair.fromSecretKey(Uint8Array.from(jsonArray));
    } catch {
      throw new Error(
        "SERVER_PRIVATE_KEY must be a base58-encoded string or JSON array of bytes"
      );
    }
  }
}

const requestCounts = new Map<string, { count: number; resetAt: number }>();

function rateLimiter(windowMs: number, maxRequests: number) {
  return (req: Request, res: Response, next: NextFunction) => {
    const clientIp =
      (req.headers["x-forwarded-for"] as string)?.split(",")[0]?.trim() ??
      req.socket.remoteAddress ??
      "unknown";

    const now = Date.now();
    let entry = requestCounts.get(clientIp);

    if (!entry || now > entry.resetAt) {
      entry = { count: 0, resetAt: now + windowMs };
      requestCounts.set(clientIp, entry);
    }

    entry.count++;

    res.set({
      "X-RateLimit-Limit": maxRequests.toString(),
      "X-RateLimit-Remaining": Math.max(
        0,
        maxRequests - entry.count
      ).toString(),
      "X-RateLimit-Reset": Math.ceil(entry.resetAt / 1000).toString(),
    });

    if (entry.count > maxRequests) {
      const errorResponse: ErrorResponse = {
        error: "Too Many Requests",
        code: "RATE_LIMITED",
        message: `Rate limit exceeded. Try again in ${Math.ceil((entry.resetAt - now) / 1000)} seconds.`,
        timestamp: now,
      };
      res.status(429).json(errorResponse);
      return;
    }

    next();
  };
}

function cleanupRateLimits(): void {
  setInterval(() => {
    const now = Date.now();
    for (const [key, val] of requestCounts.entries()) {
      if (now > val.resetAt) {
        requestCounts.delete(key);
      }
    }
  }, 60_000);
}

async function main(): Promise<void> {
  const config = loadConfig();

  console.log(`PIKKY API Server v${API_VERSION}`);
  console.log(`Solana RPC: ${config.solanaRpcUrl}`);
  console.log(`Program ID: ${config.programId}`);

  const connection = new Connection(config.solanaRpcUrl, "confirmed");
  const programId = new PublicKey(config.programId);
  const serverKeypair = createServerKeypair(config.serverPrivateKey);

  const recipientAddress =
    config.recipientAddress || serverKeypair.publicKey.toBase58();

  console.log(`Server wallet: ${serverKeypair.publicKey.toBase58()}`);
  console.log(`Payment recipient: ${recipientAddress}`);

  const app = express();

  app.use(helmet({ contentSecurityPolicy: false }));
  app.use(
    cors({
      origin: config.corsOrigins.includes("*") ? true : config.corsOrigins,
      methods: ["GET", "POST", "OPTIONS"],
      allowedHeaders: [
        "Content-Type",
        "Authorization",
        "X-Payment-Scheme",
        "X-Payment-Token",
        "X-Payment-Amount",
        "X-Payment-Payer",
        "X-Payment-Recipient",
        "X-Payment-Signature",
        "X-Payment-Nonce",
        "X-Payment-Expiry",
        "X-Payment-Tx",
      ],
      exposedHeaders: [
        "X-Payment-Amount",
        "X-Payment-Recipient",
        "X-Payment-Expiry",
        "X-Payment-Nonce",
        "X-Payment-Network",
        "X-Payment-Token",
        "X-Payment-Version",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "WWW-Authenticate",
      ],
    })
  );
  app.use(express.json({ limit: "1mb" }));
  app.use(
    morgan(":method :url :status :response-time ms - :res[content-length]")
  );
  app.use(
    rateLimiter(config.rateLimitWindowMs, config.rateLimitMaxRequests)
  );

  app.use("/health", createHealthRouter(connection));
  app.use(
    "/status",
    createStatusRouter(connection, programId)
  );
  app.use(
    "/trade",
    createTradeRouter(connection, programId, recipientAddress, serverKeypair)
  );

  app.get("/", (_req: Request, res: Response) => {
    res.json({
      name: "PIKKY API",
      version: API_VERSION,
      description:
        "x402-based Solana auto-trading AI agent with MBTI strategies",
      endpoints: {
        health: "GET /health",
        status: "GET /status (auth required)",
        pnl: "GET /status/pnl (auth required)",
        positions: "GET /status/positions (auth required)",
        createTrade: "POST /trade (auth required)",
        executeTrade: "POST /trade/execute (x402 payment required)",
        getTrade: "GET /trade/:id (auth required)",
        closeTrade: "POST /trade/:id/close (auth required)",
        listTrades: "GET /trade (auth required)",
      },
      x402: {
        version: "1.0",
        network: "solana",
        token: "SOL",
        recipientAddress,
      },
      timestamp: Date.now(),
    });
  });

  app.use((_req: Request, res: Response) => {
    const errorResponse: ErrorResponse = {
      error: "Not Found",
      code: "ROUTE_NOT_FOUND",
      message: "The requested endpoint does not exist",
      timestamp: Date.now(),
    };
    res.status(404).json(errorResponse);
  });

  app.use(
    (err: Error, _req: Request, res: Response, _next: NextFunction) => {
      console.error("Unhandled error:", err);

      const errorResponse: ErrorResponse = {
        error: "Internal Server Error",
        code: "INTERNAL_ERROR",
        message:
          process.env.NODE_ENV === "production"
            ? "An unexpected error occurred"
            : err.message,
        timestamp: Date.now(),
      };
      res.status(500).json(errorResponse);
    }
  );

  cleanupRateLimits();

  app.listen(config.port, config.host, () => {
    console.log(`PIKKY API server listening on ${config.host}:${config.port}`);
  });
}

main().catch((err) => {
  console.error("Fatal startup error:", err);
  process.exit(1);
});

