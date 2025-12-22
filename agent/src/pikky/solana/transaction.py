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


class TransactionBuilder:
    """
    Builder for constructing Solana transactions.

    Supports adding multiple instruction types and handles
    the full lifecycle of building, signing, and serializing.
    """

    def __init__(self, solana_client: Any) -> None:
        """
        Initialize the transaction builder.

        Args:
            solana_client: SolanaClient instance for blockhash fetching.
        """
        self._client = solana_client
        self._instructions: list[Instruction] = []
        self._fee_payer: Optional[str] = None
        self._compute_unit_limit: Optional[int] = None
        self._compute_unit_price: Optional[int] = None

        logger.debug("transaction_builder_created")

    def set_fee_payer(self, pubkey: str) -> TransactionBuilder:
        """Set the fee payer for the transaction."""
        self._fee_payer = pubkey
        return self

    def set_compute_budget(
        self,
        unit_limit: int = 400_000,
        unit_price_micro_lamports: int = 1000,
    ) -> TransactionBuilder:
        """
        Set compute budget for the transaction.

        Args:
            unit_limit: Maximum compute units.
            unit_price_micro_lamports: Price per compute unit in micro-lamports.
        """
        self._compute_unit_limit = unit_limit
        self._compute_unit_price = unit_price_micro_lamports
        return self

    def add_instruction(self, instruction: Instruction) -> TransactionBuilder:
        """Add a raw instruction to the transaction."""
        self._instructions.append(instruction)
        return self

    def add_sol_transfer(
        self,
        from_pubkey: str,
        to_pubkey: str,
        lamports: int,
    ) -> TransactionBuilder:
        """
        Add a SOL transfer instruction.

        Args:
            from_pubkey: Sender address.
            to_pubkey: Recipient address.
            lamports: Amount in lamports.
        """
        data = struct.pack("<I", SystemInstruction.TRANSFER) + struct.pack("<Q", lamports)

        instruction = Instruction(
            program_id=SYSTEM_PROGRAM_ID,
            accounts=[
                AccountMeta(pubkey=from_pubkey, is_signer=True, is_writable=True),
                AccountMeta(pubkey=to_pubkey, is_signer=False, is_writable=True),
            ],
            data=data,
        )
        self._instructions.append(instruction)

        if self._fee_payer is None:
            self._fee_payer = from_pubkey

        return self

    def add_memo(self, memo_text: str) -> TransactionBuilder:
        """
        Add a memo instruction.

        Args:
            memo_text: Text content of the memo.
        """
        instruction = Instruction(
            program_id=MEMO_PROGRAM_ID,
            accounts=[],
            data=memo_text.encode("utf-8"),
        )
        self._instructions.append(instruction)
        return self

    def add_create_account(
        self,
        from_pubkey: str,
        new_account_pubkey: str,
        lamports: int,
        space: int,
        program_id: str,
    ) -> TransactionBuilder:
        """
        Add a create account instruction.

        Args:
            from_pubkey: Funding account.
            new_account_pubkey: New account to create.
            lamports: Lamports to fund the account with.
            space: Data size in bytes.
            program_id: Owner program of the new account.
        """
        data = (
            struct.pack("<I", SystemInstruction.CREATE_ACCOUNT)
            + struct.pack("<Q", lamports)
            + struct.pack("<Q", space)
            + base58.b58decode(program_id)
        )

        instruction = Instruction(
            program_id=SYSTEM_PROGRAM_ID,
            accounts=[
                AccountMeta(pubkey=from_pubkey, is_signer=True, is_writable=True),
                AccountMeta(pubkey=new_account_pubkey, is_signer=True, is_writable=True),
            ],
            data=data,
        )
        self._instructions.append(instruction)
        return self

    def add_create_ata(
        self,
        payer: str,
        owner: str,
        mint: str,
    ) -> TransactionBuilder:
        """
        Add instruction to create an Associated Token Account.

        Args:
            payer: Account paying for creation.
            owner: Owner of the new token account.
            mint: Token mint address.
        """
        ata = self._derive_ata_address(owner, mint)

        instruction = Instruction(
            program_id=ASSOCIATED_TOKEN_PROGRAM_ID,
            accounts=[
                AccountMeta(pubkey=payer, is_signer=True, is_writable=True),
                AccountMeta(pubkey=ata, is_signer=False, is_writable=True),
                AccountMeta(pubkey=owner, is_signer=False, is_writable=False),
                AccountMeta(pubkey=mint, is_signer=False, is_writable=False),
                AccountMeta(pubkey=SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
                AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
                AccountMeta(pubkey=SYSVAR_RENT, is_signer=False, is_writable=False),
            ],
            data=b"",
        )
        self._instructions.append(instruction)
        return self

    def add_token_transfer(
        self,
        source: str,
        destination: str,
        owner: str,
        amount: int,
    ) -> TransactionBuilder:
        """
        Add an SPL token transfer instruction.

        Args:
            source: Source token account.
            destination: Destination token account.
            owner: Authority/owner of the source account.
            amount: Amount of tokens to transfer.
        """
        data = bytes([3]) + struct.pack("<Q", amount)

        instruction = Instruction(
            program_id=TOKEN_PROGRAM_ID,
            accounts=[
                AccountMeta(pubkey=source, is_signer=False, is_writable=True),
                AccountMeta(pubkey=destination, is_signer=False, is_writable=True),
                AccountMeta(pubkey=owner, is_signer=True, is_writable=False),
            ],
            data=data,
        )
        self._instructions.append(instruction)
        return self

    def add_close_token_account(
        self,
        account: str,
        destination: str,
        owner: str,
    ) -> TransactionBuilder:
        """
        Add instruction to close a token account and recover rent.

        Args:
            account: Token account to close.
            destination: Where to send remaining SOL.
            owner: Authority of the token account.
        """
        data = bytes([9])

        instruction = Instruction(
            program_id=TOKEN_PROGRAM_ID,
            accounts=[
                AccountMeta(pubkey=account, is_signer=False, is_writable=True),
                AccountMeta(pubkey=destination, is_signer=False, is_writable=True),
                AccountMeta(pubkey=owner, is_signer=True, is_writable=False),
            ],
            data=data,
        )
        self._instructions.append(instruction)
        return self

    def add_jupiter_swap_instruction(
        self,
        swap_data: bytes,
        accounts: list[AccountMeta],
        jupiter_program_id: str = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
    ) -> TransactionBuilder:
        """
        Add a Jupiter swap instruction.

        Args:
            swap_data: Serialized swap instruction data from Jupiter API.
            accounts: Account metas for the swap instruction.
            jupiter_program_id: Jupiter program address.
        """
        instruction = Instruction(
            program_id=jupiter_program_id,
            accounts=accounts,
            data=swap_data,
        )
        self._instructions.append(instruction)
        return self

    async def build(self) -> TransactionMessage:
        """
        Build the transaction message.

        Prepends compute budget instructions if set, then adds
        all user instructions.

        Returns:
            Compiled TransactionMessage.
        """
        if self._fee_payer is None:
            raise TransactionBuildError("Fee payer not set")

        all_instructions: list[Instruction] = []

        if self._compute_unit_limit is not None:
            limit_data = bytes([ComputeBudgetInstruction.SET_COMPUTE_UNIT_LIMIT]) + struct.pack(
                "<I", self._compute_unit_limit
            )
            all_instructions.append(Instruction(
                program_id=COMPUTE_BUDGET_PROGRAM_ID,
                accounts=[],
                data=limit_data,
            ))

        if self._compute_unit_price is not None:
            price_data = bytes([ComputeBudgetInstruction.SET_COMPUTE_UNIT_PRICE]) + struct.pack(
                "<Q", self._compute_unit_price
            )
            all_instructions.append(Instruction(
                program_id=COMPUTE_BUDGET_PROGRAM_ID,
                accounts=[],
                data=price_data,
            ))

        all_instructions.extend(self._instructions)

        if not all_instructions:
            raise TransactionBuildError("No instructions added to transaction")

        blockhash = await self._client.get_recent_blockhash()

        message = TransactionMessage(
            recent_blockhash=blockhash,
            fee_payer=self._fee_payer,
            instructions=all_instructions,
        )

        logger.debug(
            "transaction_built",
            instructions=len(all_instructions),
            fee_payer=self._fee_payer[:8],
        )

        return message

    async def build_and_sign(self, keypair_bytes: Optional[bytes]) -> bytes:
        """
        Build the transaction, sign it, and return serialized bytes.

        Args:
            keypair_bytes: 64-byte keypair (32 private + 32 public).

        Returns:
            Serialized signed transaction bytes.
        """
        message = await self.build()
        message_bytes = message.compile()

        if keypair_bytes is None:
            raise TransactionBuildError("No keypair provided for signing")

        try:
            from solders.keypair import Keypair
            from solders.transaction import Transaction
            from solders.message import Message
            from solders.hash import Hash

            kp = Keypair.from_bytes(keypair_bytes)
            msg = Message.from_bytes(message_bytes)
            blockhash = Hash.from_string(message.recent_blockhash)
            tx = Transaction.new_unsigned(msg)
            tx.sign([kp], blockhash)
            return bytes(tx)

        except ImportError:
            logger.warning("solders_unavailable_using_fallback_signing")
            return self._fallback_sign(message_bytes, keypair_bytes)

    def _fallback_sign(self, message_bytes: bytes, keypair_bytes: bytes) -> bytes:
        """
        Fallback signing using cryptography library when solders is unavailable.

        Constructs a signed transaction by prepending the Ed25519 signature.
        """
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

            private_bytes = keypair_bytes[:32]
            private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
            signature = private_key.sign(message_bytes)

            num_signatures = bytes([1])
            signed_tx = num_signatures + signature + message_bytes
            return signed_tx

        except Exception as exc:
            raise TransactionBuildError(f"Fallback signing failed: {exc}") from exc

    def estimate_fee(self) -> int:
        """
        Estimate the transaction fee in lamports.

        Base fee is 5000 lamports per signature plus priority fee
        based on compute units and price.
        """
        base_fee = 5000

        priority_fee = 0
        if self._compute_unit_limit and self._compute_unit_price:
            priority_fee = (self._compute_unit_limit * self._compute_unit_price) // 1_000_000

        return base_fee + priority_fee

    def instruction_count(self) -> int:
        """Get the number of instructions (excluding compute budget)."""
        return len(self._instructions)

    def clear(self) -> TransactionBuilder:
        """Clear all instructions and reset the builder."""
        self._instructions.clear()
        self._compute_unit_limit = None
        self._compute_unit_price = None
        return self

    @staticmethod
    def _derive_ata_address(owner: str, mint: str) -> str:
        """Derive the Associated Token Account address."""
        try:
            from solders.pubkey import Pubkey
            owner_pk = Pubkey.from_string(owner)
            mint_pk = Pubkey.from_string(mint)
            token_program = Pubkey.from_string(TOKEN_PROGRAM_ID)
            ata_program = Pubkey.from_string(ASSOCIATED_TOKEN_PROGRAM_ID)

            ata, _bump = Pubkey.find_program_address(
                [bytes(owner_pk), bytes(token_program), bytes(mint_pk)],
                ata_program,
            )
            return str(ata)
        except ImportError:
            import hashlib
            seeds = (
                base58.b58decode(owner)
                + base58.b58decode(TOKEN_PROGRAM_ID)
                + base58.b58decode(mint)
            )
            h = hashlib.sha256(
                seeds
                + base58.b58decode(ASSOCIATED_TOKEN_PROGRAM_ID)
                + b"ProgramDerivedAddress"
            ).digest()
            return base58.b58encode(h[:32]).decode("ascii")


class TransactionBuildError(Exception):
    """Raised when transaction building fails."""
