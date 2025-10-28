from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.cache import get_redis
from app.core.config import settings
from app.services.brapi_client import BrapiClient
from app.utils.key import make_cache_key
from app.utils.json_serializer import json_serializer, normalize_for_json
from app.models import ApiCall, CryptoSnapshot
from datetime import datetime, timezone
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

def _extract_snapshots(payload: dict) -> list[CryptoSnapshot]:
    rows = payload.get("coins") or payload.get("results") or []
    out: list[CryptoSnapshot] = []
    for item in rows:
        out.append(CryptoSnapshot(
            symbol=item.get("coin") or item.get("symbol") or "",
            currency=item.get("currency"),
            price=item.get("regularMarketPrice") or item.get("price"),
            change=item.get("regularMarketChange") or item.get("change"),
            change_percent=item.get("regularMarketChangePercent") or item.get("changePercent"),
            time=_ts_to_datetime(item.get("regularMarketTime") or item.get("time")),
            raw=normalize_for_json(item),  # Normaliza datetime para JSON
        ))
    return out

async def get_crypto(session: AsyncSession, coins: str, currency: str) -> dict[str, Any]:
    r = await get_redis()
    params = {"currency": currency}
    key = make_cache_key("crypto", coins, params)

    cached = await r.get(key)
    if cached:
        payload = json.loads(cached)
        await _log_call(session, "crypto", coins, params, True, 200, payload)
        return {"cached": True, "results": payload}

    client = BrapiClient()
    coin_list = [c.strip() for c in coins.split(",") if c.strip()]

    try:
        payload = await client.crypto(coin_list, currency)
    except httpx.HTTPStatusError as e:
        body = {}
        try:
            body = e.response.json()
        except Exception:
            body = {"message": e.response.text}
        await _log_call(session, "crypto", coins, params, False, e.response.status_code, body)
        return {"cached": False, "error": True, "status": e.response.status_code, "message": body.get("message"), "details": body}
    except ValueError as e:
        await _log_call(session, "crypto", coins, params, False, 400, {"message": str(e)})
        return {"cached": False, "error": True, "status": 400, "message": str(e)}

    ttl = settings.cache_ttl_crypto_seconds
    await r.set(key, json.dumps(payload, separators=(",", ":"), default=json_serializer), ex=ttl)

    _ok, _obj, _err = try_validate("app.openapi_models:CryptoResponse", payload)

    await _log_call(session, "crypto", coins, params, False, 200, payload)

    snaps = _extract_snapshots(payload)
    if snaps:
        session.add_all(snaps)
        await session.commit()

    return {"cached": False, "results": payload}

async def _log_call(session: AsyncSession, endpoint: str, tickers: str | None, params: dict | None, cached: bool, status_code: int, response: dict | None):
    rec = ApiCall(endpoint=endpoint, tickers=tickers, params=normalize_for_json(params), cached=cached, status_code=status_code, response=normalize_for_json(response))
    session.add(rec)
    await session.commit()
