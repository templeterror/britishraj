from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class HeirloomSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HEIRLOOM_", extra="ignore")

    mode: Literal["demo", "clerk"] = "demo"
    demo_secret: str = "dev-only-demo-secret"
    demo_token_ttl_s: int = 43200
    database_url: str = "sqlite:///./.data/heirloom.db"
    neo4j_uri: str | None = None
    neo4j_user: str = "neo4j"
    neo4j_password: str | None = None
    integration_token: str = "dev-integration-token"
    frontend_origin: str = "http://localhost:3000"
    clerk_domain: str | None = None
    review_threshold: float = 0.5


@lru_cache
def get_settings() -> HeirloomSettings:
    return HeirloomSettings()
