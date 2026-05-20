# Contributing to Wane

Thanks for considering a contribution. This document is a short, opinionated
guide that gets you from a clean checkout to a merged PR with the minimum
amount of friction.

## Ground rules

- One concern per PR. Mixed PRs are hard to review and slow to merge.
- Tests live next to the code they exercise: `src/<module>.rs` and
  `src/<module>_test.rs` in Rust, `*.test.ts` in TypeScript.
- New public APIs require a short doc comment and one usage example.
- We follow [Conventional Commits](https://www.conventionalcommits.org)
  (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`, `perf:`).

## Local setup

```bash
git clone https://github.com/WaneProtocol/wane-solana
cd wane

# Anchor engine
anchor build
anchor test --skip-local-validator

# CLI
cargo build --release -p wane-cli

# SDK
cd sdk && npm install && npm test && npm run build
```

You need:

- Rust >= 1.78 (`rustup install stable`)
- Solana CLI 1.18.x (`sh -c "$(curl -sSfL https://release.solana.com/v1.18.26/install)"`)
- Anchor 0.31.x via [avm](https://www.anchor-lang.com/docs/installation)
- Node.js 20+ for the SDK / examples

## Before submitting

1. `cargo fmt --all` and `cargo clippy -p wane_registry -- -W warnings`.
2. `cd sdk && npm run format:check && npm run lint && npm test`.
3. Update `CHANGELOG.md` under `## Unreleased`.
4. If you touched account layouts or instructions, regenerate the IDL with
   `anchor build` and commit `target/idl/wane_registry.json` if it changed.

## Reporting bugs

Open an issue with the **Bug Report** template. Reproductions on devnet are
worth their weight; include the transaction signature, expected vs actual
behavior, and the engine commit hash you tested against.

## Proposing features

Open a **Feature Request** issue first. New signal types in particular need
governance discussion before code lands.

## Security

If you find a vulnerability, please follow the disclosure path in
[`SECURITY.md`](./SECURITY.md). Do not open a public issue.

## Code of conduct

This project follows the
[Contributor Covenant 2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
See [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md).
