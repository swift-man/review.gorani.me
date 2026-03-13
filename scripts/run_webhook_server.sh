#!/bin/zsh
set -euo pipefail

if [[ $# -gt 0 ]]; then
  echo "usage: $0"
  exit 1
fi

ROOT_DIR="${LOCAL_REVIEW_HOME:-$(cd "$(dirname "$0")/.." && pwd)}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

export PYTHONPATH="$ROOT_DIR"
exec "$ROOT_DIR/venv/bin/uvicorn" review_runner.webhook_app:app --host "$HOST" --port "$PORT"
