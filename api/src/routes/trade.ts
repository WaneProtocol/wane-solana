import { Router, Response } from "express";
import { Connection, PublicKey, Keypair, Transaction, SystemProgram, sendAndConfirmTransaction } from "@solana/web3.js";
import { z } from "zod";
import { v4 as uuidv4 } from "uuid";
import {
  AuthenticatedRequest,
  X402VerifiedRequest,
  TradeRequest,
  TradeResponse,
  PositionResponse,
  ErrorResponse,
} from "../types";
import { walletAuth } from "../middleware/auth";
import { x402PaymentGate } from "../middleware/x402";

const TradeRequestSchema = z.object({
  tokenMint: z
    .string()
    .min(32)
    .max(44)
    .refine((val) => {
      try {
        new PublicKey(val);
        return true;
      } catch {
        return false;
      }
    }, "Invalid Solana public key"),
  direction: z.enum(["LONG", "SHORT"]),
  size: z.number().positive().min(0.01).max(1000),
  leverage: z.number().int().min(1).max(20).optional().default(1),
  orderType: z
    .enum(["MARKET", "LIMIT", "STOP_LOSS", "TAKE_PROFIT"])
    .optional()
    .default("MARKET"),
  limitPrice: z.number().positive().optional(),
  stopLoss: z.number().positive().optional(),
  takeProfit: z.number().positive().optional(),
  walletAddress: z
    .string()
    .min(32)
    .max(44)
    .refine((val) => {
      try {
        new PublicKey(val);
        return true;
      } catch {
        return false;
      }
    }, "Invalid Solana public key"),
});

const tradeStore = new Map<string, StoredTrade>();

interface StoredTrade {
  id: string;
  request: TradeRequest;
  status: "pending" | "open" | "closed" | "failed";
  txSignature: string | null;
  position: PositionResponse | null;
  createdAt: number;
  updatedAt: number;
  payer: string | null;
  paymentTx: string | null;
  error: string | null;
}

export function createTradeRouter(
  connection: Connection,
  programId: PublicKey,
  recipientAddress: string,
  serverKeypair: Keypair
): Router {
  const router = Router();

  router.post(
    "/",
    walletAuth(),
    async (req: AuthenticatedRequest, res: Response) => {
      const parseResult = TradeRequestSchema.safeParse(req.body);

      if (!parseResult.success) {
        const errorResponse: ErrorResponse = {
          error: "Validation Error",
          code: "INVALID_REQUEST",
          message: parseResult.error.issues
            .map((i) => `${i.path.join(".")}: ${i.message}`)
            .join("; "),
          timestamp: Date.now(),
        };
        res.status(400).json(errorResponse);
        return;
      }

      const tradeReq = parseResult.data as TradeRequest;

      if (tradeReq.walletAddress !== req.walletAddress) {
        const errorResponse: ErrorResponse = {
          error: "Forbidden",
          code: "WALLET_MISMATCH",
          message:
            "Authenticated wallet does not match trade wallet address",
          timestamp: Date.now(),
        };
        res.status(403).json(errorResponse);
        return;
      }

      if (
        tradeReq.orderType === "LIMIT" &&
        tradeReq.limitPrice === undefined
      ) {
        const errorResponse: ErrorResponse = {
          error: "Validation Error",
          code: "MISSING_LIMIT_PRICE",
          message: "Limit orders require a limitPrice",
          timestamp: Date.now(),
        };
        res.status(400).json(errorResponse);
        return;
      }

      const tradeId = `trade_${Date.now().toString(36)}_${uuidv4().slice(0, 8)}`;

      const storedTrade: StoredTrade = {
        id: tradeId,
        request: tradeReq,
        status: "pending",
        txSignature: null,
        position: null,
        createdAt: Date.now(),
        updatedAt: Date.now(),
        payer: null,
        paymentTx: null,
        error: null,
      };

      tradeStore.set(tradeId, storedTrade);

      const response: TradeResponse = {
        success: true,
        tradeId,
        txSignature: "",
        position: null,
        error: null,
        timestamp: Date.now(),
      };

      res.status(201).json(response);
    }
  );

  router.get(
    "/:id",
    walletAuth(),
    async (req: AuthenticatedRequest, res: Response) => {
      const tradeId = req.params.id;
      const trade = tradeStore.get(tradeId);

      if (!trade) {
        const errorResponse: ErrorResponse = {
          error: "Not Found",
          code: "TRADE_NOT_FOUND",
          message: `Trade ${tradeId} not found`,
          timestamp: Date.now(),
        };
        res.status(404).json(errorResponse);
        return;
      }

      if (trade.request.walletAddress !== req.walletAddress) {
        const errorResponse: ErrorResponse = {
          error: "Forbidden",
          code: "ACCESS_DENIED",
          message: "You do not have access to this trade",
          timestamp: Date.now(),
        };
        res.status(403).json(errorResponse);
        return;
      }

      const response: TradeResponse = {
        success: trade.status !== "failed",
        tradeId: trade.id,
        txSignature: trade.txSignature ?? "",
        position: trade.position,
        error: trade.error,
        timestamp: trade.updatedAt,
      };

      res.json(response);
    }
  );

  router.post(
    "/execute",
    x402PaymentGate(connection, recipientAddress, 0.002),
    async (req: X402VerifiedRequest, res: Response) => {
      const parseResult = TradeRequestSchema.safeParse(req.body);

      if (!parseResult.success) {
        const errorResponse: ErrorResponse = {
          error: "Validation Error",
          code: "INVALID_REQUEST",
          message: parseResult.error.issues
            .map((i) => `${i.path.join(".")}: ${i.message}`)
            .join("; "),
          timestamp: Date.now(),
        };
        res.status(400).json(errorResponse);
        return;
      }

      const tradeReq = parseResult.data as TradeRequest;
      const payment = req.x402Payment!;

      const tradeId = `trade_${Date.now().toString(36)}_${uuidv4().slice(0, 8)}`;

      try {
        const userPubkey = new PublicKey(tradeReq.walletAddress);
        const tokenMint = new PublicKey(tradeReq.tokenMint);

        const [userAccountPDA] = PublicKey.findProgramAddressSync(
          [Buffer.from("user_account"), userPubkey.toBuffer()],
          programId
        );

        const accountInfo = await connection.getAccountInfo(
          userAccountPDA,
          "confirmed"
        );

        if (!accountInfo) {
          const errorResponse: ErrorResponse = {
            error: "Not Found",
            code: "ACCOUNT_NOT_FOUND",
            message: `No PIKKY account found for wallet ${tradeReq.walletAddress}. Initialize first.`,
            timestamp: Date.now(),
          };
          res.status(404).json(errorResponse);
          return;
        }

        const txSignature = await executeTrade(
          connection,
          programId,
          serverKeypair,
          userPubkey,
          tokenMint,
          tradeId,
          tradeReq
        );

        const position: PositionResponse = {
          id: tradeId,
          owner: tradeReq.walletAddress,
          tokenMint: tradeReq.tokenMint,
          direction: tradeReq.direction,
          entryPrice: 0,
          currentPrice: 0,
          size: tradeReq.size,
          leverage: tradeReq.leverage ?? 1,
          margin: tradeReq.size / (tradeReq.leverage ?? 1),
          unrealizedPnl: 0,
          realizedPnl: 0,
          status: "OPEN",
          stopLoss: tradeReq.stopLoss ?? null,
          takeProfit: tradeReq.takeProfit ?? null,
          openedAt: Date.now(),
          closedAt: null,
        };

        const storedTrade: StoredTrade = {
          id: tradeId,
          request: tradeReq,
          status: "open",
          txSignature,
          position,
          createdAt: Date.now(),
          updatedAt: Date.now(),
          payer: payment.payer,
          paymentTx: payment.txSignature,
          error: null,
        };

        tradeStore.set(tradeId, storedTrade);

        const response: TradeResponse = {
          success: true,
          tradeId,
          txSignature,
          position,
          error: null,
          timestamp: Date.now(),
        };

        res.status(200).json(response);
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : String(error);

        const storedTrade: StoredTrade = {
          id: tradeId,
          request: tradeReq,
          status: "failed",
          txSignature: null,
          position: null,
          createdAt: Date.now(),
          updatedAt: Date.now(),
          payer: payment.payer,
          paymentTx: payment.txSignature,
          error: errorMessage,
        };

        tradeStore.set(tradeId, storedTrade);

        const response: TradeResponse = {
          success: false,
          tradeId,
          txSignature: "",
          position: null,
          error: errorMessage,
          timestamp: Date.now(),
        };

        res.status(500).json(response);
      }
    }
  );

  router.post(
    "/:id/close",
    walletAuth(),
    async (req: AuthenticatedRequest, res: Response) => {
      const tradeId = req.params.id;
      const trade = tradeStore.get(tradeId);

      if (!trade) {
        const errorResponse: ErrorResponse = {
          error: "Not Found",
          code: "TRADE_NOT_FOUND",
          message: `Trade ${tradeId} not found`,
          timestamp: Date.now(),
        };
        res.status(404).json(errorResponse);
        return;
      }

      if (trade.request.walletAddress !== req.walletAddress) {
        const errorResponse: ErrorResponse = {
          error: "Forbidden",
          code: "ACCESS_DENIED",
          message: "You do not have access to this trade",
          timestamp: Date.now(),
        };
        res.status(403).json(errorResponse);
        return;
      }

      if (trade.status !== "open") {
        const errorResponse: ErrorResponse = {
          error: "Bad Request",
          code: "TRADE_NOT_OPEN",
          message: `Trade is in ${trade.status} state and cannot be closed`,
          timestamp: Date.now(),
        };
        res.status(400).json(errorResponse);
        return;
      }

      try {
        const userPubkey = new PublicKey(trade.request.walletAddress);

        const txSignature = await closeTrade(
          connection,
          programId,
          serverKeypair,
          userPubkey,
          tradeId
        );

        trade.status = "closed";
        trade.txSignature = txSignature;
        trade.updatedAt = Date.now();
        if (trade.position) {
          trade.position.status = "CLOSED";
          trade.position.closedAt = Date.now();
        }

        const response: TradeResponse = {
          success: true,
          tradeId,
          txSignature,
          position: trade.position,
          error: null,
          timestamp: Date.now(),
        };

        res.json(response);
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : String(error);
        const response: TradeResponse = {
          success: false,
          tradeId,
          txSignature: "",
          position: trade.position,
          error: errorMessage,
          timestamp: Date.now(),
        };
        res.status(500).json(response);
      }
    }
  );

  router.get(
    "/",
    walletAuth(),
    async (req: AuthenticatedRequest, res: Response) => {
      const walletAddress = req.walletAddress!;
      const statusFilter = req.query.status as string | undefined;

      const trades: StoredTrade[] = [];
      for (const trade of tradeStore.values()) {
        if (trade.request.walletAddress !== walletAddress) continue;
        if (statusFilter && trade.status !== statusFilter) continue;
        trades.push(trade);
      }

      trades.sort((a, b) => b.createdAt - a.createdAt);

      const page = parseInt(req.query.page as string, 10) || 1;
      const limit = Math.min(
        parseInt(req.query.limit as string, 10) || 20,
        100
      );
      const startIdx = (page - 1) * limit;
      const paginated = trades.slice(startIdx, startIdx + limit);

      res.json({
        trades: paginated.map((t) => ({
          tradeId: t.id,
          status: t.status,
          direction: t.request.direction,
          tokenMint: t.request.tokenMint,
          size: t.request.size,
          leverage: t.request.leverage,
          txSignature: t.txSignature,
          createdAt: t.createdAt,
          updatedAt: t.updatedAt,
        })),
        pagination: {
          page,
          limit,
          total: trades.length,
          totalPages: Math.ceil(trades.length / limit),
        },
        timestamp: Date.now(),
      });
    }
  );

  return router;
}

async function executeTrade(
  connection: Connection,
  programId: PublicKey,
  serverKeypair: Keypair,
  userPubkey: PublicKey,
  tokenMint: PublicKey,
  tradeId: string,
  tradeReq: TradeRequest
): Promise<string> {
  const [userAccountPDA] = PublicKey.findProgramAddressSync(
    [Buffer.from("user_account"), userPubkey.toBuffer()],
    programId
  );

  const [tradeVaultPDA] = PublicKey.findProgramAddressSync(
    [
      Buffer.from("trade_vault"),
      userPubkey.toBuffer(),
      Buffer.from(tradeId),
    ],
    programId
  );

  const [protocolTreasuryPDA] = PublicKey.findProgramAddressSync(
    [Buffer.from("protocol_treasury")],
    programId
  );

  const directionByte = tradeReq.direction === "LONG" ? 0 : 1;
  const orderTypeMap: Record<string, number> = {
    MARKET: 0,
    LIMIT: 1,
    STOP_LOSS: 2,
    TAKE_PROFIT: 3,
  };
  const orderTypeByte = orderTypeMap[tradeReq.orderType ?? "MARKET"] ?? 0;

  const sizeLamports = BigInt(Math.round(tradeReq.size * 1e9));
  const leverage = tradeReq.leverage ?? 1;

  const discriminator = createInstructionDiscriminator("openTrade");

  const tradeIdBytes = Buffer.from(tradeId, "utf-8");
  const tradeIdLenBuf = Buffer.alloc(4);
  tradeIdLenBuf.writeUInt32LE(tradeIdBytes.length);

  const argBuffers: Buffer[] = [
    discriminator,
    tradeIdLenBuf,
    tradeIdBytes,
  ];

  const dirBuf = Buffer.alloc(1);
  dirBuf.writeUInt8(directionByte);
  argBuffers.push(dirBuf);

  const sizeBuf = Buffer.alloc(8);
  sizeBuf.writeBigUInt64LE(sizeLamports);
  argBuffers.push(sizeBuf);

  const levBuf = Buffer.alloc(1);
  levBuf.writeUInt8(leverage);
  argBuffers.push(levBuf);

  const otBuf = Buffer.alloc(1);
  otBuf.writeUInt8(orderTypeByte);
  argBuffers.push(otBuf);

  // limitPrice option
  if (tradeReq.limitPrice !== undefined) {
    argBuffers.push(Buffer.from([1]));
    const lpBuf = Buffer.alloc(8);
    lpBuf.writeBigUInt64LE(BigInt(Math.round(tradeReq.limitPrice * 1e9)));
    argBuffers.push(lpBuf);
  } else {
    argBuffers.push(Buffer.from([0]));
  }

  // stopLoss option
  if (tradeReq.stopLoss !== undefined) {
    argBuffers.push(Buffer.from([1]));
    const slBuf = Buffer.alloc(8);
    slBuf.writeBigUInt64LE(BigInt(Math.round(tradeReq.stopLoss * 1e9)));
    argBuffers.push(slBuf);
  } else {
    argBuffers.push(Buffer.from([0]));
  }

  // takeProfit option
  if (tradeReq.takeProfit !== undefined) {
    argBuffers.push(Buffer.from([1]));
    const tpBuf = Buffer.alloc(8);
    tpBuf.writeBigUInt64LE(BigInt(Math.round(tradeReq.takeProfit * 1e9)));
    argBuffers.push(tpBuf);
  } else {
    argBuffers.push(Buffer.from([0]));
  }

  const data = Buffer.concat(argBuffers);

  const mbtiType = "INTJ";
  const [mbtiStrategyPDA] = PublicKey.findProgramAddressSync(
    [Buffer.from("mbti_strategy"), Buffer.from(mbtiType)],
    programId
  );

  const instruction = {
    programId,
    keys: [
      { pubkey: serverKeypair.publicKey, isSigner: true, isWritable: true },
      { pubkey: userAccountPDA, isSigner: false, isWritable: true },
      { pubkey: tradeVaultPDA, isSigner: false, isWritable: true },
      { pubkey: protocolTreasuryPDA, isSigner: false, isWritable: true },
      { pubkey: tokenMint, isSigner: false, isWritable: false },
      { pubkey: mbtiStrategyPDA, isSigner: false, isWritable: false },
      {
        pubkey: SystemProgram.programId,
        isSigner: false,
        isWritable: false,
      },
      {
        pubkey: new PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"),
        isSigner: false,
        isWritable: false,
      },
    ],
    data,
  };

  const transaction = new Transaction().add(instruction);
  const { blockhash, lastValidBlockHeight } =
    await connection.getLatestBlockhash("confirmed");
  transaction.recentBlockhash = blockhash;
  transaction.lastValidBlockHeight = lastValidBlockHeight;
  transaction.feePayer = serverKeypair.publicKey;

  const txSignature = await sendAndConfirmTransaction(
    connection,
    transaction,
    [serverKeypair],
    { commitment: "confirmed", maxRetries: 3 }
  );

  return txSignature;
}

async function closeTrade(
  connection: Connection,
  programId: PublicKey,
  serverKeypair: Keypair,
  userPubkey: PublicKey,
  tradeId: string
): Promise<string> {
  const [userAccountPDA] = PublicKey.findProgramAddressSync(
    [Buffer.from("user_account"), userPubkey.toBuffer()],
    programId
  );

  const [tradeVaultPDA] = PublicKey.findProgramAddressSync(
    [
      Buffer.from("trade_vault"),
      userPubkey.toBuffer(),
      Buffer.from(tradeId),
    ],
    programId
  );

  const [protocolTreasuryPDA] = PublicKey.findProgramAddressSync(
    [Buffer.from("protocol_treasury")],
    programId
  );

  const discriminator = createInstructionDiscriminator("closeTrade");
  const tradeIdBytes = Buffer.from(tradeId, "utf-8");
  const tradeIdLenBuf = Buffer.alloc(4);
  tradeIdLenBuf.writeUInt32LE(tradeIdBytes.length);
  const data = Buffer.concat([discriminator, tradeIdLenBuf, tradeIdBytes]);

  const instruction = {
    programId,
    keys: [
      { pubkey: serverKeypair.publicKey, isSigner: true, isWritable: true },
      { pubkey: userAccountPDA, isSigner: false, isWritable: true },
      { pubkey: tradeVaultPDA, isSigner: false, isWritable: true },
      { pubkey: protocolTreasuryPDA, isSigner: false, isWritable: true },
      {
        pubkey: SystemProgram.programId,
        isSigner: false,
        isWritable: false,
      },
    ],
    data,
  };

  const transaction = new Transaction().add(instruction);
  const { blockhash, lastValidBlockHeight } =
    await connection.getLatestBlockhash("confirmed");
  transaction.recentBlockhash = blockhash;
  transaction.lastValidBlockHeight = lastValidBlockHeight;
  transaction.feePayer = serverKeypair.publicKey;

  const txSignature = await sendAndConfirmTransaction(
    connection,
    transaction,
    [serverKeypair],
    { commitment: "confirmed", maxRetries: 3 }
  );

  return txSignature;
}

function createInstructionDiscriminator(name: string): Buffer {
  const crypto = require("crypto");
  const preimage = `global:${name}`;
  const hash = crypto.createHash("sha256").update(preimage).digest();
  return hash.slice(0, 8);
}
