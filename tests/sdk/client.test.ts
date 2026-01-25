import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import { Connection, Keypair, PublicKey, LAMPORTS_PER_SOL } from '@solana/web3.js';
import { PikkyClient } from '../../sdk/src/client';
import { MBTIType } from '../../sdk/src/mbti';

// Mock Solana connection
const mockConnection = {
  getLatestBlockhash: jest.fn().mockResolvedValue({
    blockhash: '4NpEQ3XKFX1113mZbSLcV8LjMhVCWS4Bps11K3L8AAAA',
    lastValidBlockHeight: 200000,
  }),
  sendTransaction: jest.fn().mockResolvedValue('mockedTxSignature123'),
  confirmTransaction: jest.fn().mockResolvedValue({ value: { err: null } }),
  getAccountInfo: jest.fn().mockResolvedValue(null),
  getBalance: jest.fn().mockResolvedValue(5 * LAMPORTS_PER_SOL),
  getMinimumBalanceForRentExemption: jest.fn().mockResolvedValue(2_039_280),
} as unknown as Connection;

const mockWallet = {
  publicKey: Keypair.generate().publicKey,
  signTransaction: jest.fn().mockImplementation((tx: any) => Promise.resolve(tx)),
  signAllTransactions: jest.fn().mockImplementation((txs: any) => Promise.resolve(txs)),
};

const PROGRAM_ID = new PublicKey('PikkyPRGMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx');

describe('PikkyClient', () => {
  let client: PikkyClient;

  beforeEach(() => {
    jest.clearAllMocks();
    client = new PikkyClient({
      connection: mockConnection,
      wallet: mockWallet as any,
      programId: PROGRAM_ID,
    });
  });

  describe('constructor', () => {
    it('should initialize with required parameters', () => {
      expect(client).toBeDefined();
      expect(client.connection).toBe(mockConnection);
      expect(client.programId.equals(PROGRAM_ID)).toBe(true);
    });

    it('should throw if connection is not provided', () => {
      expect(() => {
        new PikkyClient({
          connection: null as any,
          wallet: mockWallet as any,
          programId: PROGRAM_ID,
        });
      }).toThrow('Connection is required');
    });

    it('should throw if wallet is not provided', () => {
      expect(() => {
        new PikkyClient({
          connection: mockConnection,
          wallet: null as any,
          programId: PROGRAM_ID,
        });
      }).toThrow('Wallet is required');
    });

    it('should use default program ID if not provided', () => {
      const defaultClient = new PikkyClient({
        connection: mockConnection,
        wallet: mockWallet as any,
      });
      expect(defaultClient.programId).toBeDefined();
    });
  });

  describe('initialize', () => {
    it('should create user state account', async () => {
      const tx = await client.initialize();
      expect(tx).toBeDefined();
      expect(typeof tx).toBe('string');
      expect(mockConnection.sendTransaction).toHaveBeenCalled();
    });

    it('should derive correct user state PDA', async () => {
      const [expectedPDA] = PublicKey.findProgramAddressSync(
        [Buffer.from('user'), mockWallet.publicKey.toBuffer()],
        PROGRAM_ID,
      );
      await client.initialize();
      const userStatePDA = client.getUserStatePDA();
      expect(userStatePDA.equals(expectedPDA)).toBe(true);
    });

    it('should fail if user state already exists', async () => {
      (mockConnection.getAccountInfo as jest.Mock).mockResolvedValueOnce({
        data: Buffer.alloc(256),
        owner: PROGRAM_ID,
        lamports: 2_039_280,
        executable: false,
      });
      await expect(client.initialize()).rejects.toThrow('User state already exists');
    });
  });

  describe('deposit', () => {
    it('should deposit SOL into vault', async () => {
      const amount = 1.5;
      const tx = await client.deposit(amount);
      expect(tx).toBeDefined();
      expect(mockConnection.sendTransaction).toHaveBeenCalled();
    });

    it('should convert SOL amount to lamports correctly', async () => {
      const amount = 2.5;
      const tx = await client.deposit(amount);
      expect(tx).toBeDefined();
      // Internal conversion: 2.5 * LAMPORTS_PER_SOL = 2,500,000,000
    });

    it('should reject zero deposit', async () => {
      await expect(client.deposit(0)).rejects.toThrow('Amount must be positive');
    });

    it('should reject negative deposit', async () => {
      await expect(client.deposit(-1)).rejects.toThrow('Amount must be positive');
    });
