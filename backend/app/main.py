import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import run_migrations
from .routers import (
    account,
    achievements,
    activities,
    admin,
    auth,
    coach,
    cycle,
    diet,
    feedback,
    news,
    profile,
    push,
    reminders,
    sharing,
    stats,
    supplements,
    water,
    weight,
    workout,
)
from .seed import seed_exercises, seed_foods
from .services.push import push_enabled, run_rest_timer_loop
from .services.reminders import run_reminder_loop


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # As migracoes vem antes das sementes: semear so faz sentido com o schema pronto.
    run_migrations()
    seed_exercises()
    seed_foods()
    # Laco que envia os avisos de fim de descanso por push. Sem chaves VAPID nao ha
    # para onde enviar, entao nem sobe.
    # O laco dos lembretes (refeicao, pesagem, sequencia) segue a mesma regra.
    background_tasks = (
        [asyncio.create_task(run_rest_timer_loop()), asyncio.create_task(run_reminder_loop())]
        if push_enabled()
        else []
    )
    yield
    for task in background_tasks:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Gym App API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # cors_origins cobre o dev (localhost); frontend_url cobre o dominio de producao
    # (definido por GYMAPP_FRONTEND_URL, ex.: https://gymapp-web.onrender.com).
    allow_origins=[*settings.cors_origins, settings.frontend_url],
    # Libera também IPs da rede local (celular acessando via --host), em qualquer porta.
    allow_origin_regex=(
        r"http://(localhost|127\.0\.0\.1|"
        r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"192\.168\.\d{1,3}\.\d{1,3}|"
        r"172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(:\d+)?"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Sem expor explicitamente, o navegador esconde do JavaScript qualquer cabecalho
    # que nao seja da lista basica do CORS. Retry-After e o que diz a tela de login
    # quantos minutos faltam do bloqueio por tentativas.
    expose_headers=["Retry-After"],
)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(weight.router)
app.include_router(water.router)
app.include_router(workout.router)
app.include_router(diet.router)
app.include_router(stats.router)
app.include_router(coach.router)
app.include_router(cycle.router)
app.include_router(achievements.router)
app.include_router(feedback.router)
app.include_router(account.router)
app.include_router(supplements.router)
app.include_router(activities.router)
app.include_router(sharing.router)
app.include_router(news.router)
app.include_router(push.router)
app.include_router(reminders.router)
app.include_router(admin.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
