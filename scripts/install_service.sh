#!/usr/bin/env bash
set -euo pipefail

if [ "${EUID}" -ne 0 ]; then
  echo "Ejecuta con sudo: sudo ./scripts/install_service.sh"
  exit 1
fi

APP_DIR_DEFAULT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${APP_DIR:-$APP_DIR_DEFAULT}"
SERVICE_NAME="${SERVICE_NAME:-yolo11-rtsp.service}"
APP_USER="${APP_USER:-${SUDO_USER:-$(id -un)}}"
APP_GROUP="${APP_GROUP:-$(id -gn "$APP_USER")}" 
ENV_FILE="${ENV_FILE:-/etc/yolo11-rtsp.env}"
TEMPLATE="$APP_DIR/deploy/systemd/yolo11-rtsp.service.template"

if [ ! -f "$TEMPLATE" ]; then
  echo "No existe template: $TEMPLATE"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  if [ -f "$APP_DIR/.env.example" ]; then
    install -m 600 "$APP_DIR/.env.example" "$ENV_FILE"
    echo "Se creó $ENV_FILE desde .env.example con permisos 600; edítalo antes de usar producción."
  else
    echo "No existe $ENV_FILE y no hay .env.example"
    exit 1
  fi
fi

chown root:root "$ENV_FILE"
chmod 600 "$ENV_FILE"

if [ -x "$APP_DIR/.venv/bin/uvicorn" ]; then
  UVICORN_BIN="$APP_DIR/.venv/bin/uvicorn"
else
  UVICORN_BIN="$(command -v uvicorn || true)"
fi

if [ -z "$UVICORN_BIN" ]; then
  echo "No se encontró uvicorn. Activa tu entorno o instala dependencias."
  exit 1
fi

TMP_SERVICE="$(mktemp)"
trap 'rm -f "$TMP_SERVICE"' EXIT

sed \
  -e "s|__APP_USER__|$APP_USER|g" \
  -e "s|__APP_GROUP__|$APP_GROUP|g" \
  -e "s|__APP_DIR__|$APP_DIR|g" \
  -e "s|__ENV_FILE__|$ENV_FILE|g" \
  -e "s|__UVICORN_BIN__|$UVICORN_BIN|g" \
  "$TEMPLATE" > "$TMP_SERVICE"

install -m 644 "$TMP_SERVICE" "/etc/systemd/system/$SERVICE_NAME"
systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"

systemctl --no-pager --full status "$SERVICE_NAME"
echo
echo "Variables sensibles en uso por systemd: $ENV_FILE"
