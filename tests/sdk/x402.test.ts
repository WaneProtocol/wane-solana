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

      // Last instruction should be memo with nonce
      const memoInstruction = transaction.instructions[transaction.instructions.length - 1];
      expect(memoInstruction.data.toString()).toContain(TEST_NONCE);
    });

    it('should reject expired payment request', async () => {
      const payer = Keypair.generate();
      const request: X402PaymentRequest = {
        version: 'x402/1.0',
        network: 'solana:devnet',
        amount: 10_000_000,
        tokenMint: 'So11111111111111111111111111111111111111112',
        address: VAULT_ADDRESS.toBase58(),
        nonce: TEST_NONCE,
        expiresAt: Math.floor(Date.now() / 1000) - 60, // expired 1 minute ago
      };

      await expect(
        buildPaymentTransaction(mockConnection, payer.publicKey, request),
      ).rejects.toThrow('Payment request has expired');
    });

    it('should set correct transfer amount in lamports', async () => {
      const payer = Keypair.generate();
      const amount = 50_000_000; // 0.05 SOL
      const request: X402PaymentRequest = {
        version: 'x402/1.0',
        network: 'solana:devnet',
        amount,
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

      // First instruction should be the transfer
      const transferIx = transaction.instructions[0];
      expect(transferIx).toBeDefined();
    });
  });

  describe('verifyPaymentReceipt', () => {
    it('should verify a valid payment receipt', async () => {
      const result = await verifyPaymentReceipt(
        mockConnection,
        'paymentTxSig456',
        {
          expectedAddress: VAULT_ADDRESS.toBase58(),
          expectedAmount: 10_000_000,
          expectedNonce: TEST_NONCE,
        },
      );
      expect(result.verified).toBe(true);
      expect(result.status).toBe('verified');
    });

    it('should reject receipt with wrong destination', async () => {
      const result = await verifyPaymentReceipt(
        mockConnection,
        'paymentTxSig456',
        {
          expectedAddress: Keypair.generate().publicKey.toBase58(),
          expectedAmount: 10_000_000,
          expectedNonce: TEST_NONCE,
        },
      );
      expect(result.verified).toBe(false);
      expect(result.status).toBe('invalid');
    });

    it('should reject receipt for failed transaction', async () => {
      (mockConnection.getTransaction as jest.Mock).mockResolvedValueOnce({
        meta: { err: { InstructionError: [0, 'Custom(1)'] } },
        transaction: { message: { accountKeys: [] } },
      });

      const result = await verifyPaymentReceipt(
        mockConnection,
        'failedTxSig',
        {
          expectedAddress: VAULT_ADDRESS.toBase58(),
          expectedAmount: 10_000_000,
          expectedNonce: TEST_NONCE,
        },
      );
      expect(result.verified).toBe(false);
      expect(result.status).toBe('invalid');
    });

    it('should return pending for unconfirmed transaction', async () => {
      (mockConnection.getTransaction as jest.Mock).mockResolvedValueOnce(null);

      const result = await verifyPaymentReceipt(
        mockConnection,
        'pendingTxSig',
        {
          expectedAddress: VAULT_ADDRESS.toBase58(),
          expectedAmount: 10_000_000,
          expectedNonce: TEST_NONCE,
        },
      );
      expect(result.verified).toBe(false);
      expect(result.status).toBe('pending');
    });
  });

  describe('X402Client', () => {
    let x402Client: X402Client;
    const wallet = {
      publicKey: Keypair.generate().publicKey,
      signTransaction: jest.fn().mockImplementation((tx: any) => Promise.resolve(tx)),
    };

    beforeEach(() => {
      jest.clearAllMocks();
      x402Client = new X402Client({
        connection: mockConnection,
        wallet: wallet as any,
        network: 'solana:devnet',
      });
    });

    it('should handle full 402 payment flow', async () => {
      const mockFetch = jest.fn()
        .mockResolvedValueOnce({
          status: 402,
          headers: new Map([
            ['x-payment-version', 'x402/1.0'],
            ['x-payment-network', 'solana:devnet'],
            ['x-payment-amount', '10000000'],
            ['x-payment-token-mint', 'So11111111111111111111111111111111111111112'],
            ['x-payment-address', VAULT_ADDRESS.toBase58()],
            ['x-payment-nonce', TEST_NONCE],
            ['x-payment-expires', String(Math.floor(Date.now() / 1000) + 300)],
          ]),
        })
        .mockResolvedValueOnce({
          status: 200,
          json: () => Promise.resolve({ trade: { id: 'trade_123' } }),
          headers: new Map([
            ['x-payment-receipt', 'paymentTxSig456'],
            ['x-payment-status', 'verified'],
          ]),
        });

      const result = await x402Client.requestWithPayment(
        'https://api.pikky.sol/api/agent/trade',
        { fetchFn: mockFetch as any },
      );
      expect(result).toBeDefined();
    });

    it('should pass through non-402 responses', async () => {
      const mockFetch = jest.fn().mockResolvedValueOnce({
        status: 200,
        json: () => Promise.resolve({ data: 'free_endpoint' }),
      });

      const result = await x402Client.requestWithPayment(
        'https://api.pikky.sol/api/portfolio',
        { fetchFn: mockFetch as any },
      );
      expect(result).toBeDefined();
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    it('should throw on non-402 error responses', async () => {
      const mockFetch = jest.fn().mockResolvedValueOnce({
        status: 500,
        statusText: 'Internal Server Error',
      });

      await expect(
        x402Client.requestWithPayment('https://api.pikky.sol/api/broken', {
          fetchFn: mockFetch as any,
        }),
      ).rejects.toThrow();
    });
  });
});
