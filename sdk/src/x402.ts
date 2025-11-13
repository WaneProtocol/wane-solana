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
