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
