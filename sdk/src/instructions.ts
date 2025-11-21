import {
  PublicKey,
  SystemProgram,
  TransactionInstruction,
  SYSVAR_RENT_PUBKEY,
} from "@solana/web3.js";
import { TOKEN_PROGRAM_ID } from "@solana/spl-token";
import { BorshCoder } from "@coral-xyz/anchor";
import {
  MbtiType,
  TradeDirection,
  OrderType,
  PIKKY_PROGRAM_ID,
} from "./types";
import {
  deriveUserAccountPDA,
  deriveTradeVaultPDA,
  deriveProtocolTreasuryPDA,
  deriveMbtiStrategyPDA,
} from "./utils";

const PIKKY_IDL = {
  version: "0.1.0",
  name: "pikky",
  instructions: [
    {
      name: "initialize",
      accounts: [
        { name: "user", isMut: true, isSigner: true },
        { name: "userAccount", isMut: true, isSigner: false },
        { name: "systemProgram", isMut: false, isSigner: false },
        { name: "rent", isMut: false, isSigner: false },
      ],
      args: [{ name: "mbtiType", type: "string" }],
    },
    {
      name: "deposit",
      accounts: [
        { name: "user", isMut: true, isSigner: true },
        { name: "userAccount", isMut: true, isSigner: false },
        { name: "tradeVault", isMut: true, isSigner: false },
        { name: "systemProgram", isMut: false, isSigner: false },
      ],
      args: [{ name: "amount", type: "u64" }],
    },
    {
      name: "withdraw",
      accounts: [
        { name: "user", isMut: true, isSigner: true },
        { name: "userAccount", isMut: true, isSigner: false },
        { name: "tradeVault", isMut: true, isSigner: false },
        { name: "systemProgram", isMut: false, isSigner: false },
      ],
      args: [{ name: "amount", type: "u64" }],
    },
    {
      name: "openTrade",
      accounts: [
        { name: "user", isMut: true, isSigner: true },
        { name: "userAccount", isMut: true, isSigner: false },
        { name: "tradeVault", isMut: true, isSigner: false },
        { name: "protocolTreasury", isMut: true, isSigner: false },
        { name: "tokenMint", isMut: false, isSigner: false },
        { name: "mbtiStrategy", isMut: false, isSigner: false },
        { name: "systemProgram", isMut: false, isSigner: false },
        { name: "tokenProgram", isMut: false, isSigner: false },
      ],
      args: [
        { name: "tradeId", type: "string" },
        { name: "direction", type: "u8" },
        { name: "size", type: "u64" },
        { name: "leverage", type: "u8" },
        { name: "orderType", type: "u8" },
        { name: "limitPrice", type: { option: "u64" } },
        { name: "stopLoss", type: { option: "u64" } },
        { name: "takeProfit", type: { option: "u64" } },
      ],
    },
    {
      name: "closeTrade",
      accounts: [
        { name: "user", isMut: true, isSigner: true },
        { name: "userAccount", isMut: true, isSigner: false },
        { name: "tradeVault", isMut: true, isSigner: false },
        { name: "protocolTreasury", isMut: true, isSigner: false },
        { name: "systemProgram", isMut: false, isSigner: false },
      ],
      args: [{ name: "tradeId", type: "string" }],
    },
    {
      name: "setMbtiStrategy",
      accounts: [
        { name: "user", isMut: true, isSigner: true },
        { name: "userAccount", isMut: true, isSigner: false },
        { name: "mbtiStrategy", isMut: false, isSigner: false },
      ],
      args: [{ name: "mbtiType", type: "string" }],
    },
  ],
  accounts: [
    {
      name: "UserAccount",
      type: {
        kind: "struct",
        fields: [
          { name: "owner", type: "publicKey" },
          { name: "authority", type: "publicKey" },
          { name: "mbtiType", type: "string" },
          { name: "balance", type: "u64" },
          { name: "lockedBalance", type: "u64" },
          { name: "totalDeposited", type: "u64" },
          { name: "totalWithdrawn", type: "u64" },
          { name: "totalTrades", type: "u32" },
          { name: "winningTrades", type: "u32" },
          { name: "losingTrades", type: "u32" },
          { name: "totalPnl", type: "i64" },
          { name: "createdAt", type: "i64" },
          { name: "lastTradeAt", type: "i64" },
          { name: "bump", type: "u8" },
        ],
      },
    },
  ],
} as const;

function encodeInstructionData(
  instructionName: string,
  args: Record<string, unknown>
): Buffer {
  const discriminator = createDiscriminator(instructionName);
  const argBuffers: Buffer[] = [discriminator];

  const instrDef = PIKKY_IDL.instructions.find(
    (i) => i.name === instructionName
  );
  if (!instrDef) {
    throw new Error(`Unknown instruction: ${instructionName}`);
  }

  for (const argDef of instrDef.args) {
    const value = args[argDef.name];
    const argType =
      typeof argDef.type === "string" ? argDef.type : "option";

    switch (argType) {
      case "string": {
        const str = value as string;
        const strBytes = Buffer.from(str, "utf-8");
        const lenBuf = Buffer.alloc(4);
        lenBuf.writeUInt32LE(strBytes.length);
        argBuffers.push(lenBuf, strBytes);
        break;
      }
      case "u8": {
        const buf = Buffer.alloc(1);
        buf.writeUInt8(value as number);
        argBuffers.push(buf);
        break;
      }
      case "u16": {
        const buf = Buffer.alloc(2);
        buf.writeUInt16LE(value as number);
        argBuffers.push(buf);
        break;
      }
      case "u32": {
        const buf = Buffer.alloc(4);
        buf.writeUInt32LE(value as number);
        argBuffers.push(buf);
        break;
      }
      case "u64": {
        const buf = Buffer.alloc(8);
        const bigVal = BigInt(value as number | bigint);
        buf.writeBigUInt64LE(bigVal);
        argBuffers.push(buf);
        break;
      }
      case "i64": {
        const buf = Buffer.alloc(8);
        const bigVal = BigInt(value as number | bigint);
        buf.writeBigInt64LE(bigVal);
        argBuffers.push(buf);
        break;
      }
      case "option": {
        if (value === null || value === undefined) {
          argBuffers.push(Buffer.from([0]));
        } else {
          argBuffers.push(Buffer.from([1]));
          const buf = Buffer.alloc(8);
          buf.writeBigUInt64LE(BigInt(value as number));
          argBuffers.push(buf);
        }
        break;
      }
      default:
        throw new Error(`Unsupported arg type: ${argType}`);
    }
  }

  return Buffer.concat(argBuffers);
}

function createDiscriminator(instructionName: string): Buffer {
  const crypto = require("crypto");
  const preimage = `global:${instructionName}`;
  const hash = crypto.createHash("sha256").update(preimage).digest();
  return hash.slice(0, 8);
}

export async function buildInitializeInstruction(
  user: PublicKey,
  mbtiType: MbtiType,
  programId?: PublicKey
): Promise<TransactionInstruction> {
  const pid = programId ?? new PublicKey(PIKKY_PROGRAM_ID);
  const [userAccount] = await deriveUserAccountPDA(user, pid);

  const data = encodeInstructionData("initialize", {
    mbtiType: mbtiType.toString(),
  });

  return new TransactionInstruction({
    programId: pid,
    keys: [
      { pubkey: user, isSigner: true, isWritable: true },
      { pubkey: userAccount, isSigner: false, isWritable: true },
      { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
      { pubkey: SYSVAR_RENT_PUBKEY, isSigner: false, isWritable: false },
    ],
    data,
  });
}
