#!/bin/zsh
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 /absolute/target/path"
  exit 1
fi

TARGET_ROOT="$1"
SOURCE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$TARGET_ROOT/review_runner"
mkdir -p "$TARGET_ROOT/scripts"
mkdir -p "$TARGET_ROOT/deploy"
cp "$SOURCE_ROOT/review_runner/"*.py "$TARGET_ROOT/review_runner/"
cp "$SOURCE_ROOT/review_runner/requirements.txt" "$TARGET_ROOT/review_runner/"
cp "$SOURCE_ROOT/scripts/run_webhook_server.sh" "$TARGET_ROOT/scripts/"
cp "$SOURCE_ROOT/deploy/nginx-pr-review.conf" "$TARGET_ROOT/deploy/"

if [[ ! -d "$TARGET_ROOT/venv" ]]; then
  python3 -m venv "$TARGET_ROOT/venv"
fi

"$TARGET_ROOT/venv/bin/pip" install --upgrade pip
"$TARGET_ROOT/venv/bin/pip" install -r "$TARGET_ROOT/review_runner/requirements.txt"

cat <<EOF
Installed local review runner into:
  $TARGET_ROOT

Start the webhook server with:
  LOCAL_REVIEW_HOME=$TARGET_ROOT zsh $TARGET_ROOT/scripts/run_webhook_server.sh
EOF
