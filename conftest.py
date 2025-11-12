"""
Configuração global para testes pytest.
"""
import pytest
import asyncio
from app.core.http import close_async_client
from app.core.limits import _DEFAULT_LIMITS


@pytest.fixture(scope="function", autouse=True)
async def cleanup_resources():
    """Limpa recursos compartilhados entre testes."""
    yield
    # Limpar HTTP client global
    await close_async_client()
    # Limpar limiters globais
    _DEFAULT_LIMITS.clear()
