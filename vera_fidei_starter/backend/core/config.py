from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Vera.fidei"
    database_url: str = "sqlite:///./vera_fidei.db"
    llm_enabled: bool = False
    llm_model_name: str = "qwen"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
