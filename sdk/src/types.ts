import { PublicKey, TransactionSignature } from "@solana/web3.js";

export enum MbtiType {
  INTJ = "INTJ",
  INTP = "INTP",
  ENTJ = "ENTJ",
  ENTP = "ENTP",
  INFJ = "INFJ",
  INFP = "INFP",
  ENFJ = "ENFJ",
  ENFP = "ENFP",
  ISTJ = "ISTJ",
  ISFJ = "ISFJ",
  ESTJ = "ESTJ",
  ESFJ = "ESFJ",
  ISTP = "ISTP",
  ISFP = "ISFP",
  ESTP = "ESTP",
  ESFP = "ESFP",
}

export enum TradeDirection {
  LONG = "LONG",
  SHORT = "SHORT",
}

export enum TradeStatus {
  PENDING = "PENDING",
  OPEN = "OPEN",
  CLOSED = "CLOSED",
  LIQUIDATED = "LIQUIDATED",
  CANCELLED = "CANCELLED",
}

export enum OrderType {
  MARKET = "MARKET",
  LIMIT = "LIMIT",
  STOP_LOSS = "STOP_LOSS",
  TAKE_PROFIT = "TAKE_PROFIT",
}

export interface TradePosition {
  id: string;
  owner: PublicKey;
  tokenMint: PublicKey;
  direction: TradeDirection;
  entryPrice: number;
  currentPrice: number;
  size: number;
  leverage: number;
  margin: number;
  unrealizedPnl: number;
  realizedPnl: number;
  status: TradeStatus;
  stopLoss: number | null;
  takeProfit: number | null;
  openedAt: number;
  closedAt: number | null;
  txSignature: TransactionSignature;
}

export interface TradingStrategy {
  mbtiType: MbtiType;
  riskTolerance: number;
  maxPositionSizePct: number;
  maxLeverage: number;
  defaultLeverage: number;
  entryThreshold: number;
  exitThreshold: number;
  stopLossPercentage: number;
  takeProfitPercentage: number;
  maxHoldingPeriodMs: number;
  minHoldingPeriodMs: number;
  maxConcurrentPositions: number;
  trailingStopEnabled: boolean;
  trailingStopPercentage: number;
  dcaEnabled: boolean;
  dcaIntervalMs: number;
  sentimentWeight: number;
  technicalWeight: number;
  fundamentalWeight: number;
  rebalanceIntervalMs: number;
  description: string;
}

export interface UserAccount {
  owner: PublicKey;
  authority: PublicKey;
  mbtiType: MbtiType;
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
  accountBump: number;
}

export interface TradeResult {
  success: boolean;
  tradeId: string;
  txSignature: TransactionSignature;
  position: TradePosition | null;
  error: string | null;
  timestamp: number;
}

export interface X402Payment {
  version: string;
  network: string;
  paymentToken: string;
  paymentAmount: number;
  payerAddress: string;
  recipientAddress: string;
  txSignature: TransactionSignature | null;
  expiresAt: number;
  nonce: string;
  payload: string;
}
