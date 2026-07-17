from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    secret_key: str = "dev-secret-change-me-in-production"
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    database_url: str = f"sqlite:///{Path(__file__).resolve().parent.parent / 'gymapp.db'}"
    # URL base do frontend, usada em links de e-mail (ex.: redefinir senha).
    frontend_url: str = "http://localhost:5175"
    # Validade do token de redefinicao de senha, em minutos.
    password_reset_minutes: int = 30
    # Portas do vite em dev (5173+ conforme disponibilidade) e do Capacitor futuro.
    cors_origins: list[str] = [
        f"http://{host}:{port}"
        for host in ("localhost", "127.0.0.1")
        for port in range(5173, 5180)
    ]
    # E-mails com acesso de administrador (ex.: ver os feedbacks). Definido por env
    # (GYMAPP_ADMIN_EMAILS) em producao. Allowlist evita adicionar coluna is_admin na
    # tabela users (que nao migraria sozinha no Postgres).
    admin_emails: list[str] = []

    model_config = {"env_prefix": "GYMAPP_", "env_file": ".env"}


settings = Settings()
