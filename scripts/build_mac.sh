#!/usr/bin/env bash
# Builds "Cursor Usage Bar.app" into dist/. Pass --install to copy it to /Applications and launch it.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt pyinstaller==6.16.0
.venv/bin/pyinstaller --noconfirm --clean --distpath dist --workpath build packaging/cursor_usage_bar.spec

APP="dist/Cursor Usage Bar.app"
echo "Gerado: $APP"

if [[ "${1:-}" == "--install" ]]; then
  osascript -e 'quit app "Cursor Usage Bar"' 2>/dev/null || true
  pkill -f "Cursor Usage Bar.app" 2>/dev/null || true
  rm -rf "/Applications/Cursor Usage Bar.app"
  cp -R "$APP" /Applications/
  open "/Applications/Cursor Usage Bar.app"
  echo "Instalado em /Applications e aberto."
fi
