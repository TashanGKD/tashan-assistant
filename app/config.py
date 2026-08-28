from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "他山助手"
    app_version: str = "1.0.0"
    course_version: str = "2026-fall-v1"

    llm_api_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_app_token: str = ""
    feishu_case_table_id: str = ""
    feishu_report_table_id: str = ""
    feishu_store_transcript: bool = False

    admin_token: str = "change-me-before-production"
    allowed_origins: str = ""

    local_store_path: str = str(BASE_DIR / "data" / "cases.jsonl")

settings = Settings()
