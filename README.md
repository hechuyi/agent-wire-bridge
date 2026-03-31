# agent-wire-bridge

`agent-wire-bridge` turns a locally working Claude-compatible bridge into a reproducible, reviewable repository.

The project keeps LiteLLM as a pinned upstream runtime and stores our custom compatibility layer as:

- a patch bundle against `litellm==1.82.6`
- bootstrap and launch scripts
- redacted fixtures
- verification utilities
- architecture notes

## Why this exists

The original setup worked, but the important behavior lived in hidden runtime files under a private virtualenv. That made upgrades, review, rollback, and sharing unnecessarily hard.

This repository makes the custom layer explicit.

## What the patch changes

The patch focuses on Anthropic `v1/messages` to OpenAI `responses` compatibility:

- preserve Claude model alias reasoning behavior after proxy-side model resolution
- normalize cached token usage mapping
- lift embedded `<system-reminder>` blocks into `instructions`
- avoid replaying assistant `thinking` blocks as plain text
- stabilize tool call identifiers
- derive a stable `prompt_cache_key` from Anthropic metadata
- omit `user` and `safety_identifier` in Responses requests for middleboxes that reject them

## Repository layout

```text
agent-wire-bridge/
  config/
  docs/
  fixtures/
  patches/
  scripts/
```

## Quick start

1. Create the local runtime and apply the patch:

   ```bash
   bash scripts/bootstrap.sh
   ```

2. Verify the patched request transformation:

   ```bash
   python3 scripts/verify_transform.py
   ```

3. Start the local Claude-compatible bridge on `127.0.0.1:4000`:

   ```bash
   bash scripts/start.sh
   ```

`start.sh` reads:

- `~/.codex/config.toml` for the upstream OpenAI-compatible base URL
- `~/.codex/auth.json` for `OPENAI_API_KEY`

It does not store credentials in this repository.

`bootstrap.sh` recreates the repository-local `.venv` on each run so the patch application stays deterministic.
`start.sh` launches LiteLLM through a tiny Python wrapper that forces `asyncio` instead of `uvloop`, because LiteLLM `1.82.6` hard-codes `uvloop` and that currently breaks on Python `3.14`.

## Verification target

The main regression guarded here is request-shape safety for OpenAI Responses middleboxes.

Expected transformed payload shape:

- `prompt_cache_key`: present
- `user`: absent
- `safety_identifier`: absent

This matches the observed Codex request shape and avoids the `502` failure mode seen on middleboxes that reject the deprecated `user` field.

## Notes

- This repository intentionally does not vendor LiteLLM source.
- The patch is pinned to `litellm==1.82.6`.
- If LiteLLM is upgraded, regenerate the patch against a fresh clean install before trusting runtime behavior.
