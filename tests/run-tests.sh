#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m unittest discover -s "$ROOT_DIR/tests" -p 'test_*.py' -v

if [[ "${1:-}" == "--runtime" ]]; then
  python3 "$ROOT_DIR/tests/runtime_smoke.py"
fi
