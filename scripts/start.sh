#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
CONFIG_PATH="${ROOT_DIR}/config/litellm-config.yaml"
OVERRIDES_DIR="${ROOT_DIR}/overrides"
PORT="${LITELLM_PORT:-4000}"

if [[ ! -x "${VENV_DIR}/bin/litellm" ]]; then
  echo "Patched LiteLLM runtime not found. Run ./scripts/bootstrap.sh first." >&2
  exit 1
fi

eval "$(
  python3 - <<'PY'
import json
import os
import pathlib
import shlex
import sys
import tomllib

home = pathlib.Path.home()
config_path = home / ".codex" / "config.toml"
auth_path = home / ".codex" / "auth.json"
upstream_env_path = home / ".config" / "litellm-claude-codex" / "upstream.env"


def load_env_file(path: pathlib.Path) -> dict[str, str]:
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return {}

    values: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")

    return values


base_url = os.getenv("LITELLM_UPSTREAM_BASE_URL")
api_key = os.getenv("LITELLM_UPSTREAM_API_KEY")

if not base_url or not api_key:
    upstream_env = load_env_file(upstream_env_path)
    base_url = base_url or upstream_env.get("LITELLM_UPSTREAM_BASE_URL")
    api_key = api_key or upstream_env.get("LITELLM_UPSTREAM_API_KEY")

if not base_url:
    try:
        config = tomllib.loads(config_path.read_text())
    except FileNotFoundError:
        config = {}

    provider_name = config.get("model_provider")
    providers = config.get("model_providers", {})
    provider = providers.get(provider_name, {})
    base_url = provider.get("base_url")

if not api_key:
    try:
        auth = json.loads(auth_path.read_text())
    except FileNotFoundError:
        auth = {}

    api_key = auth.get("OPENAI_API_KEY")

if not base_url:
    print(
        "echo 'No upstream base_url found in env, ~/.config/litellm-claude-codex/upstream.env, or .codex/config.toml' >&2"
    )
    print("exit 1")
    sys.exit(0)

if not api_key:
    print(
        "echo 'No upstream api key found in env, ~/.config/litellm-claude-codex/upstream.env, or .codex/auth.json' >&2"
    )
    print("exit 1")
    sys.exit(0)

print(f"export LITELLM_UPSTREAM_BASE_URL={shlex.quote(base_url)}")
print(f"export LITELLM_UPSTREAM_API_KEY={shlex.quote(api_key)}")
PY
)"

if [[ -d "${OVERRIDES_DIR}" ]]; then
  export PYTHONPATH="${OVERRIDES_DIR}${PYTHONPATH:+:${PYTHONPATH}}"
fi

export LITELLM_DISABLE_OPENAI_RESPONSES_INPUT_TOKENS="${LITELLM_DISABLE_OPENAI_RESPONSES_INPUT_TOKENS:-1}"
export DISABLE_AIOHTTP_TRANSPORT="${DISABLE_AIOHTTP_TRANSPORT:-True}"

exec "${VENV_DIR}/bin/python" - "${CONFIG_PATH}" "${PORT}" <<'PY'
import sys

from litellm.proxy.proxy_cli import ProxyInitializationHelpers, run_server

config_path = sys.argv[1]
port = sys.argv[2]

# LiteLLM 1.82.6 hard-codes uvloop on non-Windows platforms. That fails on
# Python 3.14 today, so the launcher forces standard asyncio instead.
ProxyInitializationHelpers._get_loop_type = staticmethod(lambda: "asyncio")
sys.argv = [
    "litellm",
    "--config",
    config_path,
    "--host",
    "127.0.0.1",
    "--port",
    port,
]
run_server.main(standalone_mode=False)
PY
