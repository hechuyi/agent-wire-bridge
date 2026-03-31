#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
CONFIG_PATH="${ROOT_DIR}/config/litellm-config.yaml"
PORT="${LITELLM_PORT:-4000}"

if [[ ! -x "${VENV_DIR}/bin/litellm" ]]; then
  echo "Patched LiteLLM runtime not found. Run ./scripts/bootstrap.sh first." >&2
  exit 1
fi

eval "$(
  python3 - <<'PY'
import json
import pathlib
import shlex
import sys
import tomllib

home = pathlib.Path.home()
config_path = home / ".codex" / "config.toml"
auth_path = home / ".codex" / "auth.json"

try:
    config = tomllib.loads(config_path.read_text())
except FileNotFoundError:
    print("echo '.codex/config.toml not found' >&2")
    print("exit 1")
    sys.exit(0)

try:
    auth = json.loads(auth_path.read_text())
except FileNotFoundError:
    print("echo '.codex/auth.json not found' >&2")
    print("exit 1")
    sys.exit(0)

provider_name = config.get("model_provider")
providers = config.get("model_providers", {})
provider = providers.get(provider_name, {})
base_url = provider.get("base_url")
api_key = auth.get("OPENAI_API_KEY")

if not base_url:
    print("echo 'No upstream base_url found in .codex/config.toml' >&2")
    print("exit 1")
    sys.exit(0)

if not api_key:
    print("echo 'No OPENAI_API_KEY found in .codex/auth.json' >&2")
    print("exit 1")
    sys.exit(0)

print(f"export LITELLM_UPSTREAM_BASE_URL={shlex.quote(base_url)}")
print(f"export LITELLM_UPSTREAM_API_KEY={shlex.quote(api_key)}")
PY
)"

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
