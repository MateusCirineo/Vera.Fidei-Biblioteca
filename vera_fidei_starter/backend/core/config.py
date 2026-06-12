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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
