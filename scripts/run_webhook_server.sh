#!/bin/zsh
set -euo pipefail

if [[ $# -gt 0 ]]; then
  echo "usage: $0"
  exit 1
fi

ROOT_DIR="${LOCAL_REVIEW_HOME:-$(cd "$(dirname "$0")/.." && pwd)}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

: "${GITHUB_TOKEN:?Set GITHUB_TOKEN before starting the webhook server}"
: "${GITHUB_WEBHOOK_SECRET:?Set GITHUB_WEBHOOK_SECRET before starting the webhook server}"

cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR"
exec "$ROOT_DIR/venv/bin/uvicorn" review_runner.webhook_app:app --host "$HOST" --port "$PORT"
