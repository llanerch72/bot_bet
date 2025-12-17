#!/usr/bin/env bash
set -euo pipefail

# === CONFIGURACIÓN ===
SERVER_USER_HOST="root@38.242.236.14"
REMOTE_DIR="/root/bot-bet"
COMMIT_MSG="${1:-chore: auto-deploy}"

echo "🔄 [LOCAL] Haciendo commit y push..."
git status --short

# Añade todo y crea commit solo si hay cambios
if [ -n "$(git status --porcelain)" ]; then
  git add .
  git commit -m "$COMMIT_MSG"
  git push
else
  echo "✅ No hay cambios locales, solo haremos deploy del código ya pusheado."
fi

echo "🚀 [REMOTE] Actualizando proyecto en el servidor..."
ssh "$SERVER_USER_HOST" << EOF2
set -e

cd "$REMOTE_DIR"

echo "[REMOTE] git pull..."
git pull

echo "[REMOTE] Preparando venv..."
if [ ! -d "venv" ]; then
  echo "[REMOTE] venv no existe. Creándolo..."
  # Asegura que existe el módulo venv
  apt-get update -y
  apt-get install -y python3-venv
  python3 -m venv venv
fi

echo "[REMOTE] Activando venv..."
source venv/bin/activate

echo "[REMOTE] Upgrading pip..."
python -m pip install --upgrade pip

echo "[REMOTE] Instalando dependencias..."
pip install -r requirements.txt

echo "[REMOTE] Ejecutando python main.py --force (prueba inmediata)..."
python main.py --force

echo "[REMOTE] Deploy OK ✅"
EOF2
