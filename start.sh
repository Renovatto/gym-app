#!/usr/bin/env bash
# Sobe backend (FastAPI) e frontend (SvelteKit) em portas fora do padrão,
# expostos na rede local para acesso pelo celular (--host). Ctrl+C encerra os dois.
set -euo pipefail

API_PORT=8765
WEB_PORT=5175

ROOT="$(cd "$(dirname "$0")" && pwd)"

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
# acessado (localhost no PC, IP da rede no celular).
npm run dev -- --host --port "$WEB_PORT" --strictPort &
FRONT_PID=$!

trap 'kill "$BACK_PID" "$FRONT_PID" 2>/dev/null' INT TERM EXIT

echo ""
echo "  No PC:      http://localhost:$WEB_PORT"
echo "  No celular: http://$LAN_IP:$WEB_PORT   (mesma rede Wi-Fi)"
echo "  API:        http://$LAN_IP:$API_PORT   (docs em /docs)"
echo ""

wait
