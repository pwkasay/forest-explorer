"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """App settings loaded from environment / .env file."""

    database_url: str = "postgresql+asyncpg://forest:forest_dev@localhost:5432/forest_explorer"
    database_url_sync: str = "postgresql://forest:forest_dev@localhost:5432/forest_explorer"
    fia_base_url: str = "https://apps.fs.usda.gov/fiadb-api"
    fia_datamart_url: str = "https://apps.fs.usda.gov/fia/datamart/CSV"

    # API
    api_title: str = "Forest Carbon Explorer"
    api_version: str = "0.1.0"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
    ]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
