import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import { Connection, Keypair, PublicKey, LAMPORTS_PER_SOL } from '@solana/web3.js';
import {
  X402Client,
  X402PaymentRequest,
  X402PaymentResponse,
  parsePaymentHeaders,
  buildPaymentTransaction,
  verifyPaymentReceipt,
} from '../../sdk/src/x402';

const mockConnection = {
  getLatestBlockhash: jest.fn().mockResolvedValue({
    blockhash: '4NpEQ3XKFX1113mZbSLcV8LjMhVCWS4Bps11K3L8AAAA',
    lastValidBlockHeight: 200000,
  }),
  sendTransaction: jest.fn().mockResolvedValue('paymentTxSig456'),
  confirmTransaction: jest.fn().mockResolvedValue({ value: { err: null } }),
  getTransaction: jest.fn().mockResolvedValue({
    meta: { err: null },
    transaction: {
      message: {
        accountKeys: [
          Keypair.generate().publicKey,
          new PublicKey('PikkyVau1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'),
        ],
      },
    },
  }),
} as unknown as Connection;

const VAULT_ADDRESS = new PublicKey('PikkyVau1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX');
const TEST_NONCE = 'a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6';

describe('x402 Payment Flow', () => {
  describe('parsePaymentHeaders', () => {
    it('should parse valid 402 response headers', () => {
      const headers = new Map<string, string>([
        ['x-payment-version', 'x402/1.0'],
        ['x-payment-network', 'solana:devnet'],
        ['x-payment-amount', '10000000'],
        ['x-payment-token-mint', 'So11111111111111111111111111111111111111112'],
        ['x-payment-address', VAULT_ADDRESS.toBase58()],
        ['x-payment-nonce', TEST_NONCE],
        ['x-payment-expires', '1735689600'],
        ['x-payment-description', 'AI trade execution'],
      ]);

      const request = parsePaymentHeaders(headers);
      expect(request.version).toBe('x402/1.0');
      expect(request.network).toBe('solana:devnet');
      expect(request.amount).toBe(10_000_000);
      expect(request.tokenMint).toBe('So11111111111111111111111111111111111111112');
      expect(request.address).toBe(VAULT_ADDRESS.toBase58());
      expect(request.nonce).toBe(TEST_NONCE);
      expect(request.expiresAt).toBe(1735689600);
      expect(request.description).toBe('AI trade execution');
    });

    it('should throw if required headers are missing', () => {
      const incompleteHeaders = new Map<string, string>([
        ['x-payment-version', 'x402/1.0'],
        // missing other required headers
      ]);
      expect(() => parsePaymentHeaders(incompleteHeaders)).toThrow(
        'Missing required payment header',
      );
    });

    it('should throw if amount is not a valid number', () => {
      const headers = new Map<string, string>([
        ['x-payment-version', 'x402/1.0'],
        ['x-payment-network', 'solana:devnet'],
        ['x-payment-amount', 'not-a-number'],
        ['x-payment-token-mint', 'So11111111111111111111111111111111111111112'],
        ['x-payment-address', VAULT_ADDRESS.toBase58()],
        ['x-payment-nonce', TEST_NONCE],
        ['x-payment-expires', '1735689600'],
      ]);
      expect(() => parsePaymentHeaders(headers)).toThrow('Invalid payment amount');
    });

    it('should throw if amount is zero', () => {
      const headers = new Map<string, string>([
        ['x-payment-version', 'x402/1.0'],
        ['x-payment-network', 'solana:devnet'],
        ['x-payment-amount', '0'],
        ['x-payment-token-mint', 'So11111111111111111111111111111111111111112'],
        ['x-payment-address', VAULT_ADDRESS.toBase58()],
        ['x-payment-nonce', TEST_NONCE],
        ['x-payment-expires', '1735689600'],
      ]);
      expect(() => parsePaymentHeaders(headers)).toThrow('Invalid payment amount');
    });

    it('should throw if version is unsupported', () => {
      const headers = new Map<string, string>([
        ['x-payment-version', 'x402/99.0'],
        ['x-payment-network', 'solana:devnet'],
        ['x-payment-amount', '10000000'],
        ['x-payment-token-mint', 'So11111111111111111111111111111111111111112'],
        ['x-payment-address', VAULT_ADDRESS.toBase58()],
        ['x-payment-nonce', TEST_NONCE],
        ['x-payment-expires', '1735689600'],
      ]);
      expect(() => parsePaymentHeaders(headers)).toThrow('Unsupported x402 version');
    });
  });

  describe('buildPaymentTransaction', () => {
    it('should build SOL transfer transaction with memo', async () => {
      const payer = Keypair.generate();
      const request: X402PaymentRequest = {
        version: 'x402/1.0',
        network: 'solana:devnet',
        amount: 10_000_000,
        tokenMint: 'So11111111111111111111111111111111111111112',
        address: VAULT_ADDRESS.toBase58(),
        nonce: TEST_NONCE,
        expiresAt: Math.floor(Date.now() / 1000) + 300,
      };

      const transaction = await buildPaymentTransaction(
        mockConnection,
        payer.publicKey,
        request,
      );
      expect(transaction).toBeDefined();
      expect(transaction.instructions.length).toBeGreaterThanOrEqual(2);
    });

    it('should include nonce in memo instruction', async () => {
      const payer = Keypair.generate();
      const request: X402PaymentRequest = {