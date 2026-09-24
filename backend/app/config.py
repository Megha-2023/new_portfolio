from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_secret_key: str = ""
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_refresh_token: str = ""
    gmail_sender_email: str = ""
    contact_notification_to: str = ""
    rate_limit_salt: str = ""
    allowed_origins: str = ""
    trust_proxy_headers: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.allowed_origins.split(",") if origin.strip()]

    def missing_required_values(self) -> list[str]:
        values = {
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_SECRET_KEY": self.supabase_secret_key,
            "GMAIL_CLIENT_ID": self.gmail_client_id,
            "GMAIL_CLIENT_SECRET": self.gmail_client_secret,
            "GMAIL_REFRESH_TOKEN": self.gmail_refresh_token,
            "GMAIL_SENDER_EMAIL": self.gmail_sender_email,
            "CONTACT_NOTIFICATION_TO": self.contact_notification_to,
            "RATE_LIMIT_SALT": self.rate_limit_salt,
            "ALLOWED_ORIGINS": self.allowed_origins,
        }
        return [name for name, value in values.items() if not value.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
