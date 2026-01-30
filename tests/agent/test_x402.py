"""Tests for x402 payment handler."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
import time
import hashlib
import os

from src.x402_handler import (
    X402Handler,
    X402Config,
    PaymentRequest,
    PaymentResult,
    PaymentStatus,
    generate_nonce,
    parse_402_response,
    validate_payment_headers,
    build_payment_headers,
)


@pytest.fixture
def x402_config():
    return X402Config(
        rpc_url="https://api.devnet.solana.com",
        vault_address="PikkyVau1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        network="solana:devnet",
        payment_timeout_seconds=300,
        min_payment_amount=1_000_000,
        max_payment_amount=1_000_000_000,
    )


@pytest.fixture
def handler(x402_config):
    return X402Handler(x402_config)


@pytest.fixture
def valid_payment_request():
    return PaymentRequest(
        version="x402/1.0",
        network="solana:devnet",
        amount=10_000_000,
        token_mint="So11111111111111111111111111111111111111112",
        address="PikkyVau1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        nonce="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        expires_at=int(time.time()) + 300,
        description="AI trade execution",
    )


class TestNonceGeneration:
    """Tests for nonce generation and management."""

    def test_generate_nonce_returns_hex_string(self):
        nonce = generate_nonce()
        assert isinstance(nonce, str)
        assert len(nonce) == 64  # 32 bytes = 64 hex chars
        int(nonce, 16)  # Should be valid hex

    def test_generate_nonce_is_unique(self):
        nonces = {generate_nonce() for _ in range(100)}
        assert len(nonces) == 100

    def test_generate_nonce_is_cryptographically_random(self):
        nonce1 = generate_nonce()
        nonce2 = generate_nonce()
        # Hamming distance should be high for random values
        diff_bits = bin(int(nonce1, 16) ^ int(nonce2, 16)).count("1")
        assert diff_bits > 50  # Expect roughly half of 256 bits to differ


class TestPaymentRequestParsing:
    """Tests for parsing 402 response into payment request."""

    def test_parse_valid_402_response(self):
        headers = {
            "x-payment-version": "x402/1.0",
            "x-payment-network": "solana:devnet",
            "x-payment-amount": "10000000",
            "x-payment-token-mint": "So11111111111111111111111111111111111111112",
            "x-payment-address": "PikkyVau1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "x-payment-nonce": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            "x-payment-expires": str(int(time.time()) + 300),
            "x-payment-description": "AI trade execution",
        }
        request = parse_402_response(headers)
        assert request.version == "x402/1.0"
        assert request.amount == 10_000_000
        assert request.network == "solana:devnet"
        assert request.description == "AI trade execution"

    def test_parse_missing_required_header(self):
        headers = {
            "x-payment-version": "x402/1.0",
            # Missing other required headers
        }
        with pytest.raises(ValueError, match="Missing required header"):
            parse_402_response(headers)

    def test_parse_invalid_amount(self):
        headers = {
            "x-payment-version": "x402/1.0",
            "x-payment-network": "solana:devnet",
            "x-payment-amount": "not_a_number",
            "x-payment-token-mint": "So11111111111111111111111111111111111111112",
            "x-payment-address": "PikkyVau1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "x-payment-nonce": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            "x-payment-expires": str(int(time.time()) + 300),
        }
        with pytest.raises(ValueError, match="Invalid payment amount"):
            parse_402_response(headers)

    def test_parse_unsupported_version(self):
        headers = {
            "x-payment-version": "x402/99.0",
            "x-payment-network": "solana:devnet",
            "x-payment-amount": "10000000",
            "x-payment-token-mint": "So11111111111111111111111111111111111111112",
            "x-payment-address": "PikkyVau1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "x-payment-nonce": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            "x-payment-expires": str(int(time.time()) + 300),
        }
        with pytest.raises(ValueError, match="Unsupported x402 version"):
            parse_402_response(headers)

    def test_parse_case_insensitive_headers(self):
        headers = {
            "X-Payment-Version": "x402/1.0",
            "X-Payment-Network": "solana:devnet",
            "X-Payment-Amount": "10000000",
            "X-Payment-Token-Mint": "So11111111111111111111111111111111111111112",
            "X-Payment-Address": "PikkyVau1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "X-Payment-Nonce": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            "X-Payment-Expires": str(int(time.time()) + 300),
        }
        request = parse_402_response(headers)
        assert request.version == "x402/1.0"


class TestPaymentValidation:
    """Tests for payment header validation."""

    def test_validate_valid_headers(self, valid_payment_request):
        assert validate_payment_headers(valid_payment_request) is True

    def test_validate_expired_request(self):
        request = PaymentRequest(
            version="x402/1.0",
            network="solana:devnet",
            amount=10_000_000,
            token_mint="So11111111111111111111111111111111111111112",
            address="PikkyVau1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            nonce="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            expires_at=int(time.time()) - 60,  # Expired
        )
        assert validate_payment_headers(request) is False

    def test_validate_zero_amount(self):
        request = PaymentRequest(
            version="x402/1.0",
            network="solana:devnet",
            amount=0,
            token_mint="So11111111111111111111111111111111111111112",
            address="PikkyVau1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            nonce="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            expires_at=int(time.time()) + 300,
        )
        assert validate_payment_headers(request) is False

    def test_validate_negative_amount(self):
        request = PaymentRequest(
            version="x402/1.0",
            network="solana:devnet",
            amount=-100,
            token_mint="So11111111111111111111111111111111111111112",
            address="PikkyVau1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            nonce="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            expires_at=int(time.time()) + 300,
        )
        assert validate_payment_headers(request) is False

    def test_validate_empty_nonce(self):
        request = PaymentRequest(
            version="x402/1.0",
            network="solana:devnet",
            amount=10_000_000,
            token_mint="So11111111111111111111111111111111111111112",
            address="PikkyVau1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            nonce="",
            expires_at=int(time.time()) + 300,
        )
        assert validate_payment_headers(request) is False


class TestBuildPaymentHeaders:
    """Tests for building outgoing payment headers."""

    def test_build_headers_with_signature(self):
        headers = build_payment_headers(
            signature="txSig123abc",
            nonce="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        )
        assert headers["X-Payment-Signature"] == "txSig123abc"
        assert headers["X-Payment-Nonce"] == "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"

    def test_build_headers_returns_dict(self):
        headers = build_payment_headers(
            signature="txSig123",
            nonce="abc123",
        )
        assert isinstance(headers, dict)
        assert len(headers) == 2


class TestX402Handler:
    """Tests for the main x402 payment handler."""

    @pytest.mark.asyncio
    async def test_handle_402_response(self, handler, valid_payment_request):
        handler.solana_client = AsyncMock()
        handler.solana_client.send_payment.return_value = "txSig123"
        handler.solana_client.confirm_transaction.return_value = True

        result = await handler.handle_payment(valid_payment_request)
        assert result.status == PaymentStatus.VERIFIED
        assert result.signature == "txSig123"

    @pytest.mark.asyncio
    async def test_handle_expired_request(self, handler):
        expired_request = PaymentRequest(
            version="x402/1.0",
            network="solana:devnet",
            amount=10_000_000,
            token_mint="So11111111111111111111111111111111111111112",
            address="PikkyVau1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            nonce="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            expires_at=int(time.time()) - 60,
        )
        result = await handler.handle_payment(expired_request)
        assert result.status == PaymentStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_handle_payment_failure(self, handler, valid_payment_request):
        handler.solana_client = AsyncMock()
        handler.solana_client.send_payment.side_effect = Exception("Transaction failed")

        result = await handler.handle_payment(valid_payment_request)
        assert result.status == PaymentStatus.INVALID

    @pytest.mark.asyncio
    async def test_nonce_replay_protection(self, handler, valid_payment_request):
        handler.solana_client = AsyncMock()
        handler.solana_client.send_payment.return_value = "txSig123"
        handler.solana_client.confirm_transaction.return_value = True

        # First payment succeeds
        result1 = await handler.handle_payment(valid_payment_request)
        assert result1.status == PaymentStatus.VERIFIED

        # Same nonce should be rejected
        result2 = await handler.handle_payment(valid_payment_request)
        assert result2.status == PaymentStatus.REPLAYED

    @pytest.mark.asyncio
    async def test_amount_validation(self, handler):
        request = PaymentRequest(
            version="x402/1.0",
            network="solana:devnet",
            amount=100,  # Below minimum
            token_mint="So11111111111111111111111111111111111111112",
            address="PikkyVau1tXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            nonce=generate_nonce(),
            expires_at=int(time.time()) + 300,
        )
        result = await handler.handle_payment(request)
        assert result.status == PaymentStatus.INSUFFICIENT

    @pytest.mark.asyncio
    async def test_network_mismatch(self, handler, valid_payment_request):
        valid_payment_request.network = "solana:mainnet-beta"
        handler.config.network = "solana:devnet"

        result = await handler.handle_payment(valid_payment_request)
        assert result.status == PaymentStatus.INVALID

    def test_consumed_nonces_tracked(self, handler):
        nonce = generate_nonce()
        assert not handler.is_nonce_consumed(nonce)
        handler.consume_nonce(nonce)
        assert handler.is_nonce_consumed(nonce)

    def test_payment_result_fields(self):
        result = PaymentResult(
            status=PaymentStatus.VERIFIED,
            signature="txSig123",
            nonce="abc123",
            amount=10_000_000,
        )
        assert result.status == PaymentStatus.VERIFIED
        assert result.signature == "txSig123"
        assert result.nonce == "abc123"
        assert result.amount == 10_000_000


class TestX402EndpointPricing:
    """Tests for endpoint pricing configuration."""

    def test_trade_endpoint_pricing(self, handler):
        price = handler.get_price("/api/agent/trade")
        assert price == 10_000_000  # 0.01 SOL

    def test_analyze_endpoint_pricing(self, handler):
        price = handler.get_price("/api/agent/analyze")
        assert price == 5_000_000  # 0.005 SOL

    def test_free_endpoint(self, handler):
        price = handler.get_price("/api/portfolio")
        assert price == 0

    def test_unknown_endpoint_returns_default(self, handler):
        price = handler.get_price("/api/unknown/endpoint")
        assert price >= 0
