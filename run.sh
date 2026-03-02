#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

SYSTEM_ENV_FILE="/etc/yolov11-rtsp.env"
LEGACY_ENV_FILE="/etc/yolo11-rtsp.env"

if [ -z "${ENV_FILE:-}" ]; then
  if [ -f "$SYSTEM_ENV_FILE" ]; then
    ENV_FILE="$SYSTEM_ENV_FILE"
  elif [ -f "$LEGACY_ENV_FILE" ]; then
    ENV_FILE="$LEGACY_ENV_FILE"
  else
    ENV_FILE=".env"
  fi
fi

export ENV_FILE
if [ -f "$ENV_FILE" ]; then
  if [ ! -r "$ENV_FILE" ]; then
    echo "No hay permisos de lectura para ENV_FILE=$ENV_FILE" >&2
    exit 1
  fi
  echo "Usando archivo de entorno: $ENV_FILE"
  set -a
  # shellcheck disable=SC1091
  source "$ENV_FILE"
  set +a
fi

exec uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
