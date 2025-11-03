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

export interface X402PaymentHeader {
  scheme: string;
  token: string;
  amount: string;
  payer: string;
  recipient: string;
  signature: string;
  nonce: string;
  expiry: string;
}

export interface X402PaymentReceipt {
  valid: boolean;
  txSignature: TransactionSignature;
  amount: number;
  payer: string;
  recipient: string;
  confirmedAt: number;
  blockSlot: number;
}

export interface PnLReport {
  owner: PublicKey;
  period: PnLPeriod;
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
  positions: TradePosition[];
  generatedAt: number;
}

export enum PnLPeriod {
  HOUR = "1H",
  DAY = "1D",
  WEEK = "1W",
  MONTH = "1M",
  ALL = "ALL",
}

export interface PikkyConfig {
  rpcEndpoint: string;
  programId: PublicKey;
  apiEndpoint: string;
  x402RecipientAddress: string;
  commitment?: "processed" | "confirmed" | "finalized";
  maxRetries?: number;
  retryDelayMs?: number;
  timeoutMs?: number;
}

export interface DepositParams {
  amount: number;
  tokenMint?: PublicKey;
}

export interface WithdrawParams {
  amount: number;
  tokenMint?: PublicKey;
}

export interface TradeParams {
  tokenMint: PublicKey;
  direction: TradeDirection;
  size: number;
  leverage?: number;
  orderType?: OrderType;
  limitPrice?: number;
  stopLoss?: number;
  takeProfit?: number;
}

export interface StatusQuery {
  includePositions?: boolean;
  includePnl?: boolean;
  pnlPeriod?: PnLPeriod;
}

export interface InstructionAccounts {
  user: PublicKey;
  userAccount: PublicKey;
  systemProgram: PublicKey;
  tokenProgram: PublicKey;
  rent: PublicKey;
  [key: string]: PublicKey;
}

export interface ProgramAddresses {
  userAccount: PublicKey;
  userAccountBump: number;
  tradeVault: PublicKey;
  tradeVaultBump: number;
  protocolTreasury: PublicKey;
  protocolTreasuryBump: number;
}

export const PIKKY_PROGRAM_ID = "PiKKYaGE7R9Bz5N3uqT2vJkF8mHdCeqLzAo1111111";
export const LAMPORTS_PER_SOL = 1_000_000_000;
export const X402_VERSION = "1.0";
export const X402_SCHEME = "x402-sol";
export const MAX_LEVERAGE = 20;
export const MIN_TRADE_SIZE_SOL = 0.01;
export const PROTOCOL_FEE_BPS = 30; // 0.3%
