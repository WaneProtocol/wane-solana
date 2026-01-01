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
