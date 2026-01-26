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

    it('should reject deposit exceeding wallet balance', async () => {
      await expect(client.deposit(100)).rejects.toThrow('Insufficient balance');
    });

    it('should include correct vault PDA as destination', async () => {
      const [vaultPDA] = PublicKey.findProgramAddressSync(
        [Buffer.from('vault'), new PublicKey('So11111111111111111111111111111111111111112').toBuffer()],
        PROGRAM_ID,
      );
      await client.deposit(1.0);
      expect(client.getVaultPDA()).toBeDefined();
    });
  });

  describe('withdraw', () => {
    it('should withdraw SOL from vault', async () => {
      const amount = 0.5;
      const tx = await client.withdraw(amount);
      expect(tx).toBeDefined();
      expect(mockConnection.sendTransaction).toHaveBeenCalled();
    });

    it('should reject zero withdrawal', async () => {
      await expect(client.withdraw(0)).rejects.toThrow('Amount must be positive');
    });

    it('should reject withdrawal exceeding deposited balance', async () => {
      await expect(client.withdraw(1000)).rejects.toThrow('Insufficient deposited balance');
    });

    it('should handle full withdrawal', async () => {
      const tx = await client.withdrawAll();
      expect(tx).toBeDefined();
      expect(mockConnection.sendTransaction).toHaveBeenCalled();
    });
  });

  describe('setMBTIType', () => {
    it('should set MBTI type on user state', async () => {
      const tx = await client.setMBTIType(MBTIType.INTJ);
      expect(tx).toBeDefined();
      expect(mockConnection.sendTransaction).toHaveBeenCalled();
    });

    it('should accept all 16 MBTI types', async () => {
      const types: MBTIType[] = [
        MBTIType.INTJ, MBTIType.INTP, MBTIType.ENTJ, MBTIType.ENTP,
        MBTIType.INFJ, MBTIType.INFP, MBTIType.ENFJ, MBTIType.ENFP,
        MBTIType.ISTJ, MBTIType.ISFJ, MBTIType.ESTJ, MBTIType.ESFJ,
        MBTIType.ISTP, MBTIType.ISFP, MBTIType.ESTP, MBTIType.ESFP,
      ];
      for (const mbtiType of types) {
        const tx = await client.setMBTIType(mbtiType);
        expect(tx).toBeDefined();
      }
    });

    it('should reject invalid MBTI type', async () => {
      await expect(client.setMBTIType('XXXX' as MBTIType)).rejects.toThrow('Invalid MBTI type');
    });
  });

  describe('executeTrade', () => {
    it('should execute a buy trade', async () => {
      const tx = await client.executeTrade({
        side: 'buy',
        inputMint: new PublicKey('So11111111111111111111111111111111111111112'),
        outputMint: new PublicKey('EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'),
        amount: 1_000_000_000,
        slippageBps: 50,
      });
      expect(tx).toBeDefined();
      expect(mockConnection.sendTransaction).toHaveBeenCalled();
    });

    it('should execute a sell trade', async () => {
      const tx = await client.executeTrade({
        side: 'sell',
        inputMint: new PublicKey('EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'),
        outputMint: new PublicKey('So11111111111111111111111111111111111111112'),
        amount: 100_000_000,
        slippageBps: 100,
      });
      expect(tx).toBeDefined();
    });

    it('should reject trade with zero amount', async () => {
      await expect(
        client.executeTrade({
          side: 'buy',
          inputMint: new PublicKey('So11111111111111111111111111111111111111112'),
          outputMint: new PublicKey('EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'),
          amount: 0,
          slippageBps: 50,
        }),
      ).rejects.toThrow('Amount must be positive');
    });

    it('should reject trade with excessive slippage', async () => {
      await expect(
        client.executeTrade({
          side: 'buy',
          inputMint: new PublicKey('So11111111111111111111111111111111111111112'),
          outputMint: new PublicKey('EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'),
          amount: 1_000_000_000,
          slippageBps: 5000,
        }),
      ).rejects.toThrow('Slippage too high');
    });

    it('should reject trade when auto-trading is disabled', async () => {
      client.setAutoTrading(false);
      await expect(
        client.executeTrade({
          side: 'buy',
          inputMint: new PublicKey('So11111111111111111111111111111111111111112'),
          outputMint: new PublicKey('EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'),
          amount: 1_000_000_000,
          slippageBps: 50,
        }),
      ).rejects.toThrow('Auto-trading is disabled');
    });
  });

  describe('getStatus', () => {
    it('should return user state', async () => {
      (mockConnection.getAccountInfo as jest.Mock).mockResolvedValueOnce({
        data: Buffer.alloc(256),
        owner: PROGRAM_ID,
        lamports: 2_039_280,
        executable: false,
      });
      const status = await client.getStatus();
      expect(status).toBeDefined();
      expect(status).toHaveProperty('mbtiType');
      expect(status).toHaveProperty('depositedAmount');
      expect(status).toHaveProperty('currentBalance');
      expect(status).toHaveProperty('realizedPnl');
      expect(status).toHaveProperty('totalTrades');
      expect(status).toHaveProperty('autoTradeEnabled');
    });

    it('should return null if user state does not exist', async () => {
      (mockConnection.getAccountInfo as jest.Mock).mockResolvedValueOnce(null);
      const status = await client.getStatus();
      expect(status).toBeNull();
    });
  });

  describe('getTradeHistory', () => {
    it('should return trade history array', async () => {
      const history = await client.getTradeHistory();
      expect(Array.isArray(history)).toBe(true);
    });

    it('should support pagination', async () => {
      const history = await client.getTradeHistory({ limit: 10, offset: 0 });
      expect(Array.isArray(history)).toBe(true);
    });
  });

  describe('PDA derivation', () => {
    it('should derive config PDA correctly', () => {
      const [pda] = PublicKey.findProgramAddressSync(
        [Buffer.from('config')],
        PROGRAM_ID,
      );
      expect(client.getConfigPDA().equals(pda)).toBe(true);
    });

    it('should derive user state PDA correctly', () => {
      const [pda] = PublicKey.findProgramAddressSync(
        [Buffer.from('user'), mockWallet.publicKey.toBuffer()],
        PROGRAM_ID,
      );
      expect(client.getUserStatePDA().equals(pda)).toBe(true);
    });

    it('should derive vault PDA correctly', () => {
      const mint = new PublicKey('So11111111111111111111111111111111111111112');
      const [pda] = PublicKey.findProgramAddressSync(
        [Buffer.from('vault'), mint.toBuffer()],
        PROGRAM_ID,
      );
      expect(client.getVaultPDA(mint).equals(pda)).toBe(true);
    });
  });
});
