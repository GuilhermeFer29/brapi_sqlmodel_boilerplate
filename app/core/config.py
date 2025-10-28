from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    env: str = Field(default="dev", alias="ENV")
    brapi_base_url: str = Field(default="https://brapi.dev", alias="BRAPI_BASE_URL")
    brapi_token: str | None = Field(default=None, alias="BRAPI_TOKEN")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    database_url: str = Field(default="mysql+asyncmy://user:pass@localhost:3306/db", alias="DATABASE_URL")
    cache_ttl_quote_seconds: int = Field(default=1800, alias="CACHE_TTL_QUOTE_SECONDS")
    cache_ttl_crypto_seconds: int = Field(default=3600, alias="CACHE_TTL_CRYPTO_SECONDS")
    cache_ttl_currency_seconds: int = Field(default=3600, alias="CACHE_TTL_CURRENCY_SECONDS")
    cache_ttl_macro_seconds: int = Field(default=86400, alias="CACHE_TTL_MACRO_SECONDS")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
