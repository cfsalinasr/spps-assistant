#!/usr/bin/env bash
# Freezes the spps_assistant.api sidecar into a standalone executable via
# PyInstaller and stages it where electron-builder's extraResources config
# expects it (desktop/resources/sidecar/). Run before `electron-builder`
# for any target platform — desktop/package.json's build:mac/build:win
# scripts call this automatically.
#
# Runs on macOS, Linux, and Windows (via Git Bash, which is what GitHub's
# windows-latest runners use for `shell: bash` steps).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# python3.11 is this project's convention everywhere else (dev-mode sidecar
# spawn, local tooling) since it's the one guaranteed-correct interpreter on
# a macOS/Linux dev machine (bare python3/python may resolve to something
# older). CI's windows-latest runner (actions/setup-python, pinned to 3.11)
# exposes its interpreter as `python` instead, so fall back for portability
# rather than assuming python3.11 exists everywhere.
PYTHON_BIN="${SPPS_PYTHON_BIN:-python3.11}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN=python
  fi
fi

if ! "$PYTHON_BIN" -m PyInstaller --version >/dev/null 2>&1; then
  echo "PyInstaller not found for $PYTHON_BIN. Install it first:" >&2
  echo "  $PYTHON_BIN -m pip install -e '.[packaging]'" >&2
  exit 1
fi

rm -rf packaging/build packaging/dist packaging/spps-sidecar.spec
rm -rf desktop/resources/sidecar

"$PYTHON_BIN" -m PyInstaller \
  --onedir \
  --name spps-sidecar \
  --distpath packaging/dist \
  --workpath packaging/build \
  --specpath packaging \
  --paths . \
  --noconfirm \
  packaging/sidecar_entry.py

mkdir -p desktop/resources
cp -R packaging/dist/spps-sidecar desktop/resources/sidecar

echo "Frozen sidecar staged at desktop/resources/sidecar/"
