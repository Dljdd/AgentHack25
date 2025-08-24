from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = Field(default="sqlite:///./app.db")

    # Redis (optional for Celery/background)
    REDIS_URL: Optional[str] = None

    # Stripe
    STRIPE_API_KEY: Optional[str] = None

    # JWT/Secrets
    JWT_SECRET: str = Field(default="dev-secret")
    JWT_ALG: str = Field(default="HS256")

    # LLM API keys
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None

    # App
    ENV: str = Field(default="dev")
    CORS_ORIGINS: str = Field(default="*")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()  # loads from environment and .env
