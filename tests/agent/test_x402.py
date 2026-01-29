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
