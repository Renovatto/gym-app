# GymApp

App de treino, dieta, peso, água e objetivos. Touch-first, multi-idioma (pt-BR, en, es).

## Stack

- **Frontend**: SvelteKit (SPA estática via `adapter-static`, pronta para Capacitor) + Tailwind CSS 4 + Paraglide JS (i18n)
- **Backend**: FastAPI + SQLite (WAL) + SQLModel, auth JWT (access + refresh)

## Rodando em desenvolvimento

Backend (porta 8000):

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # primeira vez
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Frontend (porta 5173, ou a próxima livre):

```bash
cd frontend
npm install          # primeira vez
npm run dev
```

A URL da API pode ser sobrescrita com `VITE_API_URL` (padrão `http://localhost:8000`).
Docs interativas da API: http://localhost:8000/docs

## Configuração do backend

Variáveis de ambiente com prefixo `GYMAPP_` (ou arquivo `backend/.env`):

- `GYMAPP_SECRET_KEY` — **obrigatória em produção** (assina os JWTs)
- `GYMAPP_DATABASE_URL` — padrão `sqlite:///backend/gymapp.db`
- `GYMAPP_CORS_ORIGINS` — lista JSON de origens permitidas

## Fases do projeto

1. ✅ Fundação — auth, perfil, motor de metas (Mifflin-St Jeor/TDEE/macros/água), i18n, LGPD (exportar/excluir conta)
2. Peso + Água (histórico, quick-add)
3. Treino (catálogo, rotinas, templates, execução) — prioridade nº 1
4. Dieta (módulo opcional: alimentos TACO/USDA, receitas, diário)
5. PWA
6. Capacitor + Bluetooth da balança (protocolo OKOK/Chipsea)
7. Monetização (assinatura; anúncios como segunda alavanca)
