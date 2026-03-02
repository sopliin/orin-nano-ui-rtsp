#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

ENV_FILE="${ENV_FILE:-.env}"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ENV_FILE"
  set +a
fi

exec uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
