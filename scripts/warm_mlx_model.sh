#!/bin/zsh
set -euo pipefail

ROOT_DIR="${LOCAL_REVIEW_HOME:-$(cd "$(dirname "$0")/.." && pwd)}"
export PYTHONPATH="$ROOT_DIR"

exec "$ROOT_DIR/venv/bin/python" -m review_runner.mlx_review_client --warmup
