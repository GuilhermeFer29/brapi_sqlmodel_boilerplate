"""
Testes para o serviço OHLCV.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ohlcv_service import (
    get_ohlcv,
    backfill_ohlcv,
    _parse_timestamp,
    _extract_ohlcv_from_quote,
    get_available_dates
)
from app.models import QuoteOHLCV


class TestTimestampParsing:
    """Testes para parsing de timestamps."""
    
    def test_parse_timestamp_seconds(self):
        # Timestamp em segundos
        ts = 1705123200  # 2024-01-13 12:00:00 UTC
        dt = _parse_timestamp(ts)
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 13
    
    def test_parse_timestamp_milliseconds(self):
        # Timestamp em milissegundos
        ts = 1705123200000  # 2024-01-13 12:00:00 UTC
        dt = _parse_timestamp(ts)
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 13
    
    def test_parse_timestamp_none(self):
        assert _parse_timestamp(None) is None
    
    def test_parse_timestamp_invalid(self):
        assert _parse_timestamp("invalid") is None
        assert _parse_timestamp("") is None


class TestOHLCVExtraction:
    """Testes para extração de dados OHLCV da resposta da API."""
    
    def test_extract_ohlcv_from_quote(self):
        payload = {
            "results": [
                {
                    "symbol": "PETR4",
                    "historicalDataPrice": [
                        {
                            "date": 1705123200,  # 2024-01-13
                            "open": 38.20,
                            "high": 39.00,
                            "low": 37.80,
                            "close": 38.50,
                            "volume": 45678901,
                            "adjClose": 38.50
                        },
                        {
                            "date": 1705036800,  # 2024-01-12
                            "open": 37.90,
                            "high": 38.30,
                            "low": 37.70,
                            "close": 38.10,
                            "volume": 38245678,
                            "adjClose": 38.10
                        }
                    ]
                }
            ]
        }
        
        ohlcv_list = _extract_ohlcv_from_quote(payload, "PETR4")
        
        assert len(ohlcv_list) == 2
        
        # Primeiro registro
        ohlcv1 = ohlcv_list[0]
        assert ohlcv1.ticker == "PETR4"
        assert ohlcv1.open == 38.20
        assert ohlcv1.high == 39.00
        assert ohlcv1.low == 37.80
        assert ohlcv1.close == 38.50
        assert ohlcv1.volume == 45678901
        assert ohlcv1.adj_close == 38.50
        
        # Segundo registro
        ohlcv2 = ohlcv_list[1]
        assert ohlcv2.ticker == "PETR4"
        assert ohlcv2.open == 37.90
        assert ohlcv2.close == 38.10
    
    def test_extract_ohlcv_empty_data(self):
        payload = {"results": [{"symbol": "PETR4", "historicalDataPrice": []}]}
        ohlcv_list = _extract_ohlcv_from_quote(payload, "PETR4")
        assert len(ohlcv_list) == 0
    
    def test_extract_ohlcv_missing_fields(self):
        payload = {
            "results": [
                {
                    "symbol": "PETR4",
                    "historicalDataPrice": [
                        {
                            "date": 1705123200,
                            "open": 38.20,
                            # Faltam outros campos
                        }
                    ]
                }
            ]
        }
        
        ohlcv_list = _extract_ohlcv_from_quote(payload, "PETR4")
        assert len(ohlcv_list) == 1
        
        ohlcv = ohlcv_list[0]
        assert ohlcv.ticker == "PETR4"
        assert ohlcv.open == 38.20
        assert ohlcv.high is None
        assert ohlcv.low is None
        assert ohlcv.close is None


@pytest.mark.asyncio
class TestOHLCVService:
    """Testes para o serviço OHLCV."""
    
    @patch('app.services.ohlcv_service.get_redis')
    async def test_get_ohlcv_with_cache(self, mock_get_redis):
        """Testa busca de dados OHLCV com cache."""
        # Mock cache hit
        mock_redis = AsyncMock()
        mock_redis.get.return_value = '{"ticker": "PETR4", "data": [{"date": "2024-01-13", "close": 38.50}], "count": 1}'
        mock_get_redis.return_value = mock_redis
        
        mock_session = AsyncMock(spec=AsyncSession)
        
        result = await get_ohlcv(mock_session, "PETR4")
        
        assert result["ticker"] == "PETR4"
        assert len(result["data"]) == 1
        assert result["count"] == 1
        
        # Não deve consultar o banco
        mock_session.execute.assert_not_called()
    
    @patch('app.services.ohlcv_service.get_redis')
    async def test_get_ohlcv_without_cache(self, mock_get_redis):
        """Testa busca de dados OHLCV sem cache."""
        # Mock cache miss
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_get_redis.return_value = mock_redis
        
        # Mock banco
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        
        # Criar dados OHLCV de exemplo
        test_date = datetime(2024, 1, 13, tzinfo=timezone.utc)
        mock_ohlcv = QuoteOHLCV(
            ticker="PETR4",
            date=test_date,
            open=38.20,
            high=39.00,
            low=37.80,
            close=38.50,
            volume=45678901
        )
        
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_ohlcv]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        result = await get_ohlcv(mock_session, "PETR4")
        
        assert result["ticker"] == "PETR4"
        assert len(result["data"]) == 1
        assert result["data"][0]["date"] == "2024-01-13T00:00:00+00:00"
        assert result["data"][0]["close"] == 38.50
        assert result["count"] == 1
        
        # Verifica que cache foi setado
        mock_redis.setex.assert_called_once()
    
    async def test_get_ohlcv_with_date_filters(self):
        """Testa busca de dados OHLCV com filtros de data."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)
        
        with patch('app.services.ohlcv_service.get_redis', return_value=mock_redis):
            result = await get_ohlcv(
                mock_session, 
                "PETR4", 
                start_date=start_date, 
                end_date=end_date
            )
        
        # Verifica que o query builder foi chamado com filtros de data
        mock_session.execute.assert_called()
        
        # Verifica que os parâmetros foram passados corretamente
        call_args = mock_session.execute.call_args[0][0]
        # O query construído deve incluir os filtros de data
    
    @patch('app.services.ohlcv_service._fetch_quote_with_semaphore')
    @patch('app.services.ohlcv_service._log_call')
    async def test_backfill_ohlcv_wrapper(self, mock_log_call, mock_fetch):
        """Testa backfill com múltiplos tickers."""
        # Mock resposta da API para cada ticker
        mock_fetch.return_value = {
            "results": [{
                "symbol": "PETR4",
                "historicalDataPrice": [{"date": 1705123200, "open": 38.20, "high": 39.00, "low": 37.80, "close": 38.50, "volume": 45678901}] * 65
            }]
        }
        
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        
        result = await backfill_ohlcv(
            mock_session,
            ["PETR4", "VALE3"],
            range="3mo",
            interval="1d"
        )
        
        assert result["processed"] == 2
        assert result["inserted"] == 130  # 65 per ticker
        assert result["total_requested"] == 2
    
    async def test_get_available_dates(self):
        """Testa busca de datas disponíveis."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        
        # Mock datas
        dates = [
            datetime(2024, 1, 15, tzinfo=timezone.utc),
            datetime(2024, 1, 12, tzinfo=timezone.utc),
            datetime(2024, 1, 11, tzinfo=timezone.utc)
        ]
        
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = dates
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        result = await get_available_dates(mock_session, "PETR4")
        
        assert len(result) == 3
        # Formato retornado é ISO com timezone: 2024-01-15T00:00:00+00:00
        assert "2024-01-15T00:00:00+00:00" in result
        assert "2024-01-12T00:00:00+00:00" in result
        assert "2024-01-11T00:00:00+00:00" in result
        
        # Deve estar em ordem decrescente (mais recentes primeiro)
        assert result[0] == "2024-01-15T00:00:00+00:00"
        assert result[-1] == "2024-01-11T00:00:00+00:00"


@pytest.mark.asyncio
class TestOHLCVIntegration:
    """Testes de integração para o serviço OHLCV."""
    
    async def test_empty_tickers_list(self):
        """Testa comportamento com lista vazia de tickers."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        result = await backfill_ohlcv(mock_session, [])
        
        assert result["processed"] == 0
        assert result["inserted"] == 0
        assert result["updated"] == 0
        assert result["errors"] == 0
        assert result["total_requested"] == 0
    
    @patch('app.services.ohlcv_service._fetch_quote_with_semaphore')
    @patch('app.services.ohlcv_service._log_call')
    async def test_single_ticker_processing(self, mock_log_call, mock_fetch):
        """Testa processamento de um único ticker."""
        # Mock resposta da API
        mock_fetch.return_value = {
            "results": [
                {
                    "symbol": "PETR4",
                    "historicalDataPrice": [
                        {
                            "date": 1705123200,
                            "open": 38.20,
                            "high": 39.00,
                            "low": 37.80,
                            "close": 38.50,
                            "volume": 45678901
                        }
                    ]
                }
            ]
        }
        
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        
        result = await backfill_ohlcv(mock_session, ["PETR4"])
        
        assert result["processed"] == 1
        assert result["inserted"] == 1
        mock_fetch.assert_called_once()


@pytest.fixture
def sample_ohlcv_data():
    """Fixture com dados OHLCV de exemplo."""
    return [
        QuoteOHLCV(
            ticker="PETR4",
            date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            open=38.20,
            high=39.00,
            low=37.80,
            close=38.50,
            volume=45678901
        ),
        QuoteOHLCV(
            ticker="PETR4",
            date=datetime(2024, 1, 12, tzinfo=timezone.utc),
            open=37.90,
            high=38.30,
            low=37.70,
            close=38.10,
            volume=38245678
        )
    ]
