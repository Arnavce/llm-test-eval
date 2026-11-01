#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup_env.sh - reproducible environment bootstrap for llm-test-eval
#
# Creates .venv, installs requirements.txt, and (on macOS only) prepares an
# ad-hoc-signed copy of the interpreter that can load the wheel-installed
# native extensions used by numpy/scipy/matplotlib.  Some hardened-runtime
# Python distributions refuse to load unsigned .so files with
# "code signature ... not valid for use in process"; the signed copy fixes
# that without touching the system Python.
#
# Usage:
#   ./setup_env.sh          # create/reuse .venv and install requirements
#   source .venv/bin/activate && python -V
# ---------------------------------------------------------------------------
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

PYTHON="${PYTHON:-python3}"

echo "[setup] using $($PYTHON --version 2>&1)"
"$PYTHON" -m venv .venv
./.venv/bin/python -m pip install --upgrade pip >/dev/null
./.venv/bin/python -m pip install -r requirements.txt

if [[ "$(uname -s)" == "Darwin" ]]; then
  echo "[setup] preparing macOS-compatible interpreter copy"
  cp .venv/bin/python3 .venv/bin/python-local
  cat > .venv/dsh-entitlements.plist <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>com.apple.security.cs.disable-library-validation</key><true/>
</dict></plist>
PLIST
  codesign --force --sign - --entitlements .venv/dsh-entitlements.plist \
    .venv/bin/python-local >/dev/null 2>&1 || true
  echo "[setup] wrote .venv/bin/python-local (use this if the default python cannot import numpy)"
fi

echo
echo "[setup] done.  Activate with:  source .venv/bin/activate"
echo "[setup] smoke test:           python run_experiments.py --mock --runs 5 --skip-mutation"
