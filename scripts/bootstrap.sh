#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PATCH_PATH="${ROOT_DIR}/patches/litellm-1.82.6-anthropic-responses.patch"

rm -rf "${VENV_DIR}"
python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install -U pip >/dev/null
"${VENV_DIR}/bin/pip" install "litellm[proxy]==1.82.6" >/dev/null

SITE_PACKAGES="$("${VENV_DIR}/bin/python" - <<'PY'
import site

for path in site.getsitepackages():
    if path.endswith("site-packages"):
        print(path)
        break
else:
    raise SystemExit("site-packages path not found")
PY
)"

patch -p1 -d "${SITE_PACKAGES}" < "${PATCH_PATH}"

echo "Bootstrap complete."
echo "Venv: ${VENV_DIR}"
echo "Site-packages: ${SITE_PACKAGES}"
