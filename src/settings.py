"""Application configuration for local execution and WhatsApp adapters."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local", "production"] = "local"
    db_path: Path = Path("./data/retornar_agent.db")
    field_encryption_key: str

    whatsapp_send_mode: Literal["console", "meta"] = "console"
    whatsapp_verify_token: str = "retornar-local-token"
    whatsapp_app_secret: str = "retornar-local-secret"
    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_api_version: str = "v21.0"

    def require_meta_send_config(self) -> None:
        if not self.whatsapp_access_token or not self.whatsapp_phone_number_id:
            raise ValueError(
                "WHATSAPP_ACCESS_TOKEN y WHATSAPP_PHONE_NUMBER_ID son requeridos "
                "cuando WHATSAPP_SEND_MODE=meta."
            )
