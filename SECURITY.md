# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |
| < 0.1   | No        |

## Reporting a Vulnerability

The PIKKY team takes security seriously. If you discover a security vulnerability,
please report it responsibly.

### Process

1. **Do NOT open a public GitHub issue.** Security vulnerabilities must be reported
   privately to avoid exposing users to risk.

2. **Send an email** to security@pikky.sol with the following information:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

3. **Response timeline**:
   - Acknowledgment within 48 hours
   - Initial assessment within 5 business days
   - Fix timeline communicated within 10 business days

4. **Disclosure**: We follow coordinated disclosure. We will work with you on
   a timeline for public disclosure after a fix is available.

### Scope

The following are in scope for security reports:

- **Solana Program vulnerabilities**: unauthorized fund access, PDA collision,
  integer overflow/underflow, missing signer checks, missing account validation,
  reinitialization attacks, CPI injection

- **x402 Payment flow**: payment bypass, replay attacks, signature forgery,
  payment verification bypass, double-spend scenarios

- **SDK vulnerabilities**: private key exposure, insecure defaults,
  transaction manipulation

- **Agent vulnerabilities**: prompt injection (if LLM-integrated), credential
  leakage, unauthorized trade execution, strategy manipulation

### Out of Scope

- Vulnerabilities in third-party dependencies (report to upstream)
- Issues in Solana runtime or validator software
- Social engineering attacks
- Denial of service attacks on public RPC endpoints

## Security Practices

### On-Chain Program

- All accounts are validated with Anchor constraints
- PDAs use deterministic seeds with bump verification
- Arithmetic uses checked operations to prevent overflow
- Signer checks on all privileged instructions
- Reentrancy guards on state-mutating instructions
- Program is non-upgradeable on mainnet

### x402 Payment Verification

- Payments are verified on-chain before granting access
- Transaction signatures are validated against expected parameters
- Replay protection via nonce tracking
- Payment amount and recipient are verified
- Timeout enforcement on payment windows

### SDK

- No private keys stored in plaintext
- All RPC calls use HTTPS
- Transaction simulation before submission
- Configurable confirmation commitment levels

### Agent

- API keys stored in environment variables only
- No hardcoded credentials
- Rate limiting on trade execution
- Position size limits enforced
- Kill switch for emergency stop

## Audit Status

| Audit | Status | Date |
|-------|--------|------|
| Internal review | Complete | 2025-Q1 |
| External audit | Planned | TBD |

## Bug Bounty

We are planning a bug bounty program. Details will be announced on
https://x.com/pikkydotsol.

Severity classifications:

| Severity | Description | Reward Range |
|----------|-------------|-------------|
| Critical | Direct loss of funds, program takeover | TBD |
| High | Unauthorized trading, payment bypass | TBD |
| Medium | Strategy manipulation, data leakage | TBD |
| Low | Minor issues, documentation errors | TBD |

## Contact

- Security reports: security@pikky.sol
- General questions: https://x.com/pikkydotsol
