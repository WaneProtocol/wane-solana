"""
Solana RPC Client for PIKKY.

Wraps solana-py to provide a high-level async interface for all
Solana blockchain interactions: balance checks, transaction building,
signing, submission, confirmation, and account data fetching.
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from pathlib import Path
from typing import Any, Optional

import base58
import httpx
import structlog

logger = structlog.get_logger(__name__)

LAMPORTS_PER_SOL = 1_000_000_000
SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
ASSOCIATED_TOKEN_PROGRAM_ID = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
MEMO_PROGRAM_ID = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"
COMPUTE_BUDGET_PROGRAM_ID = "ComputeBudget111111111111111111111111111111"


class SolanaClient:
    """
    Async Solana RPC client.

    Provides methods for common Solana operations with automatic
    retry logic, connection management, and error handling.
    """

    def __init__(
        self,
        rpc_url: str = "https://api.mainnet-beta.solana.com",
        ws_url: Optional[str] = None,
        commitment: str = "confirmed",
        keypair_path: Optional[str] = None,
        private_key_b58: Optional[str] = None,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize the Solana client.

        Args:
            rpc_url: HTTP RPC endpoint URL.
            ws_url: WebSocket RPC endpoint URL.
            commitment: Default commitment level.
            keypair_path: Path to keypair JSON file.
            private_key_b58: Base58-encoded private key.
            max_retries: Maximum retries for RPC calls.
        """
        self._rpc_url = rpc_url
        self._ws_url = ws_url or rpc_url.replace("https://", "wss://").replace("http://", "ws://")
        self._commitment = commitment
        self._max_retries = max_retries
        self._http: Optional[httpx.AsyncClient] = None
        self._request_id: int = 0

        self._keypair_bytes: Optional[bytes] = None
        self._public_key: Optional[str] = None

        if keypair_path:
            self._load_keypair_from_file(keypair_path)
        elif private_key_b58:
            self._load_keypair_from_base58(private_key_b58)

        self._slot_cache: Optional[int] = None
        self._slot_cache_time: float = 0
        self._blockhash_cache: Optional[str] = None
        self._blockhash_cache_time: float = 0

        logger.info(
            "solana_client_initialized",
            rpc_url=rpc_url,
            commitment=commitment,
            has_keypair=self._keypair_bytes is not None,
        )

    async def connect(self) -> None:
        """Establish connection to Solana RPC."""
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

        try:
            health = await self._rpc_request("getHealth")
            version = await self._rpc_request("getVersion")
            logger.info(
                "solana_connected",
                rpc_url=self._rpc_url,
                version=version.get("solana-core", "unknown"),
            )
        except Exception as exc:
            logger.warning("solana_connect_health_check_failed", error=str(exc))

    async def disconnect(self) -> None:
        """Close the RPC connection."""
        if self._http:
            await self._http.aclose()
            self._http = None
        logger.info("solana_disconnected")

    async def get_wallet_pubkey(self) -> str:
        """Get the public key of the loaded wallet."""
        if self._public_key is None:
            raise SolanaClientError("No wallet keypair loaded")
        return self._public_key

    async def get_sol_balance(self, address: Optional[str] = None) -> float:
        """
        Get SOL balance for an address.

        Args:
            address: Wallet address. Uses loaded wallet if None.

        Returns:
            Balance in SOL.
        """
        addr = address or self._public_key
        if addr is None:
            raise SolanaClientError("No address provided and no wallet loaded")

        result = await self._rpc_request(
            "getBalance",
            [addr, {"commitment": self._commitment}],
        )
        lamports = result.get("value", 0)
        return lamports / LAMPORTS_PER_SOL

    async def get_token_balance(
        self,
        owner: Optional[str] = None,
        mint: Optional[str] = None,
        token_account: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Get SPL token balance.

        Either provide a specific token_account address, or
        owner + mint to look up the associated token account.

        Returns:
            Dict with 'amount' (raw), 'decimals', and 'ui_amount'.
        """
        if token_account:
            result = await self._rpc_request(
                "getTokenAccountBalance",
                [token_account, {"commitment": self._commitment}],
            )
            value = result.get("value", {})
            return {
                "amount": int(value.get("amount", "0")),
                "decimals": value.get("decimals", 0),
                "ui_amount": float(value.get("uiAmountString", "0")),
            }

        owner_addr = owner or self._public_key
        if owner_addr is None or mint is None:
            raise SolanaClientError("Provide either token_account or owner+mint")

        ata = self._derive_ata(owner_addr, mint)
        try:
            return await self.get_token_balance(token_account=ata)
        except Exception:
            return {"amount": 0, "decimals": 0, "ui_amount": 0.0}

    async def get_token_accounts(
        self,
        owner: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Get all SPL token accounts for an owner.

        Returns:
            List of dicts with 'mint', 'amount', 'decimals', 'account'.
        """
        owner_addr = owner or self._public_key
        if owner_addr is None:
            raise SolanaClientError("No owner address")

        result = await self._rpc_request(
            "getTokenAccountsByOwner",
            [
                owner_addr,
                {"programId": TOKEN_PROGRAM_ID},
                {"encoding": "jsonParsed", "commitment": self._commitment},
            ],
        )

        accounts = []
        for item in result.get("value", []):
            info = item.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
            token_amount = info.get("tokenAmount", {})
            accounts.append({
                "account": item.get("pubkey", ""),
                "mint": info.get("mint", ""),
                "amount": int(token_amount.get("amount", "0")),
                "decimals": token_amount.get("decimals", 0),
                "ui_amount": float(token_amount.get("uiAmountString", "0")),
            })

        return accounts

    async def get_transaction(
        self,
        signature: str,
        max_supported_version: int = 0,
    ) -> Optional[dict[str, Any]]:
        """
        Fetch a transaction by signature.

        Args:
            signature: Transaction signature.
            max_supported_version: Max transaction version to support.

        Returns:
            Transaction data dict or None if not found.
        """
        result = await self._rpc_request(
            "getTransaction",
            [
                signature,
                {
                    "encoding": "jsonParsed",
                    "commitment": self._commitment,
                    "maxSupportedTransactionVersion": max_supported_version,
                },
            ],
        )
        return result

    async def get_recent_blockhash(self) -> str:
        """
        Get a recent blockhash for transaction building.

        Caches the blockhash for 30 seconds to reduce RPC calls.

        Returns:
            Recent blockhash as a base58 string.
        """
        now = time.time()
        if self._blockhash_cache and now - self._blockhash_cache_time < 30:
            return self._blockhash_cache

        result = await self._rpc_request(
            "getLatestBlockhash",
            [{"commitment": self._commitment}],
        )
        blockhash = result.get("value", {}).get("blockhash", "")
        if not blockhash:
            raise SolanaClientError("Failed to get recent blockhash")

        self._blockhash_cache = blockhash
        self._blockhash_cache_time = now
        return blockhash

    async def get_slot(self) -> int:
        """Get the current slot number."""
        now = time.time()
        if self._slot_cache is not None and now - self._slot_cache_time < 2:
            return self._slot_cache

        result = await self._rpc_request("getSlot", [{"commitment": self._commitment}])
        self._slot_cache = int(result)
        self._slot_cache_time = now
        return self._slot_cache

    async def get_account_info(self, address: str) -> Optional[dict[str, Any]]:
        """Fetch account information."""
        result = await self._rpc_request(
            "getAccountInfo",
            [address, {"encoding": "jsonParsed", "commitment": self._commitment}],
        )
        value = result.get("value")
        if value is None:
            return None
        return value

    async def send_sol(
        self,
        to_address: str,
        amount_lamports: int,
        memo: Optional[str] = None,
    ) -> str:
        """
        Send SOL to an address.

        Args:
            to_address: Recipient address.
            amount_lamports: Amount in lamports.
            memo: Optional memo to include.

        Returns:
            Transaction signature.
        """
        from pikky.solana.transaction import TransactionBuilder

        if self._public_key is None:
            raise SolanaClientError("No wallet loaded")

        builder = TransactionBuilder(self)
        builder.add_sol_transfer(
            from_pubkey=self._public_key,
            to_pubkey=to_address,
            lamports=amount_lamports,
        )

        if memo:
            builder.add_memo(memo)

        tx_bytes = await builder.build_and_sign(self._keypair_bytes)
        return await self.send_raw_transaction(tx_bytes)

    async def send_raw_transaction(
        self,
        transaction_bytes: bytes,
        skip_preflight: bool = False,
    ) -> str:
        """
        Send a raw serialized transaction.

        Args:
            transaction_bytes: Serialized transaction bytes.
            skip_preflight: Skip preflight simulation.

        Returns:
            Transaction signature.
        """
        encoded = base64.b64encode(transaction_bytes).decode("ascii")

        result = await self._rpc_request(
            "sendTransaction",
            [
                encoded,
                {
                    "encoding": "base64",
                    "skipPreflight": skip_preflight,
                    "preflightCommitment": self._commitment,
                    "maxRetries": 3,
                },
            ],
        )

        if isinstance(result, str):
            sig = result
        else:
            sig = str(result)

        logger.info("transaction_sent", signature=sig[:16] + "...")
        return sig

    async def sign_and_send_transaction(
        self,
        transaction_b64: str,
    ) -> str:
        """
        Sign a base64-encoded transaction and send it.

        Used for Jupiter swap transactions that come pre-built.

        Args:
            transaction_b64: Base64-encoded transaction.

        Returns:
            Transaction signature.
        """
        if self._keypair_bytes is None:
            raise SolanaClientError("No keypair loaded for signing")

        tx_bytes = base64.b64decode(transaction_b64)

        try:
            from solders.transaction import VersionedTransaction
            from solders.keypair import Keypair

            keypair = Keypair.from_bytes(self._keypair_bytes)
            tx = VersionedTransaction.from_bytes(tx_bytes)
            signed_tx = VersionedTransaction(tx.message, [keypair])
            signed_bytes = bytes(signed_tx)
        except ImportError:
            logger.warning("solders_not_available_using_raw_send")
            signed_bytes = tx_bytes

        return await self.send_raw_transaction(signed_bytes, skip_preflight=True)

    async def confirm_transaction(
        self,
        signature: str,
        timeout_seconds: float = 60,
        poll_interval: float = 2.0,
    ) -> bool:
        """
        Wait for a transaction to be confirmed.

        Args:
            signature: Transaction signature to confirm.
            timeout_seconds: Maximum time to wait.
            poll_interval: Seconds between status checks.

        Returns:
            True if confirmed, False if timed out.
        """
        start = time.time()

        while time.time() - start < timeout_seconds:
            try:
                result = await self._rpc_request(
                    "getSignatureStatuses",
                    [[signature]],
                )
                statuses = result.get("value", [])
                if statuses and statuses[0] is not None:
                    status = statuses[0]
                    if status.get("err"):
                        logger.error(
                            "transaction_failed",
                            signature=signature[:16],
                            error=status["err"],
                        )
                        return False
                    conf_status = status.get("confirmationStatus", "")
                    if conf_status in ("confirmed", "finalized"):
                        logger.info(
                            "transaction_confirmed",
                            signature=signature[:16],
                            status=conf_status,
                            elapsed=f"{time.time() - start:.1f}s",
                        )
                        return True
            except Exception as exc:
                logger.warning(
                    "confirm_check_error",
                    signature=signature[:16],
                    error=str(exc),
                )

            await asyncio.sleep(poll_interval)

        logger.warning(
            "transaction_confirmation_timeout",
            signature=signature[:16],
            timeout=timeout_seconds,
        )
        return False

    async def get_minimum_balance_for_rent(self, data_size: int) -> int:
        """Get minimum balance for rent exemption for a given data size."""
        result = await self._rpc_request(
            "getMinimumBalanceForRentExemption",
            [data_size],
        )
        return int(result)

    async def get_token_supply(self, mint: str) -> dict[str, Any]:
        """Get the total supply of an SPL token."""
        result = await self._rpc_request(
            "getTokenSupply",
            [mint, {"commitment": self._commitment}],
        )
        value = result.get("value", {})
        return {
            "amount": int(value.get("amount", "0")),
            "decimals": value.get("decimals", 0),
            "ui_amount": float(value.get("uiAmountString", "0")),
        }
