import {
  Connection,
  PublicKey,
  SystemProgram,
  Transaction,
  TransactionInstruction,
  Keypair,
  sendAndConfirmTransaction,
} from "@solana/web3.js";
import axios, { AxiosInstance, AxiosResponse, AxiosError } from "axios";
import {
  X402Payment,
  X402PaymentHeader,
  X402PaymentReceipt,
  X402_VERSION,
  X402_SCHEME,
  LAMPORTS_PER_SOL,
} from "./types";
import {
  generateNonce,
  solToLamports,
  lamportsToSol,
  encodeSignature,
  PikkyError,
  withRetry,
  confirmTransaction,
} from "./utils";

export interface X402Config {
  connection: Connection;
  payer: Keypair;
  recipientAddress: string;
  apiEndpoint: string;
  timeoutMs?: number;
}

export class X402Client {
  private readonly connection: Connection;
  private readonly payer: Keypair;
  private readonly recipientPubkey: PublicKey;
  private readonly apiEndpoint: string;
  private readonly httpClient: AxiosInstance;
  private readonly timeoutMs: number;

  constructor(config: X402Config) {
    this.connection = config.connection;
    this.payer = config.payer;
    this.recipientPubkey = new PublicKey(config.recipientAddress);
    this.apiEndpoint = config.apiEndpoint.replace(/\/$/, "");
    this.timeoutMs = config.timeoutMs ?? 30_000;

    this.httpClient = axios.create({
      baseURL: this.apiEndpoint,
      timeout: this.timeoutMs,
      headers: {
        "Content-Type": "application/json",
        "X-Protocol-Version": X402_VERSION,
      },
    });
  }

  async makePaymentRequest<T>(
    method: "GET" | "POST",
    path: string,
    data?: unknown
  ): Promise<T> {
    try {
      const response = await this.httpClient.request<T>({
        method,
        url: path,
        data,
      });
      return response.data;
    } catch (error) {
      if (!isAxiosError(error) || !error.response) {
        throw new PikkyError(
          `Network error calling ${path}: ${error instanceof Error ? error.message : String(error)}`,
          "NETWORK_ERROR"
        );
      }

      const res = error.response;

      if (res.status !== 402) {
        throw new PikkyError(
          `API error ${res.status}: ${JSON.stringify(res.data)}`,
          "API_ERROR"
        );
      }

      const paymentDetails = this.parsePaymentRequired(res);
      const receipt = await this.executePayment(paymentDetails);
      const paymentHeader = this.buildPaymentHeader(receipt, paymentDetails);

      const paidResponse = await this.httpClient.request<T>({
        method,
        url: path,
        data,
        headers: {
          ...this.serializePaymentHeader(paymentHeader),
        },
      });

      return paidResponse.data;
    }
  }

  parsePaymentRequired(response: AxiosResponse): X402Payment {
    const headers = response.headers;
    const body = response.data as Record<string, unknown>;

    const paymentAmount =
      parseFloat(headers["x-payment-amount"] as string) ||
      (body.paymentAmount as number) ||
      0;

    const recipientAddress =
      (headers["x-payment-recipient"] as string) ||
      (body.recipientAddress as string) ||
      this.recipientPubkey.toBase58();

    const expiresAt =
      parseInt(headers["x-payment-expiry"] as string, 10) ||
      (body.expiresAt as number) ||
      Date.now() + 300_000;

    const nonce =
      (headers["x-payment-nonce"] as string) ||
      (body.nonce as string) ||
      generateNonce();

    const payload =
      (body.payload as string) || "";

    return {
      version: X402_VERSION,
      network: "solana",
      paymentToken: "SOL",
      paymentAmount,
      payerAddress: this.payer.publicKey.toBase58(),
      recipientAddress,
      txSignature: null,
      expiresAt,
      nonce,
      payload,
    };
  }

  async executePayment(payment: X402Payment): Promise<X402PaymentReceipt> {
    if (Date.now() > payment.expiresAt) {
      throw new PikkyError("Payment request has expired", "PAYMENT_EXPIRED");
    }

    const lamports = solToLamports(payment.paymentAmount);
    const recipient = new PublicKey(payment.recipientAddress);

    const paymentMemo = this.buildPaymentMemo(payment);

    const transaction = new Transaction();

    transaction.add(
      SystemProgram.transfer({
        fromPubkey: this.payer.publicKey,
        toPubkey: recipient,
        lamports,
      })
    );

    transaction.add(
      new TransactionInstruction({
        keys: [
          { pubkey: this.payer.publicKey, isSigner: true, isWritable: false },
        ],
        programId: new PublicKey(
          "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"
        ),
        data: Buffer.from(paymentMemo),
      })
    );

    const { blockhash, lastValidBlockHeight } =
      await this.connection.getLatestBlockhash("confirmed");
    transaction.recentBlockhash = blockhash;
    transaction.lastValidBlockHeight = lastValidBlockHeight;
    transaction.feePayer = this.payer.publicKey;

    const txSignature = await withRetry(
      () =>
        sendAndConfirmTransaction(this.connection, transaction, [this.payer], {
          commitment: "confirmed",
          maxRetries: 3,
        }),
      2,
      1000
    );

    const confirmed = await confirmTransaction(
      this.connection,
      txSignature,
      "confirmed",
      this.timeoutMs
    );

    if (!confirmed) {
      throw new PikkyError(
        "Payment transaction not confirmed",
        "PAYMENT_UNCONFIRMED"
      );
    }

    const txInfo = await this.connection.getTransaction(txSignature, {
      commitment: "confirmed",
    });

    return {
      valid: true,
      txSignature,
      amount: payment.paymentAmount,
      payer: payment.payerAddress,
      recipient: payment.recipientAddress,
      confirmedAt: Date.now(),
      blockSlot: txInfo?.slot ?? 0,
    };
  }

  buildPaymentHeader(
    receipt: X402PaymentReceipt,
    payment: X402Payment
  ): X402PaymentHeader {
    return {
      scheme: X402_SCHEME,
      token: payment.paymentToken,
      amount: payment.paymentAmount.toString(),
      payer: receipt.payer,
      recipient: receipt.recipient,
      signature: receipt.txSignature,
      nonce: payment.nonce,
      expiry: payment.expiresAt.toString(),
    };
  }

  serializePaymentHeader(header: X402PaymentHeader): Record<string, string> {
    const encodedHeader = Buffer.from(
      JSON.stringify({
        scheme: header.scheme,
        token: header.token,
        amount: header.amount,
        payer: header.payer,
        recipient: header.recipient,
        nonce: header.nonce,
        expiry: header.expiry,
      })
    ).toString("base64");

    return {
      "X-Payment-Scheme": header.scheme,
      "X-Payment-Token": header.token,
      "X-Payment-Amount": header.amount,
      "X-Payment-Payer": header.payer,
      "X-Payment-Recipient": header.recipient,
      "X-Payment-Signature": header.signature,
      "X-Payment-Nonce": header.nonce,
      "X-Payment-Expiry": header.expiry,
      Authorization: `${X402_SCHEME} ${encodedHeader}`,
      "X-Payment-Tx": header.signature,
    };
  }

  private buildPaymentMemo(payment: X402Payment): string {
    return JSON.stringify({
      protocol: "x402",
      version: payment.version,
      nonce: payment.nonce,
      payload: payment.payload,
      timestamp: Date.now(),
    });
  }

  async verifyPaymentOnChain(
    txSignature: string,
    expectedAmount: number,
    expectedRecipient: string
  ): Promise<X402PaymentReceipt> {
    const txInfo = await withRetry(
      () =>
        this.connection.getTransaction(txSignature, {
          commitment: "confirmed",
          maxSupportedTransactionVersion: 0,
        }),
      3,
      1000
    );

    if (!txInfo) {
      throw new PikkyError(
        `Transaction not found: ${txSignature}`,
        "TX_NOT_FOUND"
      );
    }

    if (txInfo.meta?.err) {
      throw new PikkyError(
        `Transaction failed: ${JSON.stringify(txInfo.meta.err)}`,
        "TX_FAILED"
      );
    }

    const preBalances = txInfo.meta?.preBalances ?? [];
    const postBalances = txInfo.meta?.postBalances ?? [];
    const accountKeys =
      txInfo.transaction.message.getAccountKeys().staticAccountKeys;

    let payerAddress = "";
    let recipientFound = false;
    let transferAmount = 0;

    for (let i = 0; i < accountKeys.length; i++) {
      const key = accountKeys[i].toBase58();
      const balanceDelta = (postBalances[i] ?? 0) - (preBalances[i] ?? 0);

      if (key === expectedRecipient && balanceDelta > 0) {
        recipientFound = true;
        transferAmount = lamportsToSol(balanceDelta);
      }

      if (balanceDelta < 0 && payerAddress === "") {
        payerAddress = key;
      }
    }

    if (!recipientFound) {
      throw new PikkyError(
        "Payment recipient not found in transaction",
        "INVALID_RECIPIENT"
      );
    }

    if (transferAmount < expectedAmount * 0.999) {
      throw new PikkyError(
        `Insufficient payment: expected ${expectedAmount} SOL, got ${transferAmount} SOL`,
        "INSUFFICIENT_PAYMENT"
      );
    }

    return {
      valid: true,
      txSignature,
      amount: transferAmount,
      payer: payerAddress,
      recipient: expectedRecipient,
      confirmedAt: (txInfo.blockTime ?? 0) * 1000,
      blockSlot: txInfo.slot,
    };
  }

  static buildPaymentRequiredResponse(
    amount: number,
    recipientAddress: string,
    payload: string = "",
    ttlMs: number = 300_000
  ): {
    status: 402;
    headers: Record<string, string>;
    body: Record<string, unknown>;
  } {
    const nonce = generateNonce();
    const expiresAt = Date.now() + ttlMs;

    return {
      status: 402,
      headers: {
        "X-Payment-Amount": amount.toString(),
        "X-Payment-Recipient": recipientAddress,
        "X-Payment-Expiry": expiresAt.toString(),
        "X-Payment-Nonce": nonce,
        "X-Payment-Network": "solana",
        "X-Payment-Token": "SOL",
        "X-Payment-Version": X402_VERSION,
      },
      body: {
        error: "Payment Required",
        message: `This endpoint requires a payment of ${amount} SOL`,
        paymentAmount: amount,
        recipientAddress,
        nonce,
        expiresAt,
        payload,
        network: "solana",
        token: "SOL",
        version: X402_VERSION,
      },
    };
  }

  static parsePaymentHeader(
    headers: Record<string, string | undefined>
  ): X402PaymentHeader | null {
    const scheme = headers["x-payment-scheme"];
    const signature = headers["x-payment-signature"] || headers["x-payment-tx"];

    if (!scheme || !signature) {
      const auth = headers["authorization"];
      if (!auth || !auth.startsWith(X402_SCHEME)) {
        return null;
      }

      const encoded = auth.slice(X402_SCHEME.length + 1);
      try {
        const decoded = JSON.parse(
          Buffer.from(encoded, "base64").toString("utf-8")
        );
        return {
          scheme: decoded.scheme ?? X402_SCHEME,
          token: decoded.token ?? "SOL",
          amount: decoded.amount ?? "0",
          payer: decoded.payer ?? "",
          recipient: decoded.recipient ?? "",
          signature: headers["x-payment-tx"] ?? "",
          nonce: decoded.nonce ?? "",
          expiry: decoded.expiry ?? "0",
        };
      } catch {
        return null;
      }
    }

    return {
      scheme: scheme ?? X402_SCHEME,
      token: headers["x-payment-token"] ?? "SOL",
      amount: headers["x-payment-amount"] ?? "0",
      payer: headers["x-payment-payer"] ?? "",
      recipient: headers["x-payment-recipient"] ?? "",
      signature,
      nonce: headers["x-payment-nonce"] ?? "",
      expiry: headers["x-payment-expiry"] ?? "0",
    };
  }
}

function isAxiosError(error: unknown): error is AxiosError {
  return (
    typeof error === "object" &&
    error !== null &&
    "isAxiosError" in error &&
    (error as AxiosError).isAxiosError === true
  );
}

