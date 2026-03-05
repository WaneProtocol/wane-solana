#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────
# PIKKY Development Environment Setup
# ─────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo ""
echo "  PIKKY - Development Environment Setup"
echo "  ======================================"
echo ""

# ─────────────────────────────────────────────
# Check prerequisites
# ─────────────────────────────────────────────

check_command() {
    if command -v "$1" &> /dev/null; then
        local version
        version=$("$1" --version 2>&1 | head -1)
        log_ok "$1 found: $version"
        return 0
    else
        log_error "$1 not found. Please install it first."
        return 1
    fi
}

log_info "Checking prerequisites..."
echo ""

MISSING=0
check_command "rustc"   || MISSING=1
check_command "cargo"   || MISSING=1
check_command "node"    || MISSING=1
check_command "npm"     || MISSING=1
check_command "python3" || MISSING=1
check_command "solana"  || MISSING=1
check_command "anchor"  || MISSING=1

echo ""

if [ "$MISSING" -eq 1 ]; then
    log_error "Missing prerequisites. Install them and re-run this script."
    echo ""
    echo "  Install guides:"
    echo "    Rust:    https://rustup.rs"
    echo "    Node.js: https://nodejs.org"
    echo "    Python:  https://python.org"
    echo "    Solana:  https://docs.anza.xyz/cli/install"
    echo "    Anchor:  https://www.anchor-lang.com/docs/installation"
    echo ""
    exit 1
fi

# ─────────────────────────────────────────────
# Rust toolchain components
# ─────────────────────────────────────────────

log_info "Installing Rust components..."
rustup component add rustfmt clippy 2>/dev/null || true
log_ok "Rust components ready"

# ─────────────────────────────────────────────
# Build Solana program
# ─────────────────────────────────────────────

if [ -d "$PROJECT_ROOT/programs" ]; then
    log_info "Building Solana program..."
    cd "$PROJECT_ROOT/programs"
    cargo build 2>&1 | tail -1
    log_ok "Solana program built"

    log_info "Running Rust tests..."
    cargo test 2>&1 | tail -3
    log_ok "Rust tests passed"
else
    log_warn "programs/ directory not found, skipping Rust build"
fi

# ─────────────────────────────────────────────
# TypeScript SDK
# ─────────────────────────────────────────────

if [ -d "$PROJECT_ROOT/sdk" ]; then
    log_info "Installing SDK dependencies..."
    cd "$PROJECT_ROOT/sdk"
    npm ci 2>&1 | tail -1
    log_ok "SDK dependencies installed"

    log_info "Building SDK..."
    npm run build 2>&1 | tail -1
    log_ok "SDK built"

    log_info "Running SDK tests..."
    npm test 2>&1 | tail -3
    log_ok "SDK tests passed"
else
    log_warn "sdk/ directory not found, skipping TypeScript setup"
fi

# ─────────────────────────────────────────────
# Python Agent
# ─────────────────────────────────────────────

if [ -d "$PROJECT_ROOT/agent" ]; then
    log_info "Setting up Python virtual environment..."
    cd "$PROJECT_ROOT/agent"

    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi

    source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null

    log_info "Installing Python dependencies..."
    pip install -q -r requirements.txt 2>&1 | tail -1
    if [ -f "requirements-dev.txt" ]; then
        pip install -q -r requirements-dev.txt 2>&1 | tail -1
    fi
    log_ok "Python dependencies installed"

    log_info "Running Python tests..."
    pytest tests/ -q 2>&1 | tail -3
    log_ok "Python tests passed"
else
    log_warn "agent/ directory not found, skipping Python setup"
fi

# ─────────────────────────────────────────────
# Solana local config
# ─────────────────────────────────────────────

log_info "Configuring Solana CLI for localhost..."
solana config set --url localhost 2>/dev/null || true

if [ ! -f "$HOME/.config/solana/id.json" ]; then
    log_info "Generating local keypair..."
    solana-keygen new --no-bip39-passphrase --silent 2>/dev/null || true
    log_ok "Local keypair generated"
else
    log_ok "Solana keypair exists"
fi

# ─────────────────────────────────────────────
# Environment file
# ─────────────────────────────────────────────

if [ ! -f "$PROJECT_ROOT/.env" ]; then
    log_info "Creating .env from example..."
    if [ -f "$PROJECT_ROOT/.env.example" ]; then
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
    else
        cat > "$PROJECT_ROOT/.env" << 'ENVEOF'
# PIKKY Environment Configuration
SOLANA_RPC_URL=http://localhost:8899
SOLANA_WS_URL=ws://localhost:8900
PIKKY_ENV=development
PIKKY_LOG_LEVEL=debug
ENVEOF
    fi
    log_ok ".env file created"
fi

# ─────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────

echo ""
echo "  ======================================"
echo "  Setup complete."
echo ""
echo "  Next steps:"
echo "    1. Start local validator:  solana-test-validator"
echo "    2. Deploy program:         anchor deploy"
echo "    3. Run all tests:          ./scripts/test.sh"
echo ""
echo "  Documentation:  docs/"
echo "  Contributing:   CONTRIBUTING.md"
echo "  ======================================"
echo ""
