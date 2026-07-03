from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    secret_key: str = "dev-secret-change-me-in-production"
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    database_url: str = f"sqlite:///{Path(__file__).resolve().parent.parent / 'gymapp.db'}"
    # Portas do vite em dev (5173+ conforme disponibilidade) e do Capacitor futuro.
    cors_origins: list[str] = [
        f"http://{host}:{port}"
        for host in ("localhost", "127.0.0.1")
        for port in range(5173, 5180)
    ]

    model_config = {"env_prefix": "GYMAPP_", "env_file": ".env"}


settings = Settings()
