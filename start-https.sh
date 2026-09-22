#!/usr/bin/env bash
# Sobe o app num endereço HTTPS público e temporário (túnel do Cloudflare), para
# testar no celular o que só funciona em contexto seguro: câmera (código de
# barras), service worker e o modo offline. Pelo IP da rede em http o navegador
# nem oferece essas APIs — não é bug do app, é regra do navegador.
#
# Diferenças para o start.sh:
#   - roda o BUILD (npm run preview), não o dev, porque o service worker só
#     existe no build — sem ele não dá para testar o offline;
#   - a API passa por /api no mesmo endereço (proxy do vite, ver vite.config.ts),
#     então não há CORS nem segunda URL para configurar.
#
# Ctrl+C encerra os três processos.
set -euo pipefail

API_PORT=8765
WEB_PORT=4173

ROOT="$(cd "$(dirname "$0")" && pwd)"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared não encontrado. Instale com:  brew install cloudflared"
  exit 1
fi

find_free_port() {
  local port="$1"
  while lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; do
    port=$((port + 1))
  done
  echo "$port"
}

API_PORT="$(find_free_port "$API_PORT")"
WEB_PORT="$(find_free_port "$WEB_PORT")"

# --- Backend ---------------------------------------------------------------
cd "$ROOT/backend"
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT" &
BACK_PID=$!

# --- Frontend (build + preview) --------------------------------------------
cd "$ROOT/frontend"
echo "==> Gerando o build..."
# VITE_API_URL=/api faz o cliente chamar o próprio endereço; o proxy do vite
# entrega ao backend. Mesma origem: o navegador não envolve CORS.
VITE_API_URL=/api npm run build >/dev/null
VITE_API_PROXY="http://127.0.0.1:$API_PORT" npm run preview -- --port "$WEB_PORT" --strictPort >/dev/null &
FRONT_PID=$!

# --- Túnel HTTPS ------------------------------------------------------------
LOG="$(mktemp -t gymapp-tunnel)"
cloudflared tunnel --url "http://localhost:$WEB_PORT" --no-autoupdate >"$LOG" 2>&1 &
TUNNEL_PID=$!

trap 'kill "$BACK_PID" "$FRONT_PID" "$TUNNEL_PID" 2>/dev/null' INT TERM EXIT

echo "==> Abrindo o túnel..."
URL=""
for _ in $(seq 1 40); do
  URL="$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOG" | head -1 || true)"
  [ -n "$URL" ] && break
  sleep 1
done

echo ""
if [ -n "$URL" ]; then
  echo "  No celular: $URL"
  echo "  (endereço novo a cada execução; o túnel é temporário)"
else
  echo "  Não consegui ler a URL do túnel. Log: $LOG"
fi
echo "  No PC:      http://localhost:$WEB_PORT"
echo "  API:        http://127.0.0.1:$API_PORT/docs"
echo ""
echo "  Para testar offline: instale pela tela de início, abra uma vez com rede"
echo "  (o service worker guarda a casca) e depois ligue o modo avião."
echo ""

wait
