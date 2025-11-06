import {
  Connection,
  Keypair,
  PublicKey,
  Transaction,
  sendAndConfirmTransaction,
} from "@solana/web3.js";
import {
  MbtiType,
  TradeDirection,
  TradeStatus,
  OrderType,
  PikkyConfig,
  TradeParams,
  DepositParams,
  WithdrawParams,
  StatusQuery,
  TradeResult,
  TradePosition,
  UserAccount,
  PnLReport,
  PnLPeriod,
  TradingStrategy,
  PIKKY_PROGRAM_ID,
  PROTOCOL_FEE_BPS,
  MAX_LEVERAGE,
  MIN_TRADE_SIZE_SOL,
} from "./types";
import { X402Client, X402Config } from "./x402";
import { getStrategy, shouldEnterTrade, shouldExitTrade, selectLeverage } from "./mbti";
import {
  buildInitializeInstruction,
  buildDepositInstruction,
  buildWithdrawInstruction,
  buildOpenTradeInstruction,
  buildCloseTradeInstruction,
  buildSetMbtiStrategyInstruction,
} from "./instructions";
import {
  solToLamports,
  lamportsToSol,
  generateTradeId,
  deriveUserAccountPDA,
  withRetry,
  confirmTransaction,
  calculatePnL,
  calculateFee,
  PikkyError,
} from "./utils";

export interface PikkyClientConfig {
  connection: Connection;
  wallet: Keypair;
  programId?: PublicKey;
  apiEndpoint?: string;
  x402RecipientAddress?: string;
  commitment?: "processed" | "confirmed" | "finalized";
  maxRetries?: number;
  retryDelayMs?: number;
}
