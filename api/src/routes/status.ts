import { Router, Request, Response } from "express";
import { Connection, PublicKey } from "@solana/web3.js";
import { z } from "zod";
import {
  AuthenticatedRequest,
  StatusResponse,
  PnLResponse,
  PositionResponse,
  ErrorResponse,
} from "../types";
import { walletAuth } from "../middleware/auth";

const PnLPeriodSchema = z.enum(["1H", "1D", "1W", "1M", "ALL"]).default("ALL");

export function createStatusRouter(
  connection: Connection,
  programId: PublicKey
): Router {
  const router = Router();

  router.get(
    "/",
    walletAuth(),
    async (req: AuthenticatedRequest, res: Response) => {
      const walletAddress = req.walletAddress!;

      try {
        const account = await fetchUserAccount(
          connection,
          programId,
          walletAddress
        );

        if (!account) {
          const errorResponse: ErrorResponse = {
            error: "Not Found",
            code: "ACCOUNT_NOT_FOUND",
            message: `No PIKKY account found for wallet ${walletAddress}`,
            timestamp: Date.now(),
          };
          res.status(404).json(errorResponse);
          return;
        }

        const response: StatusResponse = {
          wallet: walletAddress,
          mbtiType: account.mbtiType,
          balance: account.balance,
          lockedBalance: account.lockedBalance,
          totalDeposited: account.totalDeposited,
          totalWithdrawn: account.totalWithdrawn,
          totalTrades: account.totalTrades,
          winningTrades: account.winningTrades,
          losingTrades: account.losingTrades,
          totalPnl: account.totalPnl,
          winRate:
            account.totalTrades > 0
              ? account.winningTrades / account.totalTrades
              : 0,
          createdAt: account.createdAt,
          lastTradeAt: account.lastTradeAt,
        };

        res.json(response);
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : String(error);
        const errorResponse: ErrorResponse = {
          error: "Internal Error",
          code: "STATUS_FETCH_FAILED",
          message: errorMessage,
          timestamp: Date.now(),
        };
        res.status(500).json(errorResponse);
      }
    }
  );

  router.get(
    "/pnl",
    walletAuth(),
    async (req: AuthenticatedRequest, res: Response) => {
      const walletAddress = req.walletAddress!;

      const periodResult = PnLPeriodSchema.safeParse(req.query.period);
      const period = periodResult.success ? periodResult.data : "ALL";

      try {
        const account = await fetchUserAccount(
          connection,
          programId,
          walletAddress
        );

        if (!account) {
          const errorResponse: ErrorResponse = {
            error: "Not Found",
            code: "ACCOUNT_NOT_FOUND",
            message: `No PIKKY account found for wallet ${walletAddress}`,
            timestamp: Date.now(),
          };
          res.status(404).json(errorResponse);
          return;
        }

        const positions = await fetchPositions(
          connection,
          programId,
          walletAddress
        );

        const periodMs = getPeriodMs(period);
        const cutoff = periodMs === 0 ? 0 : Date.now() - periodMs;
        const relevantPositions = positions.filter(
          (p) => p.openedAt >= cutoff
        );

        const closedPositions = relevantPositions.filter(
          (p) => p.status === "CLOSED"
        );
        const openPositions = relevantPositions.filter(
          (p) => p.status === "OPEN"
        );

        const realizedPnl = closedPositions.reduce(
          (sum, p) => sum + p.realizedPnl,
          0
        );
        const unrealizedPnl = openPositions.reduce(
          (sum, p) => sum + p.unrealizedPnl,
          0
        );
        const totalPnl = realizedPnl + unrealizedPnl;

        const winCount = closedPositions.filter(
          (p) => p.realizedPnl > 0
        ).length;
        const winRate =
          closedPositions.length > 0
            ? winCount / closedPositions.length
            : 0;

        const returns = closedPositions.map(
          (p) => p.realizedPnl / (p.size || 1)
        );
        const avgTradeReturn =
          returns.length > 0
            ? returns.reduce((s, r) => s + r, 0) / returns.length
            : 0;
        const bestTrade =
          returns.length > 0 ? Math.max(...returns) : 0;
        const worstTrade =
          returns.length > 0 ? Math.min(...returns) : 0;

        const sharpeRatio = computeSharpe(returns);
        const equityCurve = buildEquityCurve(
          account.totalDeposited,
          closedPositions
        );
        const maxDrawdown = computeMaxDrawdown(equityCurve);
        const peak =
          equityCurve.length > 0 ? Math.max(...equityCurve) : 0;
        const current =
          equityCurve.length > 0 ? equityCurve[equityCurve.length - 1] : 0;
        const currentDrawdown =
          peak > 0 ? (peak - current) / peak : 0;

        const response: PnLResponse = {
          wallet: walletAddress,
          period,
          totalPnl,
          realizedPnl,
          unrealizedPnl,
          winRate,
          totalTrades: relevantPositions.length,
          avgTradeReturn,
          bestTrade,
          worstTrade,
          sharpeRatio,
          maxDrawdown,
          currentDrawdown,
          generatedAt: Date.now(),
        };

        res.json(response);
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : String(error);
        const errorResponse: ErrorResponse = {
          error: "Internal Error",
          code: "PNL_CALC_FAILED",
          message: errorMessage,
          timestamp: Date.now(),
        };
        res.status(500).json(errorResponse);
      }
    }
  );

  router.get(
    "/positions",
    walletAuth(),
    async (req: AuthenticatedRequest, res: Response) => {
      const walletAddress = req.walletAddress!;
      const statusFilter = req.query.status as string | undefined;

      try {
        let positions = await fetchPositions(
          connection,
          programId,
          walletAddress
        );

        if (statusFilter) {
          positions = positions.filter(
            (p) => p.status === statusFilter.toUpperCase()
          );
        }

        res.json({
          wallet: walletAddress,
          count: positions.length,
          positions,
          timestamp: Date.now(),
        });
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : String(error);
        const errorResponse: ErrorResponse = {
          error: "Internal Error",
          code: "POSITIONS_FETCH_FAILED",
          message: errorMessage,
          timestamp: Date.now(),
        };
        res.status(500).json(errorResponse);
      }
    }
  );

  return router;
}

interface OnChainAccount {
  mbtiType: string;
  balance: number;
  lockedBalance: number;
  totalDeposited: number;
  totalWithdrawn: number;
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  totalPnl: number;
  createdAt: number;
  lastTradeAt: number;
}

async function fetchUserAccount(
  connection: Connection,
  programId: PublicKey,
  walletAddress: string
): Promise<OnChainAccount | null> {
  const userPubkey = new PublicKey(walletAddress);
  const [userAccountPDA] = PublicKey.findProgramAddressSync(
    [Buffer.from("user_account"), userPubkey.toBuffer()],
    programId
  );

  const accountInfo = await connection.getAccountInfo(
    userAccountPDA,
    "confirmed"
  );

  if (!accountInfo) {
    return null;
  }

  const data = accountInfo.data;
  const DISC = 8;
  let offset = DISC + 32 + 32; // skip discriminator + owner + authority

  const mbtiLen = data.readUInt32LE(offset);
  offset += 4;
  const mbtiType = data.slice(offset, offset + mbtiLen).toString("utf-8");
  offset += mbtiLen;

  const balance = Number(data.readBigUInt64LE(offset)) / 1e9;
  offset += 8;
  const lockedBalance = Number(data.readBigUInt64LE(offset)) / 1e9;
  offset += 8;
  const totalDeposited = Number(data.readBigUInt64LE(offset)) / 1e9;
  offset += 8;
  const totalWithdrawn = Number(data.readBigUInt64LE(offset)) / 1e9;
  offset += 8;
  const totalTrades = data.readUInt32LE(offset);
  offset += 4;
  const winningTrades = data.readUInt32LE(offset);
  offset += 4;
  const losingTrades = data.readUInt32LE(offset);
  offset += 4;
  const totalPnl = Number(data.readBigInt64LE(offset)) / 1e9;
  offset += 8;
  const createdAt = Number(data.readBigInt64LE(offset));
  offset += 8;
  const lastTradeAt = Number(data.readBigInt64LE(offset));

  return {
    mbtiType,
    balance,
    lockedBalance,
    totalDeposited,
    totalWithdrawn,
    totalTrades,
    winningTrades,
    losingTrades,
    totalPnl,
    createdAt,
    lastTradeAt,
  };
}

interface OnChainPosition {
  id: string;
  owner: string;
  tokenMint: string;
  direction: string;
  entryPrice: number;
  currentPrice: number;
  size: number;
  leverage: number;
  margin: number;
  unrealizedPnl: number;
  realizedPnl: number;
  status: string;
  stopLoss: number | null;
  takeProfit: number | null;
  openedAt: number;
  closedAt: number | null;
}

async function fetchPositions(
  connection: Connection,
  programId: PublicKey,
  walletAddress: string
): Promise<OnChainPosition[]> {
  const userPubkey = new PublicKey(walletAddress);

  const accounts = await connection.getProgramAccounts(programId, {
    commitment: "confirmed",
    filters: [
      { dataSize: 256 },
      {
        memcmp: {
          offset: 8,
          bytes: userPubkey.toBase58(),
        },
      },
    ],
  });

  return accounts.map((acc) => {
    const data = acc.account.data;
    let offset = 8;

    const idLen = data.readUInt32LE(offset);
    offset += 4;
    const id = data.slice(offset, offset + idLen).toString("utf-8");
    offset += idLen;

    const owner = new PublicKey(data.slice(offset, offset + 32)).toBase58();
    offset += 32;

    const tokenMint = new PublicKey(
      data.slice(offset, offset + 32)
    ).toBase58();
    offset += 32;

    const dirByte = data.readUInt8(offset);
    offset += 1;
    const direction = dirByte === 0 ? "LONG" : "SHORT";

    const entryPrice = Number(data.readBigUInt64LE(offset)) / 1e9;
    offset += 8;
    const currentPrice = Number(data.readBigUInt64LE(offset)) / 1e9;
    offset += 8;
    const size = Number(data.readBigUInt64LE(offset)) / 1e9;
    offset += 8;
    const leverage = data.readUInt8(offset);
    offset += 1;
    const margin = Number(data.readBigUInt64LE(offset)) / 1e9;
    offset += 8;
    const unrealizedPnl = Number(data.readBigInt64LE(offset)) / 1e9;
    offset += 8;
    const realizedPnl = Number(data.readBigInt64LE(offset)) / 1e9;
    offset += 8;

    const statusByte = data.readUInt8(offset);
    offset += 1;
    const statusMap: Record<number, string> = {
      0: "PENDING",
      1: "OPEN",
      2: "CLOSED",
      3: "LIQUIDATED",
      4: "CANCELLED",
    };
    const status = statusMap[statusByte] ?? "PENDING";

    const hasSL = data.readUInt8(offset) === 1;
    offset += 1;
    const stopLoss = hasSL
      ? Number(data.readBigUInt64LE(offset)) / 1e9
      : null;
    offset += 8;

    const hasTP = data.readUInt8(offset) === 1;
    offset += 1;
    const takeProfit = hasTP
      ? Number(data.readBigUInt64LE(offset)) / 1e9
      : null;
    offset += 8;

    const openedAt = Number(data.readBigInt64LE(offset));
    offset += 8;

    const hasClosed = data.readUInt8(offset) === 1;
    offset += 1;
    const closedAt = hasClosed
      ? Number(data.readBigInt64LE(offset))
      : null;

    return {
      id,
      owner,
      tokenMint,
      direction,
      entryPrice,
      currentPrice,
      size,
      leverage,
      margin,
      unrealizedPnl,
      realizedPnl,
      status,
      stopLoss,
      takeProfit,
      openedAt,
      closedAt,
    };
  });
}
