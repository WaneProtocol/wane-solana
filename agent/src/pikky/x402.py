"""
X402 Payment Handler for PIKKY.

Implements the HTTP 402 Payment Required protocol for gating access to
PIKKY's trading agent services. Users must pay in SOL on Solana to activate
their trading session. Payments are verified on-chain before granting access.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import base58
import structlog

logger = structlog.get_logger(__name__)


class PaymentStatus(str, Enum):
    """Status of an x402 payment."""

    PENDING = "pending"
    CONFIRMING = "confirming"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    REFUNDED = "refunded"
    FAILED = "failed"


@dataclass
class PaymentChallenge:
    """An x402 payment challenge issued to a client."""

    challenge_id: str
    recipient_address: str
    amount_lamports: int
    memo: str
    created_at: float
    expires_at: float
    mbti_type: str
    client_address: Optional[str] = None

    def is_expired(self) -> bool:
        """Check if this challenge has expired."""
        return time.time() > self.expires_at

    def to_header_value(self) -> str:
        """Serialize to x402 WWW-Authenticate header value."""
        return (
            f'X402 realm="pikky", '
            f'challenge="{self.challenge_id}", '
            f'recipient="{self.recipient_address}", '
            f'amount="{self.amount_lamports}", '
            f'memo="{self.memo}", '
            f'chain="solana", '
            f'expires="{int(self.expires_at)}"'
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON responses."""
        return {
            "challenge_id": self.challenge_id,
            "recipient": self.recipient_address,
            "amount_lamports": self.amount_lamports,
            "memo": self.memo,
            "chain": "solana",
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "mbti_type": self.mbti_type,
        }


@dataclass
class PaymentSession:
    """An active payment session after successful x402 payment."""

    session_id: str
    challenge_id: str
    client_address: str
    tx_signature: str
    amount_lamports: int
    mbti_type: str
    activated_at: float
    expires_at: float
    status: PaymentStatus = PaymentStatus.CONFIRMED
    trades_executed: int = 0
    pnl_lamports: int = 0

    def is_active(self) -> bool:
        """Check if this session is still active."""
        return self.status == PaymentStatus.CONFIRMED and time.time() < self.expires_at

    def remaining_seconds(self) -> float:
        """Get remaining session time in seconds."""
        remaining = self.expires_at - time.time()
        return max(0.0, remaining)

    def record_trade(self, pnl_lamports: int) -> None:
        """Record a trade execution and its PnL."""
        self.trades_executed += 1
        self.pnl_lamports += pnl_lamports


@dataclass
class RefundRecord:
    """Record of a payment refund."""

    refund_id: str
    session_id: str
    original_tx: str
    refund_tx: str
    amount_lamports: int
    reason: str
    created_at: float


class X402PaymentHandler:
    """
    Handles the x402 payment protocol for PIKKY trading agent access.

    The x402 flow:
    1. Client requests trading service without payment
    2. Server responds with 402 + payment challenge
    3. Client sends SOL payment on-chain with challenge memo
    4. Client retries request with payment proof (tx signature)
    5. Server verifies payment on-chain and activates session
    """

    def __init__(
        self,
        recipient_address: str,
        solana_client: object,
        base_fee_lamports: int = 5_000_000,
        session_duration_seconds: int = 3600,
        challenge_ttl_seconds: int = 300,
        refund_window_seconds: int = 300,
        hmac_secret: Optional[bytes] = None,
    ) -> None:
        """
        Initialize the x402 payment handler.

        Args:
            recipient_address: Solana address to receive payments.
            solana_client: SolanaClient instance for on-chain verification.
            base_fee_lamports: Base fee in lamports.
            session_duration_seconds: How long a paid session lasts.
            challenge_ttl_seconds: How long a payment challenge is valid.
            refund_window_seconds: Window after payment for refund eligibility.
            hmac_secret: Secret for signing challenge IDs. Generated if not provided.
        """
        self._recipient = recipient_address
        self._solana = solana_client
        self._base_fee = base_fee_lamports
        self._session_duration = session_duration_seconds
        self._challenge_ttl = challenge_ttl_seconds
        self._refund_window = refund_window_seconds
        self._hmac_secret = hmac_secret or secrets.token_bytes(32)

        self._pending_challenges: dict[str, PaymentChallenge] = {}
        self._active_sessions: dict[str, PaymentSession] = {}
        self._sessions_by_address: dict[str, list[str]] = {}
        self._refund_records: dict[str, RefundRecord] = {}
        self._verified_signatures: set[str] = set()

        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

        logger.info(
            "x402_handler_initialized",
            recipient=recipient_address,
            base_fee=base_fee_lamports,
            session_duration=session_duration_seconds,
        )

    async def start(self) -> None:
        """Start the background cleanup task."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("x402_cleanup_task_started")

    async def stop(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("x402_handler_stopped")

    def generate_challenge(
        self,
        mbti_type: str,
        fee_multiplier: float = 1.0,
        client_address: Optional[str] = None,
    ) -> PaymentChallenge:
        """
        Generate a new x402 payment challenge.

        Args:
            mbti_type: The MBTI type the user wants to trade with.
            fee_multiplier: Multiplier applied to base fee for this MBTI type.
            client_address: Optional client wallet address for targeted challenge.

        Returns:
            A PaymentChallenge with all details needed for the client to pay.
        """
        now = time.time()
        challenge_id = self._generate_challenge_id(mbti_type, now)
        amount = int(self._base_fee * fee_multiplier)
        memo = f"pikky:{challenge_id}:{mbti_type}"

        challenge = PaymentChallenge(
            challenge_id=challenge_id,
            recipient_address=self._recipient,
            amount_lamports=amount,
            memo=memo,
            created_at=now,
            expires_at=now + self._challenge_ttl,
            mbti_type=mbti_type,
            client_address=client_address,
        )

        self._pending_challenges[challenge_id] = challenge

        logger.info(
            "x402_challenge_generated",
            challenge_id=challenge_id,
            amount_lamports=amount,
            mbti_type=mbti_type,
            expires_in=self._challenge_ttl,
        )

        return challenge

    async def verify_payment(
        self,
        challenge_id: str,
        tx_signature: str,
        client_address: str,
    ) -> PaymentSession:
        """
        Verify an on-chain payment against a challenge and activate a session.

        Args:
            challenge_id: The challenge ID from the original 402 response.
            tx_signature: The Solana transaction signature of the payment.
            client_address: The wallet address that sent the payment.

        Returns:
            An activated PaymentSession.

        Raises:
            PaymentVerificationError: If verification fails.
        """
        async with self._lock:
            challenge = self._pending_challenges.get(challenge_id)
            if challenge is None:
                raise PaymentVerificationError(
                    f"Challenge not found: {challenge_id}",
                    code="CHALLENGE_NOT_FOUND",
                )

            if challenge.is_expired():
                del self._pending_challenges[challenge_id]
                raise PaymentVerificationError(
                    f"Challenge expired: {challenge_id}",
                    code="CHALLENGE_EXPIRED",
                )

            if challenge.client_address and challenge.client_address != client_address:
                raise PaymentVerificationError(
                    "Client address mismatch",
                    code="ADDRESS_MISMATCH",
                )

            if tx_signature in self._verified_signatures:
                raise PaymentVerificationError(
                    "Transaction signature already used",
                    code="DUPLICATE_SIGNATURE",
                )

            tx_valid = await self._verify_transaction_on_chain(
                tx_signature=tx_signature,
                expected_recipient=self._recipient,
                expected_amount=challenge.amount_lamports,
                expected_memo=challenge.memo,
                expected_sender=client_address,
            )

            if not tx_valid:
                raise PaymentVerificationError(
                    "On-chain transaction verification failed",
                    code="TX_VERIFICATION_FAILED",
                )

            self._verified_signatures.add(tx_signature)
            del self._pending_challenges[challenge_id]

            now = time.time()
            session_id = self._generate_session_id(challenge_id, tx_signature)
            session = PaymentSession(
                session_id=session_id,
                challenge_id=challenge_id,
                client_address=client_address,
                tx_signature=tx_signature,
                amount_lamports=challenge.amount_lamports,
                mbti_type=challenge.mbti_type,
                activated_at=now,
                expires_at=now + self._session_duration,
            )

            self._active_sessions[session_id] = session
            if client_address not in self._sessions_by_address:
                self._sessions_by_address[client_address] = []
            self._sessions_by_address[client_address].append(session_id)

            logger.info(
                "x402_payment_verified",
                session_id=session_id,
                challenge_id=challenge_id,
                tx_signature=tx_signature,
                client=client_address,
                mbti_type=challenge.mbti_type,
                expires_at=session.expires_at,
            )

            return session

    def get_session(self, session_id: str) -> Optional[PaymentSession]:
        """Get an active session by ID."""
        session = self._active_sessions.get(session_id)
        if session and not session.is_active():
            session.status = PaymentStatus.EXPIRED
            return None
        return session

    def get_active_session_for_address(self, client_address: str) -> Optional[PaymentSession]:
        """Get the most recent active session for a wallet address."""
        session_ids = self._sessions_by_address.get(client_address, [])
        for sid in reversed(session_ids):
            session = self._active_sessions.get(sid)
            if session and session.is_active():
                return session
        return None

    def get_all_active_sessions(self) -> list[PaymentSession]:
        """Get all currently active sessions."""
        active = []
        for session in self._active_sessions.values():
            if session.is_active():
                active.append(session)
            elif session.status == PaymentStatus.CONFIRMED:
                session.status = PaymentStatus.EXPIRED
        return active

    async def process_refund(
        self,
        session_id: str,
        reason: str = "user_requested",
    ) -> RefundRecord:
        """
        Process a refund for a payment session.

        Only sessions within the refund window and with zero trades
        executed are eligible for refund.

        Args:
            session_id: The session to refund.
            reason: Reason for the refund.

        Returns:
            A RefundRecord with the refund transaction details.

        Raises:
            RefundError: If the session is not eligible for refund.
        """
        async with self._lock:
            session = self._active_sessions.get(session_id)
            if session is None:
                raise RefundError(f"Session not found: {session_id}")

            if session.status == PaymentStatus.REFUNDED:
                raise RefundError(f"Session already refunded: {session_id}")

            elapsed = time.time() - session.activated_at
            if elapsed > self._refund_window:
                raise RefundError(
                    f"Refund window expired. Elapsed: {elapsed:.0f}s, "
                    f"window: {self._refund_window}s"
                )

            if session.trades_executed > 0:
                raise RefundError(
                    f"Cannot refund session with {session.trades_executed} trades executed"
                )

            refund_amount = session.amount_lamports
            refund_tx = await self._execute_refund_transfer(
                recipient=session.client_address,
                amount_lamports=refund_amount,
            )

            refund_id = f"refund_{session_id}_{int(time.time())}"
            record = RefundRecord(
                refund_id=refund_id,
                session_id=session_id,
                original_tx=session.tx_signature,
                refund_tx=refund_tx,
                amount_lamports=refund_amount,
                reason=reason,
                created_at=time.time(),
            )

            session.status = PaymentStatus.REFUNDED
            self._refund_records[refund_id] = record

            logger.info(
                "x402_refund_processed",
                refund_id=refund_id,
                session_id=session_id,
                amount=refund_amount,
                refund_tx=refund_tx,
            )

            return record

    def validate_session_header(self, authorization: str) -> Optional[PaymentSession]:
        """
        Validate an x402 Authorization header and return the session.

        Expected format: X402 session="<session_id>", signature="<sig>"

        Args:
            authorization: The Authorization header value.

        Returns:
            The active PaymentSession if valid, None otherwise.
        """
        if not authorization.startswith("X402 "):
            return None

        params = self._parse_header_params(authorization[5:])
        session_id = params.get("session")
        if not session_id:
            return None

        session = self.get_session(session_id)
        if session is None:
            return None

        sig = params.get("signature")
        if sig:
            expected_sig = self._sign_session_id(session_id)
            if not hmac.compare_digest(sig, expected_sig):
                logger.warning("x402_invalid_session_signature", session_id=session_id)
                return None

        return session

    def get_stats(self) -> dict:
        """Get handler statistics."""
        active_sessions = self.get_all_active_sessions()
        total_revenue = sum(s.amount_lamports for s in self._active_sessions.values())
        total_refunded = sum(r.amount_lamports for r in self._refund_records.values())

        return {
            "pending_challenges": len(self._pending_challenges),
            "active_sessions": len(active_sessions),
            "total_sessions": len(self._active_sessions),
            "total_refunds": len(self._refund_records),
            "total_revenue_lamports": total_revenue,
            "total_refunded_lamports": total_refunded,
            "net_revenue_lamports": total_revenue - total_refunded,
            "verified_signatures": len(self._verified_signatures),
        }

    async def _verify_transaction_on_chain(
        self,
        tx_signature: str,
        expected_recipient: str,
        expected_amount: int,
        expected_memo: str,
        expected_sender: str,
    ) -> bool:
        """
        Verify a payment transaction on the Solana blockchain.

        Checks:
        1. Transaction exists and is confirmed
        2. Transfer instruction sends correct amount to recipient
        3. Memo instruction contains the challenge memo
        4. Sender matches expected address
        """
        try:
            tx_info = await self._solana.get_transaction(tx_signature)
            if tx_info is None:
                logger.warning("x402_tx_not_found", tx_signature=tx_signature)
                return False

            if tx_info.get("meta", {}).get("err") is not None:
                logger.warning(
                    "x402_tx_failed",
                    tx_signature=tx_signature,
                    error=tx_info["meta"]["err"],
                )
                return False

            pre_balances = tx_info.get("meta", {}).get("preBalances", [])
            post_balances = tx_info.get("meta", {}).get("postBalances", [])
            account_keys = tx_info.get("transaction", {}).get("message", {}).get(
                "accountKeys", []
            )

            recipient_idx = None
            sender_idx = None
            for i, key in enumerate(account_keys):
                addr = key if isinstance(key, str) else key.get("pubkey", "")
                if addr == expected_recipient:
                    recipient_idx = i
                if addr == expected_sender:
                    sender_idx = i

            if recipient_idx is None:
                logger.warning("x402_recipient_not_in_tx", tx_signature=tx_signature)
                return False

            if sender_idx is None:
                logger.warning("x402_sender_not_in_tx", tx_signature=tx_signature)
                return False

            if len(pre_balances) > recipient_idx and len(post_balances) > recipient_idx:
                received = post_balances[recipient_idx] - pre_balances[recipient_idx]
                if received < expected_amount:
                    logger.warning(
                        "x402_insufficient_amount",
                        tx_signature=tx_signature,
                        expected=expected_amount,
                        received=received,
                    )
                    return False

            log_messages = tx_info.get("meta", {}).get("logMessages", [])
            memo_found = any(expected_memo in msg for msg in log_messages)
            if not memo_found:
                logger.warning(
                    "x402_memo_not_found",
                    tx_signature=tx_signature,
                    expected_memo=expected_memo,
                )
                return False

            return True

        except Exception as exc:
            logger.error(
                "x402_verification_error",
                tx_signature=tx_signature,
                error=str(exc),
            )
            return False

    async def _execute_refund_transfer(
        self,
        recipient: str,
        amount_lamports: int,
    ) -> str:
        """Execute a SOL transfer for refund. Returns the tx signature."""
        try:
            tx_sig = await self._solana.send_sol(
                to_address=recipient,
                amount_lamports=amount_lamports,
            )
            logger.info(
                "x402_refund_transfer_sent",
                recipient=recipient,
                amount=amount_lamports,
                tx=tx_sig,
            )
            return tx_sig
        except Exception as exc:
            logger.error(
                "x402_refund_transfer_failed",
                recipient=recipient,
                amount=amount_lamports,
                error=str(exc),
            )
            raise RefundError(f"Refund transfer failed: {exc}") from exc

    def _generate_challenge_id(self, mbti_type: str, timestamp: float) -> str:
        """Generate a unique, signed challenge ID."""
        nonce = secrets.token_hex(16)
        raw = f"{mbti_type}:{timestamp}:{nonce}"
        sig = hmac.new(self._hmac_secret, raw.encode(), hashlib.sha256).hexdigest()[:16]
        return f"ch_{sig}_{nonce[:8]}"

    def _generate_session_id(self, challenge_id: str, tx_signature: str) -> str:
        """Generate a unique session ID from challenge and transaction."""
        raw = f"{challenge_id}:{tx_signature}"
        digest = hashlib.sha256(raw.encode()).hexdigest()[:24]
        return f"sess_{digest}"

    def _sign_session_id(self, session_id: str) -> str:
        """Create an HMAC signature for a session ID."""
        return hmac.new(
            self._hmac_secret, session_id.encode(), hashlib.sha256
        ).hexdigest()

    @staticmethod
    def _parse_header_params(header_value: str) -> dict[str, str]:
        """Parse key=value pairs from a header string."""
        params: dict[str, str] = {}
        parts = header_value.split(",")
        for part in parts:
            part = part.strip()
            if "=" not in part:
                continue
            key, _, value = part.partition("=")
            key = key.strip()
            value = value.strip().strip('"')
            params[key] = value
        return params

    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired challenges and sessions."""
        while True:
            try:
                await asyncio.sleep(60)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("x402_cleanup_error", error=str(exc))

    async def _cleanup_expired(self) -> None:
        """Remove expired challenges and mark expired sessions."""
        now = time.time()
        expired_challenges = [
            cid for cid, c in self._pending_challenges.items() if c.is_expired()
        ]
        for cid in expired_challenges:
            del self._pending_challenges[cid]

        expired_sessions = 0
        for session in self._active_sessions.values():
            if session.status == PaymentStatus.CONFIRMED and now > session.expires_at:
                session.status = PaymentStatus.EXPIRED
                expired_sessions += 1

        if expired_challenges or expired_sessions:
            logger.info(
                "x402_cleanup_complete",
                expired_challenges=len(expired_challenges),
                expired_sessions=expired_sessions,
            )


class PaymentVerificationError(Exception):
    """Raised when x402 payment verification fails."""

    def __init__(self, message: str, code: str = "UNKNOWN") -> None:
        super().__init__(message)
        self.code = code


class RefundError(Exception):
    """Raised when a refund cannot be processed."""
