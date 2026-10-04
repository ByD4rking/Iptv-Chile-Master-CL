#!/usr/bin/env bash
set -euo pipefail
command -v ares-package >/dev/null || { echo "ares-package no instalado"; exit 78; }
cd "$(dirname "$0")"
rm -rf .build
mkdir .build
cp appinfo.json index.html player.js .build/
cp ../shared/player.js .build/
ares-package .build -o .
find . -maxdepth 1 -name '*.ipk' -print