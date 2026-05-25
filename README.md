<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&color=0:0a0e15,100:16243a&height=170&section=header&text=Wane%20Solana&fontColor=eaf0f8&fontSize=46&fontAlignY=40&desc=Shared%20on-chain%20immune%20memory%20and%20a%20screening%20session%20vault%20for%20AI%20agents&descSize=15&descAlignY=64" alt="Wane Solana"/>
</p>

<p align="center">
  <a href="https://github.com/WaneProtocol/wane-solana/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-3FE0E0?style=for-the-badge" alt="license"/></a>
  <a href="https://github.com/WaneProtocol/wane-solana/actions"><img src="https://img.shields.io/github/actions/workflow/status/WaneProtocol/wane-solana/ci.yml?style=for-the-badge&label=ci" alt="ci"/></a>
  <img src="https://img.shields.io/badge/chain-Solana-9945FF?style=for-the-badge" alt="solana"/>
  <img src="https://img.shields.io/badge/framework-Anchor-2b6cb0?style=for-the-badge" alt="anchor"/>
  <img src="https://img.shields.io/badge/lang-Rust%20%2B%20TypeScript-dea584?style=for-the-badge" alt="lang"/>
  <a href="https://wane.network"><img src="https://img.shields.io/badge/site-wane.network-eaf0f8?style=for-the-badge" alt="website"/></a>
  <a href="https://x.com/wanedotnetwork"><img src="https://img.shields.io/badge/X-@wanedotnetwork-1DA1F2?style=for-the-badge" alt="x"/></a>
</p>

Shared on-chain immune memory for AI agents, with a non-custodial session wallet that screens outflows before value moves.

When one agent gets drained, the address (or call pattern, bytecode, or semantic fingerprint) is published once as an antibody. Every other agent that reads the registry before signing is then immune to the same threat. Reading is a plain account lookup, so there is no view call and no per-read cost.

This is the Solana port of the Base/EVM Wane protection layer.

## Architecture

```mermaid
flowchart LR
  A[AI agent] -->|check before sign| R[wane_registry<br/>antibody PDAs]
  A -->|owns session| V[wane_vault<br/>funds in PDA]
  V -->|CPI account-load| R
  V -->|clean recipient| D[destination]
  V -. flagged: revert .-> D
  P[reporter] -->|stake WANE| R
  C[challenger] -->|dispute| R
```
