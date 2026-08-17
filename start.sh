#!/usr/bin/env bash
# Sobe backend (FastAPI) e frontend (SvelteKit) em portas fora do padrão,
# expostos na rede local para acesso pelo celular (--host). Ctrl+C encerra os dois.
set -euo pipefail

API_PORT=8765
WEB_PORT=5175

ROOT="$(cd "$(dirname "$0")" && pwd)"

# Acha a primeira porta livre a partir de $1 (subindo de 1 em 1). Sem isso, um
# start.sh anterior ainda rodando (ou outro app na mesma porta) derruba o script
# com "address already in use" em vez de simplesmente usar outra porta.
find_free_port() {
  local port="$1"
  while lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; do
    port=$((port + 1))
  done
  echo "$port"
}

RESOLVED_API_PORT="$(find_free_port "$API_PORT")"
RESOLVED_WEB_PORT="$(find_free_port "$WEB_PORT")"
if [ "$RESOLVED_API_PORT" != "$API_PORT" ]; then
  echo "==> Porta $API_PORT ocupada, backend vai subir em $RESOLVED_API_PORT"
fi
if [ "$RESOLVED_WEB_PORT" != "$WEB_PORT" ]; then
  echo "==> Porta $WEB_PORT ocupada, frontend vai subir em $RESOLVED_WEB_PORT"
fi
API_PORT="$RESOLVED_API_PORT"
WEB_PORT="$RESOLVED_WEB_PORT"

# IP na rede local (para abrir no celular). Tenta Wi-Fi (en0) e cabo (en1).
LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo localhost)"

# --- Backend ---------------------------------------------------------------
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  echo "==> Criando venv e instalando dependências do backend..."
  python3 -m venv .venv
  .venv/bin/pip install --quiet -r requirements.txt
fi
# --host 0.0.0.0 torna a API acessível por outros aparelhos da rede.
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port "$API_PORT" &
BACK_PID=$!

# --- Frontend ---------------------------------------------------------------
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  echo "==> Instalando dependências do frontend..."
  npm install
fi
# --host expõe o vite na rede. Sem VITE_API_URL, o front deriva a API do host
# acessado (localhost no PC, IP da rede no celular); VITE_API_PORT avisa a porta
# real do backend, que pode ter mudado se a padrão estava ocupada.
VITE_API_PORT="$API_PORT" npm run dev -- --host --port "$WEB_PORT" --strictPort &
FRONT_PID=$!

trap 'kill "$BACK_PID" "$FRONT_PID" 2>/dev/null' INT TERM EXIT

echo ""
echo "  No PC:      http://localhost:$WEB_PORT"
echo "  No celular: http://$LAN_IP:$WEB_PORT   (mesma rede Wi-Fi)"
echo "  API:        http://$LAN_IP:$API_PORT   (docs em /docs)"
echo ""

wait
