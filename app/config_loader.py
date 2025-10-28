"""
Módulo para carregar configurações de arquivos TOML e .env

Suporta tanto TOML quanto .env para flexibilidade.
Prioridade: TOML > .env > valores padrão
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import tomli  # Python < 3.11
except ImportError:
    try:
        import tomllib as tomli  # Python >= 3.11
    except ImportError:
        tomli = None  # type: ignore

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class BrapiConfig(BaseModel):
    """Configurações da API brapi"""
    mcp_url: str = Field(default="https://brapi.dev/api/mcp/mcp")
    base_url: str = Field(default="https://brapi.dev")
    api_key: str = Field(default="")
    token: str = Field(default="")


class CacheConfig(BaseModel):
    """Configurações de cache"""
    quote_ttl_seconds: int = Field(default=1800)
    crypto_ttl_seconds: int = Field(default=3600)
    currency_ttl_seconds: int = Field(default=3600)
    macro_ttl_seconds: int = Field(default=86400)


class DatabaseConfig(BaseModel):
    """Configurações de banco de dados"""
    redis_url: str = Field(default="redis://redis:6379/0")
    mysql_url: str = Field(default="mysql+asyncmy://brapi_user:brapi_pass@mysql:3306/brapi_db")


class LLMConfig(BaseModel):
    """Configurações do LLM"""
    gemini_api_key: str = Field(default="")


class BackendConfig(BaseModel):
    """Configurações do backend"""
    base_url: str = Field(default="http://localhost:8000")


class AppConfig(BaseSettings):
    """Configuração principal da aplicação"""
    
    environment: str = Field(default="dev", alias="env")
    brapi: BrapiConfig = Field(default_factory=BrapiConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    backend: BackendConfig = Field(default_factory=BackendConfig)

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"


def load_config_from_toml(config_path: str | Path = "config.toml") -> dict[str, Any] | None:
    """
    Carrega configurações de um arquivo TOML
    
    Args:
        config_path: Caminho para o arquivo TOML
        
    Returns:
        Dicionário com as configurações ou None se não encontrar
    """
    if tomli is None:
        print("⚠️  Módulo tomli/tomllib não encontrado. Instale com: pip install tomli")
        return None
    
    config_file = Path(config_path)
    if not config_file.exists():
        return None
    
    try:
        with open(config_file, "rb") as f:
            return tomli.load(f)
    except Exception as e:
        print(f"❌ Erro ao carregar {config_path}: {e}")
        return None


def load_config() -> AppConfig:
    """
    Carrega configurações com prioridade: Streamlit Secrets > TOML > .env
    
    Returns:
        AppConfig com as configurações carregadas
    """
    # Tentar carregar do Streamlit Secrets primeiro (para deploy no Streamlit Cloud)
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and st.secrets:
            config_dict = {
                "environment": st.secrets.get("environment", {}).get("env", "production"),
                "brapi": dict(st.secrets.get("brapi", {})),
                "cache": dict(st.secrets.get("cache", {})),
                "database": dict(st.secrets.get("database", {})),
                "llm": dict(st.secrets.get("llm", {})),
                "backend": dict(st.secrets.get("backend", {})),
            }
            
            config = AppConfig(
                environment=config_dict["environment"],
                brapi=BrapiConfig(**config_dict["brapi"]),
                cache=CacheConfig(**config_dict["cache"]),
                database=DatabaseConfig(**config_dict["database"]),
                llm=LLMConfig(**config_dict["llm"]),
                backend=BackendConfig(**config_dict["backend"]),
            )
            print("✅ Configurações carregadas de Streamlit Secrets")
            return config
    except (ImportError, AttributeError, FileNotFoundError):
        pass  # Streamlit não está disponível ou secrets não configurados
    
    # Tentar carregar do TOML
    toml_config = load_config_from_toml()
    
    if toml_config:
        # Mapear estrutura do TOML para o formato esperado pelo Pydantic
        config_dict = {
            "environment": toml_config.get("environment", {}).get("env", "dev"),
            "brapi": toml_config.get("brapi", {}),
            "cache": toml_config.get("cache", {}),
            "database": toml_config.get("database", {}),
            "llm": toml_config.get("llm", {}),
            "backend": toml_config.get("backend", {}),
        }
        
        # Criar instâncias dos modelos
        try:
            config = AppConfig(
                environment=config_dict["environment"],
                brapi=BrapiConfig(**config_dict["brapi"]),
                cache=CacheConfig(**config_dict["cache"]),
                database=DatabaseConfig(**config_dict["database"]),
                llm=LLMConfig(**config_dict["llm"]),
                backend=BackendConfig(**config_dict["backend"]),
            )
            print("✅ Configurações carregadas de config.toml")
            return config
        except Exception as e:
            print(f"⚠️  Erro ao processar config.toml: {e}")
            print("   Carregando de .env como fallback...")
    
    # Fallback para .env
    try:
        config = AppConfig(
            brapi=BrapiConfig(
                mcp_url=os.getenv("BRAPI_MCP_URL", "https://brapi.dev/api/mcp/mcp"),
                base_url=os.getenv("BRAPI_BASE_URL", "https://brapi.dev"),
                api_key=os.getenv("BRAPI_API_KEY", ""),
                token=os.getenv("BRAPI_TOKEN", ""),
            ),
            cache=CacheConfig(
                quote_ttl_seconds=int(os.getenv("CACHE_TTL_QUOTE_SECONDS", "1800")),
                crypto_ttl_seconds=int(os.getenv("CACHE_TTL_CRYPTO_SECONDS", "3600")),
                currency_ttl_seconds=int(os.getenv("CACHE_TTL_CURRENCY_SECONDS", "3600")),
                macro_ttl_seconds=int(os.getenv("CACHE_TTL_MACRO_SECONDS", "86400")),
            ),
            database=DatabaseConfig(
                redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
                mysql_url=os.getenv("DATABASE_URL", "mysql+asyncmy://brapi_user:brapi_pass@mysql:3306/brapi_db"),
            ),
            llm=LLMConfig(
                gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            ),
            backend=BackendConfig(
                base_url=os.getenv("BACKEND_BASE_URL", "http://localhost:8000"),
            ),
        )
        print("✅ Configurações carregadas de .env")
        return config
    except Exception as e:
        print(f"⚠️  Erro ao carregar .env: {e}")
        print("   Usando valores padrão...")
        return AppConfig()


# Instância global de configuração
config = load_config()


if __name__ == "__main__":
    """Teste do módulo de configuração"""
    print("\n📋 Configurações Carregadas:")
    print(f"\n🌍 Ambiente: {config.environment}")
    print(f"\n🔧 brapi:")
    print(f"  - MCP URL: {config.brapi.mcp_url}")
    print(f"  - Base URL: {config.brapi.base_url}")
    print(f"  - API Key: {'***' + config.brapi.api_key[-4:] if config.brapi.api_key else 'Não configurado'}")
    print(f"\n💾 Cache:")
    print(f"  - Quote TTL: {config.cache.quote_ttl_seconds}s")
    print(f"  - Crypto TTL: {config.cache.crypto_ttl_seconds}s")
    print(f"\n🗄️  Database:")
    print(f"  - Redis: {config.database.redis_url}")
    print(f"  - MySQL: {config.database.mysql_url}")
    print(f"\n🤖 LLM:")
    print(f"  - Gemini API Key: {'***' + config.llm.gemini_api_key[-4:] if config.llm.gemini_api_key else 'Não configurado'}")
    print(f"\n🚀 Backend:")
    print(f"  - Base URL: {config.backend.base_url}")
