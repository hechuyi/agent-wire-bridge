# Architecture

## Overview

This repository is an overlay project, not a full proxy rewrite.

It treats LiteLLM as the upstream runtime and makes our custom behavior reproducible by applying a narrow patch to the Anthropic `messages` to OpenAI `responses` adapter path.

## Layers

### 1. Upstream runtime

LiteLLM provides:

- local HTTP server
- model routing
- OpenAI-compatible upstream transport
- general proxy plumbing

### 2. Bridge patch

The patch only targets:

- `handler.py`
- `streaming_iterator.py`
- `transformation.py`

Those files contain the request and streaming translation logic that matters for Claude-style clients.

### 3. Local launch wiring

The launch script resolves the upstream endpoint and credentials from the local Codex configuration, then starts LiteLLM with the project config.

It also forces the LiteLLM proxy to use the standard `asyncio` loop. This compensates for upstream `litellm==1.82.6` hard-coding `uvloop` on non-Windows platforms, which currently fails on Python `3.14`.

## Why patch instead of vendoring

Vendoring the whole LiteLLM tree would make the repository larger, noisier, and harder to upgrade. A focused patch keeps the maintenance surface narrow and makes the custom behavior legible.

## Current compatibility assumptions

The repository currently assumes:

- Anthropic-compatible ingress via `v1/messages`
- OpenAI-compatible egress via `responses`
- Claude-facing aliases `cc-opus`, `cc-sonnet`, `cc-haiku`
- upstream `responses` middleboxes may reject deprecated `user`

## Main invariants

These should remain true across upgrades:

- embedded reminder blocks can become `instructions`
- cached-token accounting survives the translation layer
- Anthropic metadata can still influence prompt caching
- deprecated or middlebox-hostile fields do not leak into the final Responses payload

## Upgrade workflow

When LiteLLM changes:

1. install a clean pinned LiteLLM copy
2. diff the clean copy against the current working runtime
3. regenerate the patch
4. rerun `python3 scripts/verify_transform.py`
5. only then test live traffic
