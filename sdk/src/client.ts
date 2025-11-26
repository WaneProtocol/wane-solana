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

export class PikkyClient {
  private readonly connection: Connection;
  private readonly wallet: Keypair;
  private readonly programId: PublicKey;
  private readonly commitment: "processed" | "confirmed" | "finalized";
  private readonly maxRetries: number;
  private readonly retryDelayMs: number;
  private x402Client: X402Client | null;
  private userAccountPDA: PublicKey | null = null;
  private currentStrategy: TradingStrategy | null = null;
  private initialized = false;

  constructor(config: PikkyClientConfig) {
    this.connection = config.connection;
    this.wallet = config.wallet;
    this.programId = config.programId ?? new PublicKey(PIKKY_PROGRAM_ID);
    this.commitment = config.commitment ?? "confirmed";
    this.maxRetries = config.maxRetries ?? 3;
    this.retryDelayMs = config.retryDelayMs ?? 1000;

    if (config.apiEndpoint && config.x402RecipientAddress) {
      this.x402Client = new X402Client({
        connection: this.connection,
        payer: this.wallet,
        recipientAddress: config.x402RecipientAddress,
        apiEndpoint: config.apiEndpoint,
      });
    } else {
      this.x402Client = null;
    }
  }

  get publicKey(): PublicKey {
    return this.wallet.publicKey;
  }

  get isInitialized(): boolean {
    return this.initialized;
  }

  get strategy(): TradingStrategy | null {
    return this.currentStrategy;
  }

  async initialize(mbtiType: MbtiType): Promise<string> {
    const [userAccount, bump] = await deriveUserAccountPDA(
      this.wallet.publicKey,
      this.programId
    );
    this.userAccountPDA = userAccount;

    const instruction = await buildInitializeInstruction(
      this.wallet.publicKey,
      mbtiType,
      this.programId
    );

    const transaction = new Transaction().add(instruction);
    const { blockhash, lastValidBlockHeight } =
      await this.connection.getLatestBlockhash(this.commitment);
    transaction.recentBlockhash = blockhash;
    transaction.lastValidBlockHeight = lastValidBlockHeight;
    transaction.feePayer = this.wallet.publicKey;

    const txSignature = await withRetry(
      () =>
        sendAndConfirmTransaction(
          this.connection,
          transaction,
          [this.wallet],
          { commitment: this.commitment }
        ),
      this.maxRetries,
      this.retryDelayMs
    );

    this.currentStrategy = getStrategy(mbtiType);
    this.initialized = true;

    return txSignature;
  }

  async deposit(params: DepositParams): Promise<string> {
    this.ensureInitialized();

    if (params.amount <= 0) {
      throw new PikkyError("Deposit amount must be positive", "INVALID_AMOUNT");
    }

    const lamports = BigInt(solToLamports(params.amount));

    const balance = await this.connection.getBalance(
      this.wallet.publicKey,
      this.commitment
    );
    const requiredLamports = Number(lamports) + 10_000; // account for fees
    if (balance < requiredLamports) {
      throw new PikkyError(
        `Insufficient balance: have ${lamportsToSol(balance)} SOL, need ${lamportsToSol(requiredLamports)} SOL`,
        "INSUFFICIENT_BALANCE"
      );
    }

    const instruction = await buildDepositInstruction(
      this.wallet.publicKey,
      lamports,
      this.programId
    );

    const transaction = new Transaction().add(instruction);
    const { blockhash, lastValidBlockHeight } =
      await this.connection.getLatestBlockhash(this.commitment);
    transaction.recentBlockhash = blockhash;
    transaction.lastValidBlockHeight = lastValidBlockHeight;
    transaction.feePayer = this.wallet.publicKey;

    const txSignature = await withRetry(
      () =>
        sendAndConfirmTransaction(
          this.connection,
          transaction,
          [this.wallet],
          { commitment: this.commitment }
        ),
      this.maxRetries,
      this.retryDelayMs
    );

    return txSignature;
  }

  async withdraw(params: WithdrawParams): Promise<string> {
    this.ensureInitialized();

    if (params.amount <= 0) {
      throw new PikkyError(
        "Withdrawal amount must be positive",
        "INVALID_AMOUNT"
      );
    }

    const account = await this.getAccountData();
    if (account.balance < params.amount) {
      throw new PikkyError(
        `Insufficient account balance: have ${account.balance} SOL, withdrawing ${params.amount} SOL`,
        "INSUFFICIENT_BALANCE"
      );
    }

    const lamports = BigInt(solToLamports(params.amount));

    const instruction = await buildWithdrawInstruction(
      this.wallet.publicKey,
      lamports,
      this.programId
    );

    const transaction = new Transaction().add(instruction);
    const { blockhash, lastValidBlockHeight } =
      await this.connection.getLatestBlockhash(this.commitment);
    transaction.recentBlockhash = blockhash;
    transaction.lastValidBlockHeight = lastValidBlockHeight;
    transaction.feePayer = this.wallet.publicKey;

    const txSignature = await withRetry(
      () =>
        sendAndConfirmTransaction(
          this.connection,
          transaction,
          [this.wallet],
          { commitment: this.commitment }
        ),
      this.maxRetries,
      this.retryDelayMs
    );

    return txSignature;
  }

  async trade(params: TradeParams): Promise<TradeResult> {
    this.ensureInitialized();

    const strategy = this.currentStrategy!;
    const leverage = params.leverage ?? strategy.defaultLeverage;
    const orderType = params.orderType ?? OrderType.MARKET;
    const tradeId = generateTradeId();

    if (params.size < MIN_TRADE_SIZE_SOL) {
      throw new PikkyError(
        `Trade size must be at least ${MIN_TRADE_SIZE_SOL} SOL`,
        "TRADE_TOO_SMALL"
      );
    }

    if (leverage > strategy.maxLeverage) {
      throw new PikkyError(
        `Leverage ${leverage}x exceeds strategy max of ${strategy.maxLeverage}x for ${strategy.mbtiType}`,
        "LEVERAGE_EXCEEDED"
      );
    }

    if (leverage > MAX_LEVERAGE) {
      throw new PikkyError(
        `Leverage ${leverage}x exceeds protocol max of ${MAX_LEVERAGE}x`,
        "LEVERAGE_EXCEEDED"
      );
    }

    const account = await this.getAccountData();
    const maxPositionSize = account.balance * strategy.maxPositionSizePct;
    if (params.size > maxPositionSize) {
      throw new PikkyError(
        `Position size ${params.size} SOL exceeds max of ${maxPositionSize.toFixed(4)} SOL for ${strategy.mbtiType}`,
        "POSITION_TOO_LARGE"
      );
    }

    const fee = calculateFee(solToLamports(params.size), PROTOCOL_FEE_BPS);

    const sizeLamports = BigInt(solToLamports(params.size));
    const limitPriceLamports = params.limitPrice
      ? BigInt(solToLamports(params.limitPrice))
      : null;
    const stopLossLamports = params.stopLoss
      ? BigInt(solToLamports(params.stopLoss))
      : null;
    const takeProfitLamports = params.takeProfit
      ? BigInt(solToLamports(params.takeProfit))
      : null;

    const instruction = await buildOpenTradeInstruction(
      this.wallet.publicKey,
      tradeId,
      params.tokenMint,
      params.direction,
      sizeLamports,
      leverage,
      orderType,
      limitPriceLamports,
      stopLossLamports,
      takeProfitLamports,
      this.programId
    );

    const transaction = new Transaction().add(instruction);
    const { blockhash, lastValidBlockHeight } =
      await this.connection.getLatestBlockhash(this.commitment);
    transaction.recentBlockhash = blockhash;
    transaction.lastValidBlockHeight = lastValidBlockHeight;
    transaction.feePayer = this.wallet.publicKey;

    try {
      const txSignature = await withRetry(
        () =>
          sendAndConfirmTransaction(
            this.connection,
            transaction,
            [this.wallet],
            { commitment: this.commitment }
          ),
        this.maxRetries,
        this.retryDelayMs
      );

      const position: TradePosition = {
        id: tradeId,
        owner: this.wallet.publicKey,
        tokenMint: params.tokenMint,
        direction: params.direction,
        entryPrice: 0, // set by on-chain oracle
        currentPrice: 0,
        size: params.size,
        leverage,
        margin: params.size / leverage,
        unrealizedPnl: 0,
        realizedPnl: 0,
        status: TradeStatus.OPEN,
        stopLoss: params.stopLoss ?? null,
        takeProfit: params.takeProfit ?? null,
        openedAt: Date.now(),
        closedAt: null,
        txSignature,
      };

      return {
        success: true,
        tradeId,
        txSignature,
        position,
        error: null,
        timestamp: Date.now(),
      };
    } catch (error) {
      const errMsg =
        error instanceof Error ? error.message : String(error);
      return {
        success: false,
        tradeId,
        txSignature: "",
        position: null,
        error: errMsg,
        timestamp: Date.now(),
      };
    }
  }

  async closeTrade(tradeId: string): Promise<TradeResult> {
    this.ensureInitialized();

    const instruction = await buildCloseTradeInstruction(
      this.wallet.publicKey,
      tradeId,
      this.programId
    );

    const transaction = new Transaction().add(instruction);
    const { blockhash, lastValidBlockHeight } =
      await this.connection.getLatestBlockhash(this.commitment);
    transaction.recentBlockhash = blockhash;
    transaction.lastValidBlockHeight = lastValidBlockHeight;
    transaction.feePayer = this.wallet.publicKey;

    try {
      const txSignature = await withRetry(
        () =>
          sendAndConfirmTransaction(
            this.connection,
            transaction,
            [this.wallet],
            { commitment: this.commitment }
          ),
        this.maxRetries,
        this.retryDelayMs
      );

      return {
        success: true,
        tradeId,
        txSignature,
        position: null,
        error: null,
        timestamp: Date.now(),
      };
    } catch (error) {
      const errMsg =
        error instanceof Error ? error.message : String(error);
      return {
        success: false,
        tradeId,
        txSignature: "",
        position: null,
        error: errMsg,
        timestamp: Date.now(),
      };
    }
  }

  async setMbtiStrategy(mbtiType: MbtiType): Promise<string> {
    this.ensureInitialized();

    const instruction = await buildSetMbtiStrategyInstruction(
      this.wallet.publicKey,
      mbtiType,
      this.programId
    );

    const transaction = new Transaction().add(instruction);
    const { blockhash, lastValidBlockHeight } =
      await this.connection.getLatestBlockhash(this.commitment);
    transaction.recentBlockhash = blockhash;
    transaction.lastValidBlockHeight = lastValidBlockHeight;
    transaction.feePayer = this.wallet.publicKey;

    const txSignature = await withRetry(
      () =>
        sendAndConfirmTransaction(
          this.connection,
          transaction,
          [this.wallet],
          { commitment: this.commitment }
        ),
      this.maxRetries,
      this.retryDelayMs
    );

    this.currentStrategy = getStrategy(mbtiType);

    return txSignature;
  }

  async getStatus(query?: StatusQuery): Promise<{
    account: UserAccount;
    positions: TradePosition[];
    pnl: PnLReport | null;
  }> {
    this.ensureInitialized();

    const account = await this.getAccountData();
    let positions: TradePosition[] = [];
    let pnl: PnLReport | null = null;

    if (query?.includePositions !== false) {
      positions = await this.fetchPositions();
    }

    if (query?.includePnl) {
      pnl = await this.calculatePnLReport(
        account,
        positions,
        query.pnlPeriod ?? PnLPeriod.ALL
      );
    }

    return { account, positions, pnl };
  }

  async tradeViaApi(params: TradeParams): Promise<TradeResult> {
    if (!this.x402Client) {
      throw new PikkyError(
        "API endpoint not configured. Pass apiEndpoint and x402RecipientAddress in config.",
        "API_NOT_CONFIGURED"
      );
    }

    const payload = {
      tokenMint: params.tokenMint.toBase58(),
      direction: params.direction,
      size: params.size,
      leverage: params.leverage,
      orderType: params.orderType,
      limitPrice: params.limitPrice,
      stopLoss: params.stopLoss,
      takeProfit: params.takeProfit,
      walletAddress: this.wallet.publicKey.toBase58(),
    };

    return this.x402Client.makePaymentRequest<TradeResult>(
      "POST",
      "/trade/execute",
      payload
    );
  }

  private async getAccountData(): Promise<UserAccount> {
    if (!this.userAccountPDA) {
      const [pda] = await deriveUserAccountPDA(
        this.wallet.publicKey,
        this.programId
      );
      this.userAccountPDA = pda;
    }

    const accountInfo = await this.connection.getAccountInfo(
      this.userAccountPDA,
      this.commitment
    );

    if (!accountInfo) {
      throw new PikkyError(
        "User account not found. Call initialize() first.",
        "ACCOUNT_NOT_FOUND"
      );
    }

    return this.deserializeUserAccount(accountInfo.data);
  }

  private deserializeUserAccount(data: Buffer): UserAccount {
    const DISCRIMINATOR_SIZE = 8;
    let offset = DISCRIMINATOR_SIZE;

    const owner = new PublicKey(data.slice(offset, offset + 32));
    offset += 32;

    const authority = new PublicKey(data.slice(offset, offset + 32));
    offset += 32;

    const mbtiStrLen = data.readUInt32LE(offset);
    offset += 4;
    const mbtiStr = data.slice(offset, offset + mbtiStrLen).toString("utf-8");
    offset += mbtiStrLen;

    const balance = lamportsToSol(Number(data.readBigUInt64LE(offset)));
    offset += 8;

    const lockedBalance = lamportsToSol(
      Number(data.readBigUInt64LE(offset))
    );
    offset += 8;

    const totalDeposited = lamportsToSol(
      Number(data.readBigUInt64LE(offset))
    );
    offset += 8;

    const totalWithdrawn = lamportsToSol(
      Number(data.readBigUInt64LE(offset))
    );
    offset += 8;

    const totalTrades = data.readUInt32LE(offset);
    offset += 4;

    const winningTrades = data.readUInt32LE(offset);
    offset += 4;

    const losingTrades = data.readUInt32LE(offset);
    offset += 4;

    const totalPnl = lamportsToSol(Number(data.readBigInt64LE(offset)));
    offset += 8;

    const createdAt = Number(data.readBigInt64LE(offset));
    offset += 8;

    const lastTradeAt = Number(data.readBigInt64LE(offset));
    offset += 8;

    const accountBump = data.readUInt8(offset);

    return {
      owner,
      authority,
      mbtiType: mbtiStr as MbtiType,
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
      accountBump,
    };
  }

  private async fetchPositions(): Promise<TradePosition[]> {
    if (!this.userAccountPDA) {
      return [];
    }

    const accounts = await this.connection.getProgramAccounts(this.programId, {
      commitment: this.commitment,
      filters: [
        { dataSize: 256 },
        {
          memcmp: {
            offset: 8,
            bytes: this.wallet.publicKey.toBase58(),
          },
        },
      ],
    });

    return accounts.map((acc) => this.deserializeTradePosition(acc.account.data));
  }

  private deserializeTradePosition(data: Buffer): TradePosition {
    const DISCRIMINATOR_SIZE = 8;
    let offset = DISCRIMINATOR_SIZE;

    const idLen = data.readUInt32LE(offset);
    offset += 4;
    const id = data.slice(offset, offset + idLen).toString("utf-8");
    offset += idLen;

    const owner = new PublicKey(data.slice(offset, offset + 32));
    offset += 32;

    const tokenMint = new PublicKey(data.slice(offset, offset + 32));
    offset += 32;

    const directionByte = data.readUInt8(offset);
    offset += 1;
    const direction =
      directionByte === 0 ? TradeDirection.LONG : TradeDirection.SHORT;

    const entryPrice = lamportsToSol(Number(data.readBigUInt64LE(offset)));
    offset += 8;

    const currentPrice = lamportsToSol(Number(data.readBigUInt64LE(offset)));
    offset += 8;

    const size = lamportsToSol(Number(data.readBigUInt64LE(offset)));
    offset += 8;

    const leverage = data.readUInt8(offset);
    offset += 1;

    const margin = lamportsToSol(Number(data.readBigUInt64LE(offset)));
    offset += 8;

    const unrealizedPnl = lamportsToSol(
      Number(data.readBigInt64LE(offset))
    );
    offset += 8;

    const realizedPnl = lamportsToSol(Number(data.readBigInt64LE(offset)));
    offset += 8;

    const statusByte = data.readUInt8(offset);
    offset += 1;
    const statusMap: Record<number, TradeStatus> = {
      0: TradeStatus.PENDING,
      1: TradeStatus.OPEN,
      2: TradeStatus.CLOSED,
      3: TradeStatus.LIQUIDATED,
      4: TradeStatus.CANCELLED,
    };
    const status = statusMap[statusByte] ?? TradeStatus.PENDING;

    const hasStopLoss = data.readUInt8(offset) === 1;
    offset += 1;
    const stopLoss = hasStopLoss
      ? lamportsToSol(Number(data.readBigUInt64LE(offset)))
      : null;
    offset += 8;

    const hasTakeProfit = data.readUInt8(offset) === 1;
    offset += 1;
    const takeProfit = hasTakeProfit
      ? lamportsToSol(Number(data.readBigUInt64LE(offset)))
      : null;
    offset += 8;

    const openedAt = Number(data.readBigInt64LE(offset));
    offset += 8;

    const hasClosedAt = data.readUInt8(offset) === 1;
    offset += 1;
    const closedAt = hasClosedAt
      ? Number(data.readBigInt64LE(offset))
      : null;
    offset += 8;

    const sigLen = data.readUInt32LE(offset);
    offset += 4;
    const txSignature = data.slice(offset, offset + sigLen).toString("utf-8");

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
      txSignature,
    };
  }

  private async calculatePnLReport(
    account: UserAccount,
    positions: TradePosition[],
    period: PnLPeriod
  ): Promise<PnLReport> {
    const now = Date.now();
    const periodMs = this.getPeriodMs(period);
    const cutoff = periodMs === 0 ? 0 : now - periodMs;

    const relevantPositions = positions.filter(
      (p) => p.openedAt >= cutoff
    );

    const realizedPnl = relevantPositions
      .filter((p) => p.status === TradeStatus.CLOSED)
      .reduce((sum, p) => sum + p.realizedPnl, 0);

    const unrealizedPnl = relevantPositions
      .filter((p) => p.status === TradeStatus.OPEN)
      .reduce((sum, p) => sum + p.unrealizedPnl, 0);

    const totalPnl = realizedPnl + unrealizedPnl;
    const closedPositions = relevantPositions.filter(
      (p) => p.status === TradeStatus.CLOSED
    );
    const winningCount = closedPositions.filter(
      (p) => p.realizedPnl > 0
    ).length;
    const winRate =
      closedPositions.length > 0 ? winningCount / closedPositions.length : 0;

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

    const sharpeRatio = this.computeSharpe(returns);
    const equityCurve = this.buildEquityCurve(
      account.totalDeposited,
      closedPositions
    );
    const maxDrawdown = this.computeMaxDrawdown(equityCurve);

    const peakEquity = equityCurve.length > 0 ? Math.max(...equityCurve) : 0;
    const currentEquity =
      equityCurve.length > 0 ? equityCurve[equityCurve.length - 1] : 0;
    const currentDrawdown =
      peakEquity > 0 ? (peakEquity - currentEquity) / peakEquity : 0;

    return {
      owner: this.wallet.publicKey,
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
      positions: relevantPositions,
      generatedAt: now,
    };
  }

  private getPeriodMs(period: PnLPeriod): number {
    switch (period) {
      case PnLPeriod.HOUR:
        return 3_600_000;
      case PnLPeriod.DAY:
        return 86_400_000;
      case PnLPeriod.WEEK:
        return 7 * 86_400_000;
      case PnLPeriod.MONTH:
        return 30 * 86_400_000;
      case PnLPeriod.ALL:
        return 0;
    }
  }

  private computeSharpe(returns: number[]): number {
    if (returns.length < 2) return 0;
    const mean = returns.reduce((s, r) => s + r, 0) / returns.length;
    const variance =
      returns.reduce((s, r) => s + Math.pow(r - mean, 2), 0) /
      (returns.length - 1);
    const stdDev = Math.sqrt(variance);
    return stdDev === 0 ? 0 : mean / stdDev;
  }

  private buildEquityCurve(
    initialBalance: number,
    closedPositions: TradePosition[]
  ): number[] {
    const sorted = [...closedPositions].sort(
      (a, b) => (a.closedAt ?? 0) - (b.closedAt ?? 0)
    );
    const curve: number[] = [initialBalance];
    let running = initialBalance;
    for (const pos of sorted) {
      running += pos.realizedPnl;
      curve.push(running);
    }
    return curve;
  }

  private computeMaxDrawdown(equityCurve: number[]): number {
    if (equityCurve.length < 2) return 0;
    let maxDD = 0;
    let peak = equityCurve[0];
    for (const val of equityCurve) {
      if (val > peak) peak = val;
      const dd = (peak - val) / peak;
      if (dd > maxDD) maxDD = dd;
    }
    return maxDD;
  }

  private ensureInitialized(): void {
    if (!this.initialized) {
      throw new PikkyError(
        "Client not initialized. Call initialize() first.",
        "NOT_INITIALIZED"
      );
    }
  }
}

