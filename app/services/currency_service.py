from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import delete
from app.core.cache import get_redis, cleanup_cache_keys
from app.core.config import settings
from app.services.brapi_client import BrapiClient
from app.services.utils.key import make_cache_key
from app.services.utils.json_serializer import json_serializer, normalize_for_json, normalize_numeric, normalize_timestamp
from app.models import ApiCall, CurrencySnapshot
from datetime import datetime, timezone, timedelta
import json
from app.services.validation import try_validate
import httpx

def _ts_to_datetime(ts: Any):
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except Exception:
        return None

def _extract_snapshots(payload: dict) -> list[CurrencySnapshot]:
    rows = payload.get("currency") or payload.get("results") or []
    out: list[CurrencySnapshot] = []
    for item in rows:
        pair = f"{item.get('fromCurrency')}-{item.get('toCurrency')}" if item.get("fromCurrency") and item.get("toCurrency") else item.get("pair") or ""
        out.append(CurrencySnapshot(
            pair=pair,
            bid=normalize_numeric(item.get("bid")),
            ask=normalize_numeric(item.get("ask")),
            pct_change=normalize_numeric(item.get("pctChange") or item.get("regularMarketChangePercent")),
            time=normalize_timestamp(item.get("regularMarketTime") or item.get("time")),
            raw=normalize_for_json(item),  # Normaliza datetime para JSON
        ))
    return out

async def get_currency(session: AsyncSession, pairs: str) -> dict[str, Any]:
    r = await get_redis()
    params: dict[str, Any] = {}
    key = make_cache_key("currency", pairs, params)

    cached = await r.get(key)
    if cached:
        payload = json.loads(cached)
        await _log_call(session, "currency", pairs, params, True, 200, payload)
        return {"cached": True, "results": payload}

    client = BrapiClient()
    pair_list = [p.strip() for p in pairs.split(",") if p.strip()]
    try:
        payload = await client.currency(pair_list)
    except httpx.HTTPStatusError as e:
        body = {}
        try:
            body = e.response.json()
        except Exception:
            body = {"message": e.response.text}
        await _log_call(session, "currency", pairs, params, False, e.response.status_code, body)
        return {"cached": False, "error": True, "status": e.response.status_code, "message": body.get("message"), "details": body}

    ttl = settings.cache_ttl_currency_seconds
    await r.set(key, json.dumps(payload, separators=(",", ":"), default=json_serializer), ex=ttl)

    _ok, _obj, _err = try_validate("app.openapi_models:CurrencyResponse", payload)
    if not _ok:
        await _log_call(session, "currency", pairs, params, False, 500, {"validation_error": _err})
        return {"cached": False, "error": True, "status": 500, "message": "Response validation failed", "details": _err}

    await _log_call(session, "currency", pairs, params, False, 200, payload)

    snaps = _extract_snapshots(payload)
    if snaps:
        for snap in snaps:
            session.merge(snap)
        await session.commit()

    return {"cached": False, "results": payload}

async def _log_call(session: AsyncSession, endpoint: str, tickers: str | None, params: dict | None, cached: bool, status_code: int, response: dict | None):
    rec = ApiCall(endpoint=endpoint, tickers=tickers, params=normalize_for_json(params) if params else None, cached=cached, status_code=status_code, response=normalize_for_json(response) if response else None)
    session.add(rec)
    await session.commit()


async def cleanup_currency_artifacts(session: AsyncSession) -> dict[str, int]:
    """Remove snapshots e logs antigos de câmbio."""
    now = datetime.now(timezone.utc)
    stats = {
        "snapshots_removed": 0,
        "api_calls_removed": 0,
        "cache_keys_removed": 0,
    }

    cutoff_snapshots = now - timedelta(days=settings.retention_days_currency)
    snapshot_stmt = delete(CurrencySnapshot).where(CurrencySnapshot.created_at < cutoff_snapshots)
    snap_result = await session.execute(snapshot_stmt)
    stats["snapshots_removed"] = snap_result.rowcount or 0

    cutoff_logs = now - timedelta(days=settings.retention_days_api_calls)
    api_stmt = (
        delete(ApiCall)
        .where(ApiCall.endpoint == "currency")
        .where(ApiCall.created_at < cutoff_logs)
    )
    api_result = await session.execute(api_stmt)
    stats["api_calls_removed"] = api_result.rowcount or 0

    await session.commit()

    stats["cache_keys_removed"] = await cleanup_cache_keys(["currency:*"])
    return stats
