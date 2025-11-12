from typing import Any, List, Optional, Dict
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, update, and_, func
from sqlalchemy import desc
from app.core.cache import get_redis
from app.core.config import settings
from app.services.brapi_client import BrapiClient
from brapi import NotFoundError
from app.services.utils.key import make_cache_key
from app.services.utils.json_serializer import json_serializer, normalize_for_json
from app.models import ApiCall, Asset, QuoteOHLCV
from datetime import datetime, timezone, timedelta
import json
import asyncio
import random

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def _parse_timestamp(ts: Any) -> Optional[datetime]:
    """Converte timestamp Unix para datetime UTC."""
    if ts is None:
        return None
    try:
        # brapi usa timestamp em segundos ou milissegundos
        ts_int = int(ts)
        if ts_int > 1e12:  # Milissegundos
            return datetime.fromtimestamp(ts_int / 1000, tz=timezone.utc)
        else:  # Segundos
            return datetime.fromtimestamp(ts_int, tz=timezone.utc)
    except (ValueError, TypeError):
        return None

def _extract_ohlcv_from_quote(payload: dict, ticker: str) -> List[QuoteOHLCV]:
    """Extrai dados OHLCV da resposta da API quote."""
    results = payload.get("results") or payload.get("stocks") or []
    ohlcv_list = []
    
    for item in results:
        historical_data = item.get("historicalDataPrice") or []
        
        for data_point in historical_data:
            date = _parse_timestamp(data_point.get("date"))
            if not date:
                continue
                
            ohlcv = QuoteOHLCV(
                ticker=ticker.upper().strip(),
                date=date,
                open=data_point.get("open"),
                high=data_point.get("high"),
                low=data_point.get("low"),
                close=data_point.get("close"),
                volume=data_point.get("volume"),
                adj_close=data_point.get("adjClose"),
                raw=normalize_for_json(data_point)
            )
            ohlcv_list.append(ohlcv)
    
    return ohlcv_list

async def _log_call(session: AsyncSession, *, endpoint: str, tickers: str, params: dict | None, cached: bool, status_code: int, response: dict | None = None, error: str | None = None, count: int = 0):
    """Registra chamada da API para observabilidade."""
    rec = ApiCall(
        endpoint=endpoint, 
        tickers=tickers, 
        params=normalize_for_json(params) if params else None, 
        cached=cached, 
        status_code=status_code, 
        error=error, 
        response=normalize_for_json(response) if response else None
    )
    session.add(rec)
    await session.commit()

async def _fetch_quote_with_semaphore(client: BrapiClient, ticker: str, range: str = "3mo", interval: str = "1d", semaphore: asyncio.Semaphore = None) -> Dict[str, Any]:
    """
    Busca cotação com controle de semáforo para respeitar rate limiting.
    
    Args:
        client: Cliente brapi
        ticker: Símbolo do ativo
        range: Período histórico
        interval: Intervalo dos dados
        semaphore: Semáforo para controle de concorrência
        
    Returns:
        Response da API
    """
    if semaphore:
        async with semaphore:
            return await _fetch_quote_single(client, ticker, range, interval)
    else:
        return await _fetch_quote_single(client, ticker, range, interval)

async def _fetch_quote_single(client: BrapiClient, ticker: str, range_period: str, interval: str) -> Dict[str, Any]:
    """
    Busca cotação individual com retry e jitter.
    """
    params = {
        "range": range_period,
        "interval": interval
    }
    
    max_retries = 3
    base_delay = 1.0
    
    for attempt in range(max_retries):
        try:
            # Chamar API para um ticker apenas (plano free)
            result = await client.quote([ticker], params)
            
            # Jitter entre chamadas para não martelar
            jitter = 0.2 + random.random() * 0.4
            await asyncio.sleep(jitter)
            
            return result
            
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            
            # Backoff exponencial com jitter
            delay = base_delay * (2 ** attempt) + random.random()
            await asyncio.sleep(delay)

async def backfill_ohlcv(session: AsyncSession, tickers: List[str], range: str = "3mo", interval: str = "1d", max_concurrency: int = 3) -> Dict[str, Any]:
    """
    Preenche dados históricos OHLCV para lista de tickers.
    Respeita limites do plano free (1 ticker por requisição).
    
    Args:
        session: Sessão do banco
        tickers: Lista de símbolos
        range: Período histórico (1mo, 3mo, 6mo, 1y, etc)
        interval: Intervalo (1d, 1wk, 1mo)
        max_concurrency: Máximo de requisições simultâneas
        
    Returns:
        Estatísticas da operação
    """
    stats = {
        "processed": 0,
        "inserted": 0,
        "updated": 0,
        "errors": 0,
        "total_requested": len(tickers)
    }
    
    if not tickers:
        return stats
    
    client = BrapiClient()
    semaphore = asyncio.Semaphore(max_concurrency)
    
    # Processar tickers de forma sequencial para evitar conflitos de sessão
    for ticker in tickers:
        await _process_ticker_ohlcv(session, client, ticker, range, interval, semaphore, stats)
    
    return stats

async def _process_ticker_ohlcv(session: AsyncSession, client: BrapiClient, ticker: str, range: str, interval: str, semaphore: asyncio.Semaphore, stats: Dict[str, Any]) -> None:
    """
    Processa um ticker individual para backfill OHLCV.
    """
    try:
        # Buscar dados da API
        response = await _fetch_quote_with_semaphore(client, ticker, range, interval)
        
        await _log_call(
            session,
            endpoint="quote_backfill",
            tickers=ticker,
            params={"range": range, "interval": interval},
            cached=False,
            status_code=200,
            response=response,
            count=1
        )
        
        # Extrair dados OHLCV
        ohlcv_list = _extract_ohlcv_from_quote(response, ticker)
        
        if not ohlcv_list:
            stats["processed"] += 1
            return
        
        # Upsert para cada data
        for ohlcv in ohlcv_list:
            try:
                # Verificar se já existe
                existing = await session.execute(
                    select(QuoteOHLCV).where(
                        and_(
                            QuoteOHLCV.ticker == ohlcv.ticker,
                            QuoteOHLCV.date == ohlcv.date
                        )
                    )
                )
                existing_ohlcv = existing.scalar_one_or_none()
                
                if existing_ohlcv:
                    # Update
                    existing_ohlcv.open = ohlcv.open
                    existing_ohlcv.high = ohlcv.high
                    existing_ohlcv.low = ohlcv.low
                    existing_ohlcv.close = ohlcv.close
                    existing_ohlcv.volume = ohlcv.volume
                    existing_ohlcv.adj_close = ohlcv.adj_close
                    existing_ohlcv.raw = ohlcv.raw
                    stats["updated"] += 1
                else:
                    # Insert
                    session.add(ohlcv)
                    stats["inserted"] += 1
                
            except Exception as e:
                stats["errors"] += 1
                print(f"Error upserting OHLCV for {ticker} {ohlcv.date}: {e}")
        
        await session.commit()
        stats["processed"] += 1
        
    except NotFoundError as e:
        stats["processed"] += 1
        error_text = str(e)
        await _log_call(
            session,
            endpoint="quote_backfill",
            tickers=ticker,
            params={"range": range, "interval": interval},
            cached=False,
            status_code=404,
            error=error_text,
        )
        print(f"Ticker {ticker} não disponível no plano atual (404). Ignorando.")
        return
    except Exception as e:
        status_code = getattr(getattr(e, "response", None), "status_code", None)
        error_text = str(e)
        if status_code == 404 or "404" in error_text:
            stats["processed"] += 1
            await _log_call(
                session,
                endpoint="quote_backfill",
                tickers=ticker,
                params={"range": range, "interval": interval},
                cached=False,
                status_code=404,
                error=error_text,
            )
            print(f"Ticker {ticker} não disponível no plano atual (404). Ignorando.")
            return
        stats["errors"] += 1
        await _log_call(
            session,
            endpoint="quote_backfill",
            tickers=ticker,
            params={"range": range, "interval": interval},
            cached=False,
            status_code=status_code or 500,
            error=error_text
        )
        print(f"Error processing ticker {ticker}: {error_text}")

async def update_ohlcv_latest(session: AsyncSession, tickers: List[str], max_concurrency: int = 3) -> Dict[str, Any]:
    """
    Atualiza dados mais recentes para tickers existentes.
    Busca apenas últimos dias para atualização incremental.
    
    Args:
        session: Sessão do banco
        tickers: Lista de símbolos para atualizar
        max_concurrency: Máximo de requisições simultâneas
        
    Returns:
        Estatísticas da operação
    """
    stats = {
        "processed": 0,
        "inserted": 0,
        "updated": 0,
        "errors": 0,
        "total_requested": len(tickers)
    }
    
    if not tickers:
        return stats
    
    # Para atualização, usar range curto (5d) e interval 1d
    return await backfill_ohlcv(session, tickers, range="5d", interval="1d", max_concurrency=max_concurrency)

async def get_ohlcv(
    session: AsyncSession,
    ticker: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Busca dados OHLCV do banco local.
    
    Args:
        session: Sessão do banco
        ticker: Símbolo do ativo
        start_date: Data inicial (opcional)
        end_date: Data final (opcional)
        limit: Limite de registros (opcional)
        
    Returns:
        Dados OHLCV serializados
    """
    # Cache muito curto para dados OHLCV (30s)
    r = await get_redis()
    cache_key = make_cache_key("ohlcv_v1", ticker, start_date, end_date, limit)
    
    cached = await r.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Construir query
    query = select(QuoteOHLCV).where(QuoteOHLCV.ticker == ticker.upper().strip())
    
    # Aplicar filtros de data
    if start_date:
        query = query.where(QuoteOHLCV.date >= start_date)
    if end_date:
        query = query.where(QuoteOHLCV.date <= end_date)
    
    # Ordenação e limite
    query = query.order_by(desc(QuoteOHLCV.date))
    if limit:
        query = query.limit(limit)
    
    # Executar
    result = await session.execute(query)
    ohlcv_records = result.scalars().all()
    
    # Serializar resposta
    response = {
        "ticker": ticker.upper(),
        "data": [
            {
                "date": record.date.isoformat() if record.date else None,
                "open": record.open,
                "high": record.high,
                "low": record.low,
                "close": record.close,
                "volume": record.volume,
                "adj_close": record.adj_close
            }
            for record in reversed(ohlcv_records)  # Ordem cronológica
        ],
        "count": len(ohlcv_records)
    }
    
    # Cache por 30 segundos
    await r.setex(cache_key, 30, json.dumps(response, default=json_serializer))
    
    return response

async def get_available_dates(session: AsyncSession, ticker: str) -> List[str]:
    """
    Retorna datas disponíveis para um ticker.
    
    Args:
        session: Sessão do banco
        ticker: Símbolo do ativo
        
    Returns:
        Lista de datas ISO
    """
    query = (
        select(QuoteOHLCV.date)
        .where(QuoteOHLCV.ticker == ticker.upper().strip())
        .order_by(desc(QuoteOHLCV.date))
    )
    
    result = await session.execute(query)
    dates = result.scalars().all()
    
    return [date.isoformat() for date in dates]
