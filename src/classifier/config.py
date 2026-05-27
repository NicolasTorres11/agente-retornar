"""Environment-backed classifier configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_api_version: str = "2024-08-01-preview"
    azure_openai_deployment_name: str = "gpt-4o"

    classifier_temperature: float = 0.1
    classifier_max_tokens: int = 300
    classifier_timeout_seconds: int = 15
    classifier_offline_mode: bool = False
    log_level: str = "INFO"

    def require_azure_credentials(self) -> None:
        if not self.azure_openai_endpoint or not self.azure_openai_api_key:
            raise ValueError(
                "Configura AZURE_OPENAI_ENDPOINT y AZURE_OPENAI_API_KEY, "
                "o usa CLASSIFIER_OFFLINE_MODE=true."
            )
