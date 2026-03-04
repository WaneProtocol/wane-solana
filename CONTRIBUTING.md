# Contributing to PIKKY

Thank you for your interest in contributing to PIKKY. This guide covers everything
you need to get started.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Release Process](#release-process)

## Code of Conduct

This project follows the [Contributor Covenant](https://www.contributor-covenant.org/)
code of conduct. By participating, you are expected to uphold this standard.

## Getting Started

PIKKY has three main components, each with its own language and toolchain:

| Component | Language | Directory |
|-----------|----------|-----------|
| Solana Program | Rust | `programs/` |
| SDK | TypeScript | `sdk/` |
| Trading Agent | Python | `agent/` |

You can contribute to any component independently. You do not need all three
toolchains installed unless you are working on integration tests.

## Development Setup

### Prerequisites

- **Rust** 1.75+ with `cargo`
- **Node.js** 20+ with `npm`
- **Python** 3.11+ with `pip`
- **Solana CLI** 1.18+
- **Anchor** 0.30+
- **Git**

### Quick Setup

```bash
git clone https://github.com/pikkydotsol/pikky.git
cd pikky
chmod +x scripts/setup.sh
./scripts/setup.sh
```

### Manual Setup

#### Solana Program

```bash
cd programs
cargo build
cargo test
```

#### TypeScript SDK

```bash
cd sdk
npm install
npm run build
npm test
```

#### Python Agent

```bash
cd agent
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
pip install -r requirements-dev.txt
pytest
```

### Local Validator

For integration testing, run a local Solana validator:

```bash
solana-test-validator --reset
```

## Project Structure

```
pikky/
  programs/           # Solana on-chain program (Rust/Anchor)
    src/
      lib.rs          # Program entrypoint
      instructions/   # Instruction handlers
      state/          # Account state definitions
      errors.rs       # Custom error types
      x402.rs         # x402 payment verification
  sdk/                # TypeScript SDK
    src/
      client.ts       # Main client class
      x402.ts         # x402 payment utilities
      mbti.ts         # MBTI strategy definitions
      types.ts        # Type definitions
  agent/              # Python trading agent
    src/
      engine.py       # Core trading engine
      strategies.py   # MBTI strategy implementations
      x402_handler.py # x402 payment handler
      market.py       # Market data fetcher
  tests/              # Cross-component tests
    sdk/              # SDK unit tests
    agent/            # Agent unit tests
    integration/      # Integration tests
  docs/               # Documentation
  scripts/            # Build and deploy scripts
```

## Development Workflow

### 1. Create a Branch

Branch from `main` for all changes:

```bash
git checkout main
git pull origin main
git checkout -b feat/your-feature-name
```

Use these branch prefixes:

| Prefix | Purpose |
|--------|---------|
| `feat/` | New features |
| `fix/` | Bug fixes |
| `refactor/` | Code refactoring |
| `docs/` | Documentation changes |
| `test/` | Test additions or fixes |
| `ci/` | CI/CD changes |

### 2. Make Changes

- Write code following the coding standards below.
- Add or update tests for your changes.
- Update documentation if behavior changes.

### 3. Test Locally

```bash
# Run all tests for the component you changed
cargo test              # Rust
npm test                # TypeScript
pytest                  # Python

# Run integration tests
pytest tests/integration/
```

### 4. Commit

Write clear commit messages:

```
feat(agent): add ENFP momentum breakout strategy

Implement the ENFP trading strategy with enthusiasm-weighted
momentum indicators and social sentiment integration.
```

Format: `type(scope): description`

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `ci`, `chore`

Scopes: `program`, `sdk`, `agent`, `x402`, `mbti`

### 5. Push and Open a PR

```bash
git push -u origin feat/your-feature-name
```

Open a pull request against `main` using the PR template.

## Coding Standards

### Rust (Solana Program)

- Follow standard Rust formatting (`cargo fmt`)
- Zero clippy warnings (`cargo clippy -- -D warnings`)
- All public functions must have doc comments
- Use `thiserror` for error definitions
- Validate all accounts explicitly
- Prefer checked math operations (`checked_add`, `checked_mul`)
- No `unwrap()` in production code; use proper error handling

```rust
// Good
let result = amount
    .checked_mul(rate)
    .ok_or(PikkyError::MathOverflow)?;

// Bad
let result = amount * rate;
```

### TypeScript (SDK)

- Use strict TypeScript (`strict: true` in tsconfig)
- Format with Prettier (2-space indent, single quotes, trailing commas)
- Lint with ESLint
- Export types alongside implementations
- All public methods must have JSDoc comments
- Use `async/await` over raw Promises

```typescript
// Good
export async function deposit(
  connection: Connection,
  wallet: Wallet,
  amount: number,
): Promise<TransactionSignature> {
  // ...
}

// Bad
export function deposit(connection, wallet, amount) {
  return new Promise((resolve, reject) => { /* ... */ });
}
```

### Python (Agent)

- Format with `ruff format`
- Lint with `ruff check`
- Type hints on all function signatures
- Docstrings on all public functions (Google style)
- Use `dataclasses` or `pydantic` for data structures
- Async where I/O is involved

```python
# Good
async def execute_trade(
    self,
    signal: TradeSignal,
    mbti_type: MBTIType,
) -> TradeResult:
    """Execute a trade based on signal and personality parameters.

    Args:
        signal: The trade signal to execute.
        mbti_type: MBTI personality type for strategy selection.

    Returns:
        TradeResult with execution details.

    Raises:
        InsufficientFundsError: If wallet balance is too low.
    """
```

## Testing

### Unit Tests

Every new function or method should have corresponding tests.

- **Rust**: Tests in the same file or in `tests/` directory.
- **TypeScript**: Tests in `tests/sdk/` using Jest.
- **Python**: Tests in `tests/agent/` using pytest.

### Integration Tests

Integration tests live in `tests/integration/` and test the full flow
from SDK calls through the agent to the on-chain program.

### Test Naming

```
test_<function>_<scenario>_<expected_result>
```

Example: `test_deposit_insufficient_balance_returns_error`

### Coverage

We aim for the following minimum coverage:

| Component | Target |
|-----------|--------|
| Solana Program | 90% |
| SDK | 85% |
| Agent | 85% |

## Pull Request Process

1. Fill out the PR template completely.
2. Ensure all CI checks pass.
3. Request review from at least one maintainer.
4. Address all review comments.
5. Squash-merge after approval.

### Review Criteria

- Code follows the standards above.
- Tests are included and pass.
- No security vulnerabilities introduced.
- On-chain changes have been tested on localnet and devnet.
- Documentation is updated if behavior changes.

## Release Process

Releases follow semantic versioning:

- **Major**: Breaking changes to SDK API or on-chain account schema.
- **Minor**: New features, new MBTI strategies, new x402 capabilities.
- **Patch**: Bug fixes, documentation updates, dependency bumps.

Only maintainers can publish releases. The process:

1. Update version numbers across all components.
2. Update CHANGELOG.md.
3. Create a signed Git tag.
4. CI builds and publishes artifacts.

## Questions

If you have questions about contributing, open a GitHub Discussion or
reach out on X at https://x.com/pikkydotsol.
