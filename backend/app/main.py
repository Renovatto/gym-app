from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .routers import (
    account,
    achievements,
    auth,
    coach,
    diet,
    profile,
    stats,
    supplements,
    water,
    weight,
    workout,
)
from .seed import seed_exercises, seed_foods


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    seed_exercises()
    seed_foods()
    yield


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
)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(weight.router)
app.include_router(water.router)
app.include_router(workout.router)
app.include_router(diet.router)
app.include_router(stats.router)
app.include_router(coach.router)
app.include_router(achievements.router)
app.include_router(account.router)
app.include_router(supplements.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
