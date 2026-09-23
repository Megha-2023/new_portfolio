from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_secret_key: str = ""
    gmail_sender_email: str = ""
    gmail_app_password: str = ""
    contact_recipient_email: str = ""
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
            "GMAIL_SENDER_EMAIL": self.gmail_sender_email,
            "GMAIL_APP_PASSWORD": self.gmail_app_password,
            "CONTACT_RECIPIENT_EMAIL": self.contact_recipient_email,
            "RATE_LIMIT_SALT": self.rate_limit_salt,
            "ALLOWED_ORIGINS": self.allowed_origins,
        }
        return [name for name, value in values.items() if not value.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
