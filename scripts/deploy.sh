#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────
# PIKKY Solana Program Deployment
# ─────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# ─────────────────────────────────────────────
# Parse arguments
# ─────────────────────────────────────────────

NETWORK="${1:-devnet}"
SKIP_TESTS="${2:-false}"

case "$NETWORK" in
    localnet)
        RPC_URL="http://localhost:8899"
        ;;
    devnet)
        RPC_URL="https://api.devnet.solana.com"
        ;;
    mainnet|mainnet-beta)
        RPC_URL="https://api.mainnet-beta.solana.com"
        NETWORK="mainnet-beta"
        ;;
    *)
        log_error "Unknown network: $NETWORK. Use: localnet, devnet, or mainnet"
        ;;
esac

echo ""
echo "  PIKKY - Solana Program Deployment"
echo "  ======================================"
echo "  Network:  $NETWORK"
echo "  RPC URL:  $RPC_URL"
echo "  ======================================"
echo ""

# ─────────────────────────────────────────────
# Safety checks
# ─────────────────────────────────────────────

if [ "$NETWORK" = "mainnet-beta" ]; then
    log_warn "MAINNET DEPLOYMENT - This is irreversible!"
    echo ""
    read -r -p "  Type 'DEPLOY' to confirm mainnet deployment: " CONFIRM
    if [ "$CONFIRM" != "DEPLOY" ]; then
        log_error "Deployment cancelled."
    fi
    echo ""
fi

# Check Solana CLI
if ! command -v solana &> /dev/null; then
    log_error "Solana CLI not found. Install: https://docs.anza.xyz/cli/install"
fi

# Check Anchor CLI
if ! command -v anchor &> /dev/null; then
    log_error "Anchor CLI not found. Install: https://www.anchor-lang.com/docs/installation"
fi

# Check keypair
DEPLOYER=$(solana address 2>/dev/null || true)
if [ -z "$DEPLOYER" ]; then
    log_error "No Solana keypair found. Run: solana-keygen new"
fi

log_info "Deployer: $DEPLOYER"

# Check balance
BALANCE=$(solana balance --url "$RPC_URL" 2>/dev/null | awk '{print $1}')
log_info "Balance: $BALANCE SOL"

MIN_BALANCE="2"
if (( $(echo "$BALANCE < $MIN_BALANCE" | bc -l 2>/dev/null || echo "0") )); then
    if [ "$NETWORK" = "devnet" ]; then
        log_warn "Low balance. Requesting airdrop..."
        solana airdrop 2 --url "$RPC_URL" || log_warn "Airdrop failed, continuing..."
    else
        log_warn "Balance may be insufficient for deployment."
    fi
fi

# ─────────────────────────────────────────────
# Run tests (unless skipped)
# ─────────────────────────────────────────────

if [ "$SKIP_TESTS" != "true" ] && [ "$SKIP_TESTS" != "skip-tests" ]; then
    log_info "Running tests before deployment..."
    cd "$PROJECT_ROOT"

    if [ -d "programs" ]; then
        log_info "Running Rust tests..."
        cd programs && cargo test --quiet && cd ..
        log_ok "Rust tests passed"
    fi

    log_info "Running Anchor tests..."
    anchor test --skip-deploy 2>&1 | tail -5
    log_ok "Anchor tests passed"
else
    log_warn "Skipping tests (--skip-tests flag set)"
fi

# ─────────────────────────────────────────────
# Build
# ─────────────────────────────────────────────

log_info "Building program..."
cd "$PROJECT_ROOT"
anchor build 2>&1 | tail -3
log_ok "Program built successfully"

# Get program ID from keypair
PROGRAM_KEYPAIR="$PROJECT_ROOT/target/deploy/pikky-keypair.json"
if [ -f "$PROGRAM_KEYPAIR" ]; then
    PROGRAM_ID=$(solana address -k "$PROGRAM_KEYPAIR" 2>/dev/null)
    log_info "Program ID: $PROGRAM_ID"
else
    log_error "Program keypair not found at $PROGRAM_KEYPAIR"
fi

# ─────────────────────────────────────────────
# Deploy
# ─────────────────────────────────────────────

log_info "Deploying to $NETWORK..."
anchor deploy --provider.cluster "$RPC_URL" 2>&1
log_ok "Program deployed successfully"

# ─────────────────────────────────────────────
# Verify
# ─────────────────────────────────────────────

log_info "Verifying deployment..."
ACCOUNT_INFO=$(solana account "$PROGRAM_ID" --url "$RPC_URL" 2>/dev/null | head -5)
if echo "$ACCOUNT_INFO" | grep -q "Program"; then
    log_ok "Program verified on-chain"
else
    log_warn "Could not verify program. Check manually."
fi

# ─────────────────────────────────────────────
# Update IDL (devnet/mainnet only)
# ─────────────────────────────────────────────

if [ "$NETWORK" != "localnet" ]; then
    IDL_PATH="$PROJECT_ROOT/target/idl/pikky.json"
    if [ -f "$IDL_PATH" ]; then
        log_info "Uploading IDL..."
        anchor idl init "$PROGRAM_ID" \
            --filepath "$IDL_PATH" \
            --provider.cluster "$RPC_URL" 2>/dev/null || \
        anchor idl upgrade "$PROGRAM_ID" \
            --filepath "$IDL_PATH" \
            --provider.cluster "$RPC_URL" 2>/dev/null || \
        log_warn "IDL upload failed. Upload manually."
    fi
fi

# ─────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────

echo ""
echo "  ======================================"
echo "  Deployment Complete"
echo ""
echo "  Network:     $NETWORK"
echo "  Program ID:  $PROGRAM_ID"
echo "  Deployer:    $DEPLOYER"
echo "  ======================================"
echo ""
