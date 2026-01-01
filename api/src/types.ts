import { Request } from "express";

export interface TradeRequest {
  tokenMint: string;
  direction: "LONG" | "SHORT";
  size: number;
  leverage?: number;
  orderType?: "MARKET" | "LIMIT" | "STOP_LOSS" | "TAKE_PROFIT";
  limitPrice?: number;
  stopLoss?: number;
  takeProfit?: number;
  walletAddress: string;
}

export interface TradeResponse {
  success: boolean;
  tradeId: string;
  txSignature: string;
  position: PositionResponse | null;
  error: string | null;
  timestamp: number;
}

export interface PositionResponse {
  id: string;
  owner: string;
  tokenMint: string;
  direction: "LONG" | "SHORT";
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

export interface StatusResponse {
  wallet: string;
  mbtiType: string;
  balance: number;
  lockedBalance: number;
  totalDeposited: number;
  totalWithdrawn: number;
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  totalPnl: number;
  winRate: number;
  createdAt: number;
  lastTradeAt: number;
}

export interface PnLResponse {
  wallet: string;
  period: string;
  totalPnl: number;
  realizedPnl: number;
  unrealizedPnl: number;
  winRate: number;
  totalTrades: number;
  avgTradeReturn: number;
  bestTrade: number;
  worstTrade: number;
  sharpeRatio: number;
  maxDrawdown: number;
  currentDrawdown: number;
  generatedAt: number;
}

export interface HealthResponse {
  status: "healthy" | "degraded" | "unhealthy";
  version: string;
  uptime: number;
  solanaRpc: {
    connected: boolean;
    slot: number | null;
    latencyMs: number;
  };
  timestamp: number;
}

export interface ErrorResponse {
  error: string;
  code: string;
  message: string;
  timestamp: number;
}

export interface PaymentRequiredResponse {
  error: "Payment Required";
  message: string;
  paymentAmount: number;
  recipientAddress: string;
  nonce: string;
  expiresAt: number;
  payload: string;
  network: "solana";
  token: "SOL";
  version: string;
}

export interface AuthenticatedRequest extends Request {
  walletAddress?: string;
  walletPublicKey?: Uint8Array;
}

export interface X402VerifiedRequest extends Request {
  x402Payment?: {
    valid: boolean;
    txSignature: string;
    amount: number;
    payer: string;
    recipient: string;
    confirmedAt: number;
    blockSlot: number;
  };
}

export interface PaginationQuery {
  page?: number;
  limit?: number;
  sortBy?: string;
  sortDir?: "asc" | "desc";
}

export interface TradeFilter {
  status?: string;
  direction?: string;
  tokenMint?: string;
  fromDate?: number;
  toDate?: number;
}

export const API_VERSION = "1.0.0";
export const DEFAULT_PAGE_SIZE = 20;
export const MAX_PAGE_SIZE = 100;

export const TRADE_FEES: Record<string, number> = {
  "/trade": 0.001,
  "/trade/execute": 0.002,
};
