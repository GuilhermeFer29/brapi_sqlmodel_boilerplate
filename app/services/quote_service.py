from typing import Any, List, Optional
from datetime import datetime, timezone, timedelta
import json

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete

from app.core.cache import get_redis, cleanup_cache_keys
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models import ApiCall, QuoteSnapshot, QuoteOHLCV, Dividend, FinancialsTTM
from app.services.brapi_client import BrapiClient
from app.services.utils.key import make_cache_key
from app.services.utils.json_serializer import json_serializer, normalize_for_json, normalize_numeric, normalize_timestamp
from app.services.validation import try_validate
from app.services.ohlcv_service import _extract_ohlcv_from_quote
from app.services.utils.json_serializer import normalize_for_json as normalize

def _ts_to_datetime(ts: Any):
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    try:
        if isinstance(ts, (int, float)) or (isinstance(ts, str) and ts.strip().isdigit()):
            ts_int = int(float(ts))
            return datetime.fromtimestamp(ts_int, tz=timezone.utc)
        if isinstance(ts, str):
            cleaned = ts.strip()
            if not cleaned:
                return None
            if cleaned.endswith("Z"):
                cleaned = cleaned[:-1] + "+00:00"
            return datetime.fromisoformat(cleaned)
    except Exception:
        return None
    return None

def _extract_snapshots(payload: dict) -> list[QuoteSnapshot]:
    results = payload.get("results") or payload.get("stocks") or []
    out: list[QuoteSnapshot] = []
    for item in results:
        out.append(QuoteSnapshot(
            ticker=item.get("symbol") or item.get("ticker") or "",
            short_name=item.get("shortName"),
            currency=item.get("currency"),
            regular_market_price=normalize_numeric(item.get("regularMarketPrice")),
            previous_close=normalize_numeric(item.get("regularMarketPreviousClose")),
            market_change=normalize_numeric(item.get("regularMarketChange")),
            market_change_percent=normalize_numeric(item.get("regularMarketChangePercent")),
            regular_market_time=normalize_timestamp(item.get("regularMarketTime")),
            raw=normalize_for_json(item),  # Normaliza datetime para JSON
        ))
    return out

async def get_quote(session: AsyncSession, tickers: str, params: dict[str, Any]) -> dict[str, Any]:
    r = await get_redis()
    key = make_cache_key("quote", tickers, params)

    cached_payload = await r.get(key)
    if cached_payload:
        payload = json.loads(cached_payload)
        await _log_call(session, endpoint="quote", tickers=tickers, params=params, cached=True, status_code=200, response=payload)
        return {"cached": True, "results": payload.get("results") or []}

    client = BrapiClient()
    tick_list = [t.strip() for t in tickers.split(",") if t.strip()]
    payload = await client.quote(tick_list, params)

    ttl = settings.cache_ttl_quote_seconds
    await r.set(key, json.dumps(payload, separators=(",", ":"), default=json_serializer), ex=ttl)

    ok, obj, err = try_validate("app.openapi_models:QuoteResponse", payload)
    if not ok:
        # Validation failed – log and return error response
        await _log_call(session, endpoint="quote", tickers=tickers, params=params, cached=False, status_code=500, response={"validation_error": err})
        return {"cached": False, "error": True, "status": 500, "message": "Response validation failed", "details": err}

    await _log_call(session, endpoint="quote", tickers=tickers, params=params, cached=False, status_code=200, response=payload)

    snaps = _extract_snapshots(payload)
    if snaps:
        session.add_all(snaps)
        await session.commit()

    return {"cached": False, "results": payload.get("results") or []}


async def cleanup_quote_artifacts(session: AsyncSession) -> dict[str, int]:
    """Remove snapshots e logs antigos relacionados às cotações."""
    now = datetime.now(timezone.utc)
    stats = {
        "snapshots_removed": 0,
        "api_calls_removed": 0,
        "cache_keys_removed": 0,
    }

    cutoff_snapshots = now - timedelta(days=settings.retention_days_snapshots)
    snapshot_stmt = delete(QuoteSnapshot).where(QuoteSnapshot.created_at < cutoff_snapshots)
    snap_result = await session.execute(snapshot_stmt)
    stats["snapshots_removed"] = snap_result.rowcount or 0

    cutoff_logs = now - timedelta(days=settings.retention_days_api_calls)
    api_stmt = (
        delete(ApiCall)
        .where(ApiCall.endpoint == "quote")
        .where(ApiCall.created_at < cutoff_logs)
    )
    api_result = await session.execute(api_stmt)
    stats["api_calls_removed"] = api_result.rowcount or 0

    await session.commit()

    stats["cache_keys_removed"] = await cleanup_cache_keys(["quote:*"])
    return stats


def _extract_historical(payload: dict, symbol: str) -> List[QuoteOHLCV]:
    ohlcv_list = _extract_ohlcv_from_quote(payload, symbol)
    return ohlcv_list


def _extract_dividends(payload: dict, symbol: str) -> List[Dividend]:
    results = payload.get("results") or payload.get("stocks") or []
    dividends: List[Dividend] = []
    if not results:
        return dividends
    info = results[0]
    dividends_data = info.get("dividendsData") or {}
    cash = dividends_data.get("cashDividends") or []
    for item in cash:
        ex_date = item.get("lastDatePrior") or item.get("exDate")
        payment = item.get("paymentDate")
        ex_dt = _ts_to_datetime(ex_date)
        pay_dt = _ts_to_datetime(payment)
        dividend = Dividend(
            ticker=symbol,
            ex_date=ex_dt,
            payment_date=pay_dt,
            amount=item.get("rate"),
            currency=item.get("currency"),
            type=item.get("label"),
            raw=normalize(item),
        )
        dividends.append(dividend)
    return dividends


def _extract_ttm(payload: dict) -> Optional[dict]:
    results = payload.get("results") or payload.get("stocks") or []
    if not results:
        return None
    info = results[0]
    financial = info.get("financialData") or info.get("financial_data")
    return normalize(financial) if financial else None


async def fetch_and_enrich_asset(
    symbol: str,
    *,
    range: str = "3mo",
    interval: str = "1d",
    dividends: bool = True,
    fundamental: bool = True,
    modules: Optional[List[str]] = None,
    plan: str = "free",
) -> dict[str, Any]:
    """
    Busca e enriquece dados de um ativo único com histórico, dividendos e TTM.
    
    Args:
        symbol: Ticker do ativo
        range: Período histórico (3mo, 6mo, 1y, etc)
        interval: Intervalo dos candles (1d, 1wk, etc)
        dividends: Se deve buscar dividendos
        fundamental: Se deve buscar dados fundamentalistas
        modules: Lista de módulos adicionais (ex: ["financialData"])
        plan: Plano da API ("free" ou "premium")
    
    Returns:
        Dict com snapshot, contadores e metadados
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        raise ValueError("Símbolo inválido")

    print(f"📡 Buscando dados para {symbol} (range={range}, interval={interval})...")
    
    client = BrapiClient()
    try:
        response = await client.quote(
            [symbol],
            params=None,
            range=range,
            interval=interval,
            dividends=dividends,
            fundamental=fundamental,
            modules=modules,
            plan=plan,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403}:
            print(
                f"⚠️  Sem acesso a dados fundamentalistas para {symbol}. Tentando fallback sem fundamental/modules..."
            )
            response = await client.quote(
                [symbol],
                params=None,
                range=range,
                interval=interval,
                dividends=dividends,
                fundamental=False,
                modules=None,
                plan=plan,
            )
        else:
            raise

    snapshot_items = _extract_snapshots(response)
    
    # Criar snapshot com campos mínimos essenciais
    snapshot: dict[str, Any] = {}
    if snapshot_items and snapshot_items[0].raw:
        raw_data = snapshot_items[0].raw
        # Garantir subset mínimo de campos
        essential_fields = [
            "symbol", "shortName", "longName", "currency",
            "regularMarketPrice", "regularMarketPreviousClose",
            "regularMarketChange", "regularMarketChangePercent",
            "regularMarketTime", "regularMarketDayHigh", "regularMarketDayLow",
            "regularMarketVolume", "marketCap", "priceEarnings",
            "sector", "industry", "segment", "category",
            "isin", "isinCode", "logoUrl", "logourl",
        ]
        for field in essential_fields:
            if field in raw_data:
                snapshot[field] = raw_data[field]
    
    ohlcv_entries = _extract_historical(response, symbol)
    dividends_entries = _extract_dividends(response, symbol) if dividends else []
    ttm_data = _extract_ttm(response) if modules else None

    print(f"📊 Dados extraídos: {len(ohlcv_entries)} candles OHLCV, {len(dividends_entries)} dividendos")
    
    # Validar contagem mínima de candles
    if range == "3mo" and len(ohlcv_entries) < 45:
        print(f"⚠️  Aviso: Esperado ≥45 candles para 3mo, recebido {len(ohlcv_entries)}")
    elif range == "6mo" and len(ohlcv_entries) < 90:
        print(f"⚠️  Aviso: Esperado ≥90 candles para 6mo, recebido {len(ohlcv_entries)}")

    ohlcv_upserted = 0
    dividends_upserted = 0
    ttm_updated = False

    async with AsyncSessionLocal() as session:
        if snapshot_items:
            session.add_all(snapshot_items)
        
        for ohlcv in ohlcv_entries:
            stmt = select(QuoteOHLCV).where(QuoteOHLCV.ticker == ohlcv.ticker, QuoteOHLCV.date == ohlcv.date)
            existing = await session.execute(stmt)
            existing_obj = existing.scalar_one_or_none()
            if existing_obj:
                existing_obj.open = ohlcv.open
                existing_obj.high = ohlcv.high
                existing_obj.low = ohlcv.low
                existing_obj.close = ohlcv.close
                existing_obj.volume = ohlcv.volume
                existing_obj.adj_close = ohlcv.adj_close
                existing_obj.raw = ohlcv.raw
            else:
                session.add(ohlcv)
            ohlcv_upserted += 1

        for div in dividends_entries:
            if div.ex_date is None:
                continue
            stmt = select(Dividend).where(Dividend.ticker == div.ticker, Dividend.ex_date == div.ex_date)
            existing = await session.execute(stmt)
            existing_div = existing.scalar_one_or_none()
            if existing_div:
                existing_div.payment_date = div.payment_date
                existing_div.amount = div.amount
                existing_div.currency = div.currency
                existing_div.type = div.type
                existing_div.raw = div.raw
            else:
                session.add(div)
            dividends_upserted += 1

        if ttm_data:
            stmt = select(FinancialsTTM).where(FinancialsTTM.ticker == symbol)
            existing = await session.execute(stmt)
            record = existing.scalar_one_or_none()
            if record:
                record.data = ttm_data
                record.updated_at = datetime.now(timezone.utc)
            else:
                record = FinancialsTTM(ticker=symbol, data=ttm_data)
                session.add(record)
            ttm_updated = True

        await session.commit()
        print(f"💾 Persistido: {ohlcv_upserted} OHLCV, {dividends_upserted} dividendos, TTM={ttm_updated}")

    return {
        "symbol": symbol,
        "snapshot": snapshot,
        "ohlcv_rows_upserted": ohlcv_upserted,
        "dividends_rows_upserted": dividends_upserted,
        "ttm_updated": ttm_updated,
        "usedRange": response.get("usedRange"),
        "usedInterval": response.get("usedInterval"),
        "requestedAt": response.get("requestedAt") or datetime.now(timezone.utc).isoformat(),
    }

async def _log_call(session: AsyncSession, *, endpoint: str, tickers: str | None, params: dict | None, cached: bool, status_code: int, response: dict | None = None, error: str | None = None):
    rec = ApiCall(endpoint=endpoint, tickers=tickers, params=normalize_for_json(params) if params else None, cached=cached, status_code=status_code, error=error, response=normalize_for_json(response) if response else None)
    session.add(rec)
    await session.commit()
