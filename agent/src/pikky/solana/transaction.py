"""
Transaction Builder for PIKKY.

Builds complex Solana transactions with multiple instructions,
compute budget settings, priority fees, Jupiter swap instructions,
SOL transfers, and memo instructions.
"""

from __future__ import annotations

import base64
import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional

import base58
import structlog

logger = structlog.get_logger(__name__)

SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
ASSOCIATED_TOKEN_PROGRAM_ID = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
MEMO_PROGRAM_ID = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"
COMPUTE_BUDGET_PROGRAM_ID = "ComputeBudget111111111111111111111111111111"
SYSVAR_RENT = "SysvarRent111111111111111111111111111111111"


class SystemInstruction(IntEnum):
    """System program instruction indices."""

    CREATE_ACCOUNT = 0
    ASSIGN = 1
    TRANSFER = 2


class ComputeBudgetInstruction(IntEnum):
    """Compute budget program instruction types."""

    REQUEST_UNITS_DEPRECATED = 0
    REQUEST_HEAP_FRAME = 1
    SET_COMPUTE_UNIT_LIMIT = 2
    SET_COMPUTE_UNIT_PRICE = 3


@dataclass
class AccountMeta:
    """Account metadata for a Solana instruction."""

    pubkey: str
    is_signer: bool
    is_writable: bool


@dataclass
class Instruction:
    """A single Solana instruction."""

    program_id: str
    accounts: list[AccountMeta]
    data: bytes

    def account_keys(self) -> list[str]:
        """Get all unique account keys referenced by this instruction."""
        keys = [self.program_id]
        for acc in self.accounts:
            if acc.pubkey not in keys:
                keys.append(acc.pubkey)
        return keys


@dataclass
class TransactionMessage:
    """A Solana transaction message (legacy format)."""

    recent_blockhash: str
    fee_payer: str
    instructions: list[Instruction]

    def compile(self) -> bytes:
        """
        Compile the transaction message into serialized bytes.

        Follows Solana's wire format:
        1. Compact header (num_signers, num_readonly_signed, num_readonly_unsigned)
        2. Account keys array
        3. Recent blockhash
        4. Instructions array
        """
        account_map = self._build_account_map()
        sorted_keys = self._sort_accounts(account_map)

        num_signers = sum(1 for _, meta in sorted_keys if meta["is_signer"])
        num_readonly_signed = sum(
            1 for _, meta in sorted_keys
            if meta["is_signer"] and not meta["is_writable"]
        )
        num_readonly_unsigned = sum(
            1 for _, meta in sorted_keys
            if not meta["is_signer"] and not meta["is_writable"]
        )

        key_index_map = {key: i for i, (key, _) in enumerate(sorted_keys)}

        parts: list[bytes] = []

        parts.append(bytes([num_signers, num_readonly_signed, num_readonly_unsigned]))

        parts.append(self._encode_compact_u16(len(sorted_keys)))
        for key, _ in sorted_keys:
            parts.append(base58.b58decode(key))

        parts.append(base58.b58decode(self.recent_blockhash))

        parts.append(self._encode_compact_u16(len(self.instructions)))
        for ix in self.instructions:
            program_idx = key_index_map[ix.program_id]
            parts.append(bytes([program_idx]))

            parts.append(self._encode_compact_u16(len(ix.accounts)))
            for acc in ix.accounts:
                parts.append(bytes([key_index_map[acc.pubkey]]))

            parts.append(self._encode_compact_u16(len(ix.data)))
            parts.append(ix.data)

        return b"".join(parts)

    def _build_account_map(self) -> dict[str, dict[str, bool]]:
        """Build a map of all accounts with their signer/writable flags."""
        accounts: dict[str, dict[str, bool]] = {}

        accounts[self.fee_payer] = {"is_signer": True, "is_writable": True}

        for ix in self.instructions:
            for acc in ix.accounts:
                if acc.pubkey in accounts:
                    existing = accounts[acc.pubkey]
                    existing["is_signer"] = existing["is_signer"] or acc.is_signer
                    existing["is_writable"] = existing["is_writable"] or acc.is_writable
                else:
                    accounts[acc.pubkey] = {
                        "is_signer": acc.is_signer,
                        "is_writable": acc.is_writable,
                    }

            if ix.program_id not in accounts:
                accounts[ix.program_id] = {
                    "is_signer": False,
                    "is_writable": False,
                }

        return accounts

    def _sort_accounts(
        self,
        account_map: dict[str, dict[str, bool]],
    ) -> list[tuple[str, dict[str, bool]]]:
        """
        Sort accounts according to Solana's required ordering:
        1. Writable signers (fee payer first)
        2. Read-only signers
        3. Writable non-signers
        4. Read-only non-signers
        """
        writable_signers: list[tuple[str, dict[str, bool]]] = []
        readonly_signers: list[tuple[str, dict[str, bool]]] = []
        writable_nonsigners: list[tuple[str, dict[str, bool]]] = []
        readonly_nonsigners: list[tuple[str, dict[str, bool]]] = []

        for key, meta in account_map.items():
            if meta["is_signer"] and meta["is_writable"]:
                writable_signers.append((key, meta))
            elif meta["is_signer"]:
                readonly_signers.append((key, meta))
            elif meta["is_writable"]:
                writable_nonsigners.append((key, meta))
            else:
                readonly_nonsigners.append((key, meta))

        writable_signers.sort(key=lambda x: x[0] != self.fee_payer)

        return writable_signers + readonly_signers + writable_nonsigners + readonly_nonsigners

    @staticmethod
    def _encode_compact_u16(value: int) -> bytes:
        """Encode an integer as Solana's compact-u16 format."""
        if value < 0x80:
            return bytes([value])
        elif value < 0x4000:
            return bytes([
                (value & 0x7F) | 0x80,
                (value >> 7) & 0x7F,
            ])
        else:
            return bytes([
                (value & 0x7F) | 0x80,
                ((value >> 7) & 0x7F) | 0x80,
                (value >> 14) & 0x03,
            ])

