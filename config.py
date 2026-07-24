import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # LINE Messaging API Configuration
    LINE_CHANNEL_ACCESS_TOKEN: str = "default_access_token"
    LINE_CHANNEL_SECRET: str = "default_channel_secret"

    # Gemini API Configuration
    GEMINI_API_KEY: str = "default_gemini_key"

    # Database Configuration (Defaults to local sqlite for ease of local testing)
    DATABASE_URL: str = "sqlite:///./ajisai.db"

    # Scheduler Security Token (To authenticate Cloud Scheduler calls)
    SCHEDULER_API_KEY: str = "change_me_in_production"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
