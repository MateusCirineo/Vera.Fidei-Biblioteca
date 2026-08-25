import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Vera.fidei"
    database_url: str = "postgresql://vera:vera123@localhost:5432/vera_fidei"
    elasticsearch_url: str = "http://localhost:9200"
    chroma_path: str = "./chroma_db"
    embedding_model: str = "BAAI/bge-m3"
    embedding_device: str = "auto"
    llm_enabled: bool = False
    # Provider: "anthropic" | "groq" | "google"
    llm_provider: str = "groq"
    # Modelos padrão por provider (sobrescreva no .env se quiser outro):
    #   groq:      "llama-3.3-70b-versatile" (grátis, rápido)
    #   google:    "gemini-2.0-flash" (grátis, rápido)
    #   anthropic: "claude-haiku-4-5-20251001"
    llm_model: str = "llama-3.3-70b-versatile"
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    groq_api_key: str = os.environ.get("GROQ_API_KEY", "")
    google_api_key: str = os.environ.get("GOOGLE_API_KEY", "")
    api_key: str = ""
    jwt_secret: str = "CHANGE_ME_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 dias
    owner_email: str = "mateuscirineo@gmail.com"
    vera_environment: str = "development"
    site_url: str = "https://verafidei.oialfred.com"
    usage_reset_timezone: str = "America/Sao_Paulo"

    # E-mail (Resend)
    resend_api_key: str = ""
    email_from: str = "Vera.Fidei <noreply@verafidei.oialfred.com>"
    support_email: str = "vera.fidei661@gmail.com"

    # Instagram (Graph API) — publicação do card diário
    instagram_access_token: str = ""
    instagram_business_account_id: str = ""
    instagram_graph_api_version: str = "v21.0"
    # Publicar exige as duas chaves abaixo. O padrão seguro é somente gerar
    # prévias; a ativação vem depois da aprovação visual do template.
    instagram_publish_enabled: bool = False
    instagram_credentials_rotated_at: str = ""
    # Exceção efêmera e explícita para uma única execução manual. Nunca deve
    # ser gravada em .env nem utilizada pelo agendador.
    instagram_allow_exposed_credentials_once: bool = False
    instagram_schedule_enabled: bool = False
    instagram_schedule_timezone: str = "America/Sao_Paulo"

    # Deploy do servidor (Hetzner) — hospeda publicamente as imagens do card diário
    deploy_ssh_host: str = ""
    deploy_ssh_user: str = "root"
    deploy_ssh_password: str = ""
    deploy_ssh_key_path: str = ""
    deploy_ssh_known_hosts: str = ""
    deploy_social_cards_dir: str = "/var/www/verafidei-social-cards"
    deploy_social_cards_public_base_url: str = "https://verafidei.oialfred.com/social-cards"

    # Identidade visual e auditoria do Instagram
    social_body_font_path: str = "C:/Windows/Fonts/ARLRDBD.TTF"
    social_output_dir: str = "scripts/output/instagram"
    social_ledger_path: str = "data/social/instagram_posts.jsonl"
    social_style_approval_path: str = "data/social/style.approval.json"

    # Billing
    billing_provider: str = "stripe"
    billing_recipient_name: str = ""
    billing_recipient_bank: str = ""
    billing_recipient_pix_key: str = ""
    billing_pix_payload: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_portal_configuration_id: str = ""
    stripe_payment_method_types: str = "card,pix"
    stripe_price_catequista: str = ""
    stripe_price_apologeta: str = ""
    stripe_price_patristico: str = ""
    stripe_price_magisterio: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


def validate_runtime_security() -> None:
    if settings.vera_environment.strip().lower() not in {"production", "prod"}:
        return
    secret = settings.jwt_secret.strip()
    if secret == "CHANGE_ME_IN_PRODUCTION" or len(secret) < 32:
        raise RuntimeError("JWT_SECRET seguro e obrigatorio em producao.")
    if not settings.owner_email.strip():
        raise RuntimeError("OWNER_EMAIL e obrigatorio em producao.")
