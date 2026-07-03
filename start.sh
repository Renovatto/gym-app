#!/usr/bin/env bash
# Sobe backend (FastAPI) e frontend (SvelteKit) em portas fora do padrão,
# para não conflitar com outros projetos. Ctrl+C encerra os dois.
set -euo pipefail

API_PORT=8765
WEB_PORT=5175

ROOT="$(cd "$(dirname "$0")" && pwd)"

# --- Backend ---------------------------------------------------------------
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  echo "==> Criando venv e instalando dependências do backend..."
  python3 -m venv .venv
  .venv/bin/pip install --quiet -r requirements.txt
fi
.venv/bin/uvicorn app.main:app --reload --port "$API_PORT" &
BACK_PID=$!

# --- Frontend ---------------------------------------------------------------
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  echo "==> Instalando dependências do frontend..."
  npm install
fi
VITE_API_URL="http://localhost:$API_PORT" npm run dev -- --port "$WEB_PORT" --strictPort &
FRONT_PID=$!

trap 'kill "$BACK_PID" "$FRONT_PID" 2>/dev/null' INT TERM EXIT

echo ""
echo "  App:  http://localhost:$WEB_PORT"
echo "  API:  http://localhost:$API_PORT  (docs em /docs)"
echo ""

wait
