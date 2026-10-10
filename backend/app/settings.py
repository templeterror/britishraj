"""Environment contract for the FastAPI app.

Names here match backend/.env.example. User requests should forward the
caller's Clerk session token to Supabase so row level security applies.
SUPABASE_SECRET_KEY bypasses those policies and is for server-only work.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_origin: str = "http://localhost:3000"

    clerk_publishable_key: str
    clerk_secret_key: str
    clerk_domain: str = Field(description="Clerk Frontend API domain, no scheme.")

    supabase_url: str
    supabase_publishable_key: str
    supabase_secret_key: str

    @field_validator("clerk_domain")
    @classmethod
    def strip_clerk_domain(cls, value: str) -> str:
        domain = value.strip().removeprefix("https://").removeprefix("http://").strip("/")
        if not domain or "REPLACE_ME" in domain:
            raise ValueError("CLERK_DOMAIN is not set")
        return domain

    @field_validator("clerk_publishable_key", "clerk_secret_key")
    @classmethod
    def development_clerk_keys(cls, value: str, info) -> str:
        if value.startswith(("pk_live_", "sk_live_")):
            raise ValueError(f"{info.field_name} is a production Clerk key")
        return value

    @property
    def clerk_issuer(self) -> str:
        return f"https://{self.clerk_domain}"

    @property
    def clerk_jwks_url(self) -> str:
        return f"{self.clerk_issuer}/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
