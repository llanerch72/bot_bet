#!/usr/bin/env bash
set -euo pipefail

SERVER_USER_HOST="root@38.242.236.14"
REMOTE_DIR="/root/bot-bet"
COMMIT_MSG="${1:-chore: auto-deploy}"

echo "🔄 [LOCAL] Haciendo commit y push..."
git status --short

if [ -n "$(git status --porcelain)" ]; then
  git add .
  git commit -m "$COMMIT_MSG"
  git push
else
  echo "✅ No hay cambios locales, solo haremos deploy del código ya pusheado."
fi

echo "🚀 [REMOTE] Actualizando proyecto en el servidor..."
ssh "$SERVER_USER_HOST" << 'EOF2'
set -e

cd /root/bot-bet

echo "[REMOTE] Guardando cambios locales (stash)..."
git stash save "backup-auto-before-deploy" || true

echo "[REMOTE] git pull..."
git pull

echo "[REMOTE] Preparando venv..."
if [ ! -d "venv" ]; then
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

echo "[REMOTE] Ejecutando bot (prueba inmediata)..."
python main.py --force || true

# =========================
# Reiniciar web en tmux
# =========================
SESSION="botbet-web"
CMD="cd /root/bot-bet && source venv/bin/activate && python -m uvicorn bot_bet.webapp.app:app --host 127.0.0.1 --port 8000"

if tmux has-session -t "\$SESSION" 2>/dev/null; then
  echo "[REMOTE] Reiniciando web: matando sesión tmux '\$SESSION'..."
  tmux kill-session -t "\$SESSION"
fi

echo "[REMOTE] Levantando web en tmux '\$SESSION'..."
tmux new-session -d -s "\$SESSION" "\$CMD"

echo "[REMOTE] ✅ Deploy OK (web levantada en tmux '\$SESSION')"
EOF2
