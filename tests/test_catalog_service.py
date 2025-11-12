"""
Testes para o serviço de catálogo de ativos.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.catalog_service import (
    sync_assets, 
    list_assets, 
    get_asset_by_ticker,
    _normalize_asset_type,
    _extract_assets_from_list
)
from app.models import Asset


class TestAssetTypeNormalization:
    """Testes para normalização de tipos de ativos."""
    
    def test_normalize_stock_types(self):
        assert _normalize_asset_type("stock") == "stock"
        assert _normalize_asset_type("acao") == "stock"
        assert _normalize_asset_type("ações") == "stock"
        assert _normalize_asset_type("AÇÕES") == "stock"
    
    def test_normalize_fund_types(self):
        assert _normalize_asset_type("fund") == "fund"
        assert _normalize_asset_type("fii") == "fund"
        assert _normalize_asset_type("fundos") == "fund"
    
    def test_normalize_other_types(self):
        assert _normalize_asset_type("bdr") == "bdr"
        assert _normalize_asset_type("etf") == "etf"
        assert _normalize_asset_type("index") == "index"
        assert _normalize_asset_type("índice") == "index"
    
    def test_normalize_empty_none(self):
        assert _normalize_asset_type("") is None
        assert _normalize_asset_type(None) is None
        assert _normalize_asset_type("   ") is None
    
    def test_normalize_unknown_types(self):
        assert _normalize_asset_type("unknown") == "unknown"
        assert _normalize_asset_type("custom") == "custom"


class TestAssetExtraction:
    """Testes para extração de ativos da resposta da API."""
    
    def test_extract_assets_from_response(self):
        payload = {
            "stocks": [
                {
                    "symbol": "PETR4",
                    "name": "PETROBRAS PN",
                    "type": "stock",
                    "sector": "Petróleo",
                    "isin": "BRPETRACNOR11",
                    "logourl": "https://example.com/petr4.png"
                },
                {
                    "symbol": "VALE3",
                    "name": "VALE ON",
                    "type": "stock",
                    "sector": "Mineração"
                }
            ]
        }
        
        assets = _extract_assets_from_list(payload)
        
        assert len(assets) == 2
        assert assets[0].ticker == "PETR4"
        assert assets[0].name == "PETROBRAS PN"
        assert assets[0].type == "stock"
        assert assets[0].sector == "Petróleo"
        assert assets[0].isin == "BRPETRACNOR11"
        assert assets[0].logo_url == "https://example.com/petr4.png"
        
        assert assets[1].ticker == "VALE3"
        assert assets[1].name == "VALE ON"
        assert assets[1].type == "stock"
        assert assets[1].sector == "Mineração"
    
    def test_extract_empty_response(self):
        payload = {"stocks": []}
        assets = _extract_assets_from_list(payload)
        assert len(assets) == 0
    
    def test_extract_missing_fields(self):
        payload = {
            "stocks": [
                {"symbol": "TEST4"},  # Mínimo necessário
                {"name": "Sem símbolo"}  # Sem ticker - deve ser ignorado
            ]
        }
        
        assets = _extract_assets_from_list(payload)
        assert len(assets) == 1
        assert assets[0].ticker == "TEST4"
        assert assets[0].name is None


@pytest.mark.asyncio
class TestCatalogService:
    """Testes para o serviço de catálogo."""
    
    async def test_get_asset_by_ticker_found(self):
        """Testa busca de ativo existente."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = Asset(
            ticker="PETR4",
            name="PETROBRAS PN",
            type="stock"
        )
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        asset = await get_asset_by_ticker(mock_session, "PETR4")
        
        assert asset is not None
        assert asset.ticker == "PETR4"
        assert asset.name == "PETROBRAS PN"
        assert asset.type == "stock"
    
    async def test_get_asset_by_ticker_not_found(self):
        """Testa busca de ativo inexistente."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        asset = await get_asset_by_ticker(mock_session, "NOTFOUND")
        
        assert asset is None
    
    async def test_get_asset_by_ticker_normalization(self):
        """Testa normalização do ticker."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = Asset(ticker="PETR4")
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        # Testa várias formas do mesmo ticker
        for ticker_input in ["petr4", "PETR4", "  petr4  ", "petr4\n"]:
            asset = await get_asset_by_ticker(mock_session, ticker_input)
            assert asset is not None
            assert asset.ticker == "PETR4"
    
    @patch('app.services.catalog_service.get_redis')
    async def test_list_assets_with_cache(self, mock_get_redis):
        """Testa listagem de ativos com cache."""
        # Mock cache
        mock_redis = AsyncMock()
        mock_redis.get.return_value = '{"assets": [{"ticker": "PETR4"}], "pagination": {"page": 1}}'
        mock_get_redis.return_value = mock_redis
        
        mock_session = AsyncMock(spec=AsyncSession)
        
        result = await list_assets(mock_session)
        
        assert "assets" in result
        assert len(result["assets"]) == 1
        assert result["assets"][0]["ticker"] == "PETR4"
        
        # Verifica que não consultou o banco (cache hit)
        mock_session.execute.assert_not_called()
    
    @patch('json.dumps')  # Patchear json.dumps globalmente
    @patch('app.services.catalog_service.get_redis')
    async def test_list_assets_without_cache(self, mock_get_redis, mock_json_dumps):
        """Testa listagem de ativos sem cache (cache miss)."""
        # Mock json.dumps para retornar string sem tentar serializar
        mock_json_dumps.return_value = '{"test": "data"}'
        
        # Mock cache miss
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock(return_value=None)
        mock_get_redis.return_value = mock_redis
        
        # Mock banco
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Mock result para select de assets
        mock_assets_result = MagicMock()
        mock_scalars = MagicMock()
        
        # Criar asset com todos os campos explícitos
        test_asset = Asset(
            ticker="PETR4",
            name="PETROBRAS PN",
            type="stock",
            sector="Petróleo",
            segment=None,
            isin=None,
            logo_url=None,
            raw=None,
            updated_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            created_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            id=None
        )
        
        mock_scalars.all.return_value = [test_asset]
        mock_assets_result.scalars.return_value = mock_scalars
        
        # Mock result para count
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1
        
        # session.execute retorna diferentes resultados em cada chamada
        # ORDEM: primeiro count (linha 333), depois assets (linha 351)
        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_assets_result])
        
        result = await list_assets(mock_session)
        
        assert "assets" in result
        assert "pagination" in result
        assert len(result["assets"]) == 1
        assert result["assets"][0]["ticker"] == "PETR4"
        
        # Verifica que cache foi setado
        mock_redis.setex.assert_called_once()
    
    @patch('app.services.catalog_service.BrapiClient')
    @patch('app.services.catalog_service._log_call')
    async def test_sync_assets_success(self, mock_log_call, mock_brapi_client):
        """Testa sincronização de ativos com sucesso."""
        # Mock BrapiClient
        mock_client = AsyncMock()
        mock_client.available = AsyncMock(return_value={
            "stocks": [
                {
                    "symbol": "TEST4",
                    "name": "TEST STOCK",
                    "type": "stock",
                    "sector": "Test"
                }
            ],
            "pagination": {"hasMore": False, "totalItems": 1}
        })
        mock_client.quote = AsyncMock(return_value={"results": []})
        mock_brapi_client.return_value = mock_client
        
        # Mock session
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        
        stats = await sync_assets(mock_session, "stock", 100)
        
        assert stats["processed"] == 1
        assert stats["inserted"] == 1
        assert stats["errors"] == 0
        assert stats["pages"] == 1
        
        # Verifica que chamou API
        mock_client.available.assert_called_once()
        
        # Verifica que logou a chamada
        mock_log_call.assert_called()


@pytest.fixture
def sample_assets():
    """Fixture com ativos de exemplo para testes."""
    return [
        Asset(
            ticker="PETR4",
            name="PETROBRAS PN",
            type="stock",
            sector="Petróleo",
            updated_at=datetime.now(timezone.utc)
        ),
        Asset(
            ticker="HGLG11",
            name="CSHG LOGISTICA",
            type="fund",
            sector="Fundos Imobiliários",
            updated_at=datetime.now(timezone.utc)
        )
    ]
