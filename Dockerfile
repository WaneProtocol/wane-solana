# syntax=docker/dockerfile:1.7
# Multi-stage build for the operator CLI. Engine programs are built separately
# via `anchor build` and shipped via solana-program-deploy, not via Docker.

FROM rust:1.78-slim-bookworm AS builder
RUN apt-get update \
    && apt-get install -y --no-install-recommends pkg-config libssl-dev ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app

# 1. cache layer: copy manifests + minimal placeholder sources so dependency
#    resolution can run before the full source is on the image.
COPY Cargo.toml Cargo.lock* rust-toolchain.toml ./
COPY programs/wane/Cargo.toml programs/wane/Cargo.toml
COPY programs/wane_vault/Cargo.toml programs/wane_vault/Cargo.toml
COPY cli/Cargo.toml cli/Cargo.toml
RUN mkdir -p programs/wane/src programs/wane_vault/src cli/src \
    && echo "pub fn _stub() {}" > programs/wane/src/lib.rs \
    && echo "pub fn _stub() {}" > programs/wane_vault/src/lib.rs \
    && echo "fn main() {}" > cli/src/main.rs \
    && cargo build --release -p wane-cli || true

# 2. real source
COPY programs programs
COPY cli cli
RUN cargo build --release -p wane-cli

# ---- runtime image ----
FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libssl3 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash --uid 1001 wane
COPY --from=builder /app/target/release/wane /usr/local/bin/wane

USER wane
WORKDIR /home/wane
ENTRYPOINT ["wane"]
CMD ["--help"]
