#!/usr/bin/env bash
# Bundles the Python sidecar into app/src-tauri/binaries, where Tauri's externalBin expects it.
set -euo pipefail
cd "$(dirname "$0")/.."

triple=$(rustc -vV | sed -n 's/^host: //p')
uv run --group build pyinstaller --noconfirm --onefile --name hippocampus-sidecar \
  --paths . --distpath build/dist --workpath build/work --specpath build \
  scripts/sidecar_entry.py
# Windows programs end in .exe; Tauri expects the same ending on the bundled copy.
suffix=""
case "$triple" in *windows*) suffix=".exe" ;; esac
mkdir -p app/src-tauri/binaries
cp "build/dist/hippocampus-sidecar$suffix" "app/src-tauri/binaries/hippocampus-sidecar-$triple$suffix"
echo "Bundled app/src-tauri/binaries/hippocampus-sidecar-$triple$suffix"
