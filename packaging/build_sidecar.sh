#!/usr/bin/env bash
# Freezes the spps_assistant.api sidecar into a standalone executable via
# PyInstaller and stages it where electron-builder's extraResources config
# expects it (desktop/resources/sidecar/). Run before `electron-builder`
# for any target platform — desktop/package.json's build:mac/build:win
# scripts call this automatically.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if ! python3.11 -m PyInstaller --version >/dev/null 2>&1; then
  echo "PyInstaller not found for python3.11. Install it first:" >&2
  echo "  python3.11 -m pip install -e '.[packaging]'" >&2
  exit 1
fi

rm -rf packaging/build packaging/dist packaging/spps-sidecar.spec
rm -rf desktop/resources/sidecar

python3.11 -m PyInstaller \
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

echo "Frozen sidecar staged at desktop/resources/sidecar/spps-sidecar"
