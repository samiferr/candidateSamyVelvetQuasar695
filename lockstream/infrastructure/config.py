from pathlib import Path

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite+pysqlite:///:memory:"
    event_log_path : Path = Path(__file__).resolve().parents[1] / "event_log.jsonl"
    openapi_path : Path = Path(__file__).resolve().parents[1] / "openapi/openapi.yaml"


settings = Settings()