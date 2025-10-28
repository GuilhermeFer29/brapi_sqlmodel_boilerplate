from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.core.config import settings
from app.models import ApiCall
from app.services.brapi_client import BrapiClient
from app.services.validation import try_validate
from app.utils.key import make_cache_key
from app.utils.json_serializer import json_serializer, normalize_for_json

import json


def _ts_to_iso(ts: Any) -> Optional[str]:
    if ts in (None, "", 0):
        return None
    try:
        # brapi envia epoch (segundos)
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        return dt.isoformat()
    except Exception:
        return None


def _normalize_history(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrai apenas o histórico diario (OHLCV) do primeiro ativo retornado.
    Retorno: {"symbol": "...", "items": [{"date": iso, "open":..., "high":..., ...}, ...]}
    """
    results = payload.get("results") or payload.get("stocks") or []
    if not results:
        return {"symbol": None, "items": []}

    first = results[0]
    symbol = first.get("symbol") or first.get("stock")
    
    # A API BRAPI retorna historicalDataPrice (camelCase) ou historical_data_price (snake_case)
    # dependendo de como o SDK serializa
    hist: List[Dict[str, Any]] = (
        first.get("historicalDataPrice") or 
        first.get("historical_data_price") or 
        []
    )

    items: List[Dict[str, Any]] = []
    for row in hist:
        items.append(
            {
                "date": _ts_to_iso(row.get("date")),
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "volume": row.get("volume"),
            }
        )

    # ordena por data crescente (só por garantia)
    items = [x for x in items if x["date"] is not None]
    items.sort(key=lambda x: x["date"])

    return {"symbol": symbol, "items": items}


async def _log_call(
    session: AsyncSession,
    endpoint: str,
    tickers: Optional[str],
    params: Dict[str, Any],
    cached: bool,
    status_code: int,
    response: Optional[Dict[str, Any]],
) -> None:
    rec = ApiCall(
        endpoint=endpoint,
        tickers=tickers,
        params=normalize_for_json(params),
        cached=cached,
        status_code=status_code,
        response=normalize_for_json(response),
    )
    session.add(rec)
    await session.commit()


async def get_history(
    session: AsyncSession,
    ticker: str,
    period: str = "3mo",
    interval: str = "1d",
) -> Dict[str, Any]:
    """
    Busca histórico do ativo (por padrão 3 meses, diário),
    cacheia a resposta bruta da brapi e retorna versão normalizada (apenas OHLCV).
    """
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return {"cached": False, "symbol": None, "items": []}

    r = await get_redis()

    # chave de cache separada de /api/quote comum (para não conflitar)
    params = {"range": period, "interval": interval}
    cache_key = make_cache_key("quote_history", ticker, params)

    cached = await r.get(cache_key)
    if cached:
        raw_payload = json.loads(cached)
        normalized = _normalize_history(raw_payload)
        await _log_call(session, "quote_history", ticker, params, True, 200, raw_payload)
        return {"cached": True, **normalized}

    # chama brapi via SDK (nosso client já usa AsyncBrapi para quote)
    client = BrapiClient()
    raw_payload = await client.quote([ticker], params=params)

    # validação opcional com modelos gerados (se existirem)
    _ok, _obj, _err = try_validate("app.openapi_models:QuoteResponse", raw_payload)

    # cacheia (usa o TTL de quote)
    ttl = settings.cache_ttl_quote_seconds
    await r.set(cache_key, json.dumps(raw_payload, separators=(",", ":"), default=json_serializer), ex=ttl)

    await _log_call(session, "quote_history", ticker, params, False, 200, raw_payload)

    normalized = _normalize_history(raw_payload)
    return {"cached": False, **normalized}
