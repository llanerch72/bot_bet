#!/usr/bin/env bash
set -euo pipefail

SERVER_IP="38.242.236.14"
SERVER_USER_HOST="root@$SERVER_IP"
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
ssh "$SERVER_USER_HOST" << EOF2
set -e

cd "$REMOTE_DIR"

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
CMD="cd $REMOTE_DIR && source venv/bin/activate && python -m uvicorn bot_bet.webapp.app:app --host 127.0.0.1 --port 8000"

if tmux has-session -t "\$SESSION" 2>/dev/null; then
  echo "[REMOTE] Reiniciando web: matando sesión tmux '\$SESSION'..."
  tmux kill-session -t "\$SESSION"
fi

echo "[REMOTE] Levantando web en tmux '\$SESSION'..."
tmux new-session -d -s "\$SESSION" "\$CMD"

echo "[REMOTE] ✅ Deploy OK (web levantada en tmux '\$SESSION')"
EOF2

# =========================
# Verificación final desde local
# =========================
echo ""
echo "🌍 Verificando despliegue en http://$SERVER_IP ..."

STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://$SERVER_IP)

if [[ "$STATUS_CODE" == "200" ]]; then
  echo "✅ ¡El servidor responde correctamente en http://$SERVER_IP"
else
  echo "❌ El servidor NO está respondiendo como se esperaba. Código HTTP: $STATUS_CODE"
  echo "   Revisa los logs con: tmux attach -t botbet-web"
fi
