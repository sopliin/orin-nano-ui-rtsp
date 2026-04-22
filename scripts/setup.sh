#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

# --system-site-packages reutiliza el torch y opencv instalados por JetPack (con CUDA)
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Se creó .env desde .env.example"
fi

echo "Listo. Edita .env y ejecuta: ./run.sh"
