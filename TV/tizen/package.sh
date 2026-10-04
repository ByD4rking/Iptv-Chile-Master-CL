#!/usr/bin/env bash
set -euo pipefail
if [ -z "${TIZEN_SDK_ROOT:-}" ]; then echo "TIZEN_SDK_ROOT no configurado"; exit 78; fi
BIN="$TIZEN_SDK_ROOT/tools/ide/bin/tizen"
[ -x "$BIN" ] || { echo "Tizen CLI no encontrado: $BIN"; exit 78; }
cd "$(dirname "$0")"
rm -rf .build .out
mkdir .build .out
cp config.xml index.html player.js .build/
cp ../shared/player.js .build/
"$BIN" package -t wgt -s TV -o .out .build
find .out -name '*.wgt' -print