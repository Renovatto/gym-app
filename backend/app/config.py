from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    secret_key: str = "dev-secret-change-me-in-production"
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    # Sem default de proposito: um SQLite silencioso aqui ja fez a gente "perder"
    # dados por meia hora quando a variavel sumiu do ambiente. Sem ela, o boot
    # falha alto em vez de criar um banco vazio sem avisar. Dev usa o Postgres do
    # docker-compose.yml (ver README.md); CI exporta a URL explicitamente.
    database_url: str
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
    # SMTP para e-mail transacional (hoje so a redefinicao de senha). Sem
    # smtp_user preenchido o envio cai no modo stub, que apenas imprime no log:
    # assim o ambiente de desenvolvimento nao precisa de credencial nenhuma.
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    # Nome que aparece como remetente na caixa de entrada de quem recebe.
    smtp_from_name: str = "Gym App"

    model_config = {"env_prefix": "GYMAPP_", "env_file": ".env"}


settings = Settings()
