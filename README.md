# GymApp

App de treino, dieta, peso, água e objetivos. Touch-first, multi-idioma (pt-BR, en, es).

## Stack

- **Frontend**: SvelteKit (SPA estática via `adapter-static`, pronta para Capacitor) + Tailwind CSS 4 + Paraglide JS (i18n)
- **Backend**: FastAPI + PostgreSQL + SQLModel, auth JWT (access + refresh)

## Rodando em desenvolvimento

Sobe o Postgres local uma vez (mesma major que produção, Postgres 18):

```bash
docker compose up -d
```

Depois:

```bash
./start.sh
```

Instala as dependências na primeira execução e sobe os dois servidores
(portas fora do padrão para não conflitar com outros projetos):

- **App**: http://localhost:5175
- **API**: http://localhost:8765 (docs interativas em `/docs`)

Para rodar separado: `backend/.venv/bin/uvicorn app.main:app --reload --port 8765`
e `cd frontend && npm run dev -- --port 5175`. A URL da API pode ser sobrescrita
com `VITE_API_URL` (padrão `http://localhost:8765`).

Para zerar o banco local: `docker compose down -v` (apaga o volume) e sobe de
novo com `docker compose up -d` — o schema e o catálogo (exercícios/alimentos)
voltam sozinhos no próximo boot do backend.

## Configuração do backend

Variáveis de ambiente com prefixo `GYMAPP_` (ou arquivo `backend/.env`):

- `GYMAPP_SECRET_KEY` — **obrigatória em produção** (assina os JWTs)
- `GYMAPP_DATABASE_URL` — **obrigatória**, sem default (ex.:
  `postgresql://gymapp:gymapp@localhost:5434/gymapp` para o Postgres do
  `docker-compose.yml`). De propósito: um default silencioso já fez a gente achar
  que tinha perdido dados quando na verdade era só a variável ausente.
- `GYMAPP_CORS_ORIGINS` — lista JSON de origens permitidas

## Fases do projeto

1. ✅ Fundação — auth, perfil, motor de metas (Mifflin-St Jeor/TDEE/macros/água), i18n, LGPD (exportar/excluir conta)
2. Peso + Água (histórico, quick-add)
3. Treino (catálogo, rotinas, templates, execução) — prioridade nº 1
4. Dieta (módulo opcional: alimentos TACO/USDA, receitas, diário)
5. PWA
6. Capacitor + Bluetooth da balança (protocolo OKOK/Chipsea)
7. Monetização (assinatura; anúncios como segunda alavanca)
