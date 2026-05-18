# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.1] - 2026-06

### Fixed
- Vault screen could be bypassed by omitting the antibody account; the account
  is now bound to the destination by PDA seeds and the screen is mandatory.

### Added
- `withdraw` and `update_policy` instructions on the vault.
- `update_config`, two-step governor transfer, and registry pause.

## [0.3.0] - 2026-05

### Added
- Non-custodial session vault: enroll, deposit, screened `wane_execute`.
- Registry threat screen via CPI account-load (`is_enforceable` shared rule).

## [0.2.0] - 2026-04

### Added
- Antibody economy: stake, corroborate, challenge, resolve, slash, claim.
- `$WANE` SPL staking with a config-PDA-owned stake vault.

## [0.1.0] - 2026-03

### Added
- Initial antibody registry: one PDA per `(kind, subject)`, genesis seeding.
- Anchor workspace, TypeScript SDK skeleton, litesvm end-to-end harness.

[0.4.1]: https://github.com/WaneProtocol/wane-solana/releases/tag/v0.4.1
[0.3.0]: https://github.com/WaneProtocol/wane-solana/releases/tag/v0.3.0
[0.2.0]: https://github.com/WaneProtocol/wane-solana/releases/tag/v0.2.0
[0.1.0]: https://github.com/WaneProtocol/wane-solana/releases/tag/v0.1.0
