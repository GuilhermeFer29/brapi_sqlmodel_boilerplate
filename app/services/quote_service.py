from typing import Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.core.cache import get_redis
from app.core.config import settings
from app.services.brapi_client import BrapiClient
from app.utils.key import make_cache_key
from app.utils.json_serializer import json_serializer, normalize_for_json
from app.models import ApiCall, QuoteSnapshot
from datetime import datetime, timezone
import json
from app.services.validation import try_validate

def _ts_to_datetime(ts: Any):
    if ts is None: return None
    try: return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except Exception: return None

def _extract_snapshots(payload: dict) -> list[QuoteSnapshot]:
    results = payload.get("results") or payload.get("stocks") or []
    out: list[QuoteSnapshot] = []
    for item in results:
        out.append(QuoteSnapshot(
            ticker=item.get("symbol") or item.get("ticker") or "",
            short_name=item.get("shortName"),
            currency=item.get("currency"),
            regular_market_price=item.get("regularMarketPrice"),
            previous_close=item.get("regularMarketPreviousClose"),
            market_change=item.get("regularMarketChange"),
            market_change_percent=item.get("regularMarketChangePercent"),
            regular_market_time=_ts_to_datetime(item.get("regularMarketTime")),
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

    await _log_call(session, endpoint="quote", tickers=tickers, params=params, cached=False, status_code=200, response=payload)

    snaps = _extract_snapshots(payload)
    if snaps:
        session.add_all(snaps)
        await session.commit()

    return {"cached": False, "results": payload.get("results") or []}

async def _log_call(session: AsyncSession, *, endpoint: str, tickers: str | None, params: dict | None, cached: bool, status_code: int, response: dict | None = None, error: str | None = None):
    rec = ApiCall(endpoint=endpoint, tickers=tickers, params=normalize_for_json(params), cached=cached, status_code=status_code, error=error, response=normalize_for_json(response))
    session.add(rec)
    await session.commit()
