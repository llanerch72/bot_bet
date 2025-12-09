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

echo "[REMOTE] Activando venv..."
source venv/bin/activate

echo "[REMOTE] Instalando dependencias..."
pip install -r requirements.txt

# --- Lanzar el bot en tmux como daemon ---
if tmux has-session -t botbet 2>/dev/null; then
  echo "[REMOTE] Matando sesión tmux existente 'botbet'..."
  tmux kill-session -t botbet
fi

echo "[REMOTE] Lanzando nueva sesión tmux 'botbet'..."
tmux new-session -d -s botbet "cd $REMOTE_DIR && source venv/bin/activate && python main.py"

echo "[REMOTE] Deploy OK ✅ (bot ejecutándose en tmux 'botbet')"
EOF2
