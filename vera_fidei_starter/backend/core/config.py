from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Vera.fidei"
    database_url: str = "postgresql://vera:vera123@localhost:5432/vera_fidei"
    elasticsearch_url: str = "http://localhost:9200"
    chroma_path: str = "./chroma_db"
    embedding_model: str = "BAAI/bge-m3"
    llm_enabled: bool = False
    llm_model_name: str = "qwen"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
