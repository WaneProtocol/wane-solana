export { PikkyClient } from "./client";
export type { PikkyClientConfig } from "./client";

export { X402Client } from "./x402";
export type { X402Config } from "./x402";

export {
  MbtiType,
  TradeDirection,
  TradeStatus,
  OrderType,
  PnLPeriod,
  PIKKY_PROGRAM_ID,
  LAMPORTS_PER_SOL,
  X402_VERSION,
  X402_SCHEME,
  MAX_LEVERAGE,
  MIN_TRADE_SIZE_SOL,
  PROTOCOL_FEE_BPS,
} from "./types";

export type {
  TradePosition,
  TradingStrategy,
  UserAccount,
  TradeResult,
  X402Payment,
  X402PaymentHeader,
  X402PaymentReceipt,
  PnLReport,
  PikkyConfig,
  DepositParams,
  WithdrawParams,
  TradeParams,
  StatusQuery,
  InstructionAccounts,
  ProgramAddresses,
} from "./types";

export {
  MBTI_STRATEGIES,
  getStrategy,
  getStrategyDescription,
  getRiskCategory,
  calculatePositionSize,
  shouldEnterTrade,
  shouldExitTrade,
  selectLeverage,
  blendStrategies,
} from "./mbti";

export {
  buildInitializeInstruction,
  buildDepositInstruction,
  buildWithdrawInstruction,
  buildOpenTradeInstruction,
  buildCloseTradeInstruction,
  buildSetMbtiStrategyInstruction,
  getIDL,
} from "./instructions";

export {
  solToLamports,
  lamportsToSol,
  bpsToDecimal,
  decimalToBps,
  calculateFee,
  deriveUserAccountPDA,
  deriveTradeVaultPDA,
  deriveProtocolTreasuryPDA,
  deriveMbtiStrategyPDA,
  signMessage,
  verifySignature,
  encodeSignature,
  decodeSignature,
  generateNonce,
  isValidPublicKey,
  shortenAddress,
  generateTradeId,
  withRetry,
  sleep,
  confirmTransaction,
  calculatePnL,
  calculateLiquidationPrice,
  calculatePositionValue,
  calculateMarginRequired,
  formatSol,
  formatUsd,
  calculateSharpeRatio,
  calculateMaxDrawdown,
  PikkyError,
} from "./utils";
