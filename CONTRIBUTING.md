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
