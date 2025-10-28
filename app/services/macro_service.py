from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.cache import get_redis
from app.core.config import settings
from app.services.brapi_client import BrapiClient
from app.utils.key import make_cache_key
from app.utils.json_serializer import json_serializer, normalize_for_json
from app.models import ApiCall, MacroPoint
from datetime import datetime, timezone
import json
from app.services.validation import try_validate
import httpx

def _parse_date(s: Any):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        try:
            return datetime.fromtimestamp(int(s), tz=timezone.utc)
        except Exception:
            return None

def _extract_macro(series: str, country: str, payload: dict) -> list[MacroPoint]:
    data = payload.get("data") or payload.get("results") or payload
    if isinstance(data, dict):
        data = data.get("values") or data.get("points") or []
    out: list[MacroPoint] = []
    if isinstance(data, list):
        for item in data:
            out.append(MacroPoint(
                series=series,
                country=country,
                ref_date=_parse_date(item.get("date") or item.get("ref") or item.get("time")),
                value=item.get("value") or item.get("val") or item.get("rate"),
                raw=normalize_for_json(item),  # Normaliza datetime para JSON
            ))
    return out

async def get_inflation(session: AsyncSession, country: str) -> dict[str, Any]:
    r = await get_redis()
    params = {"country": country}
    key = make_cache_key("inflation", country, params)

    cached = await r.get(key)
    if cached:
        payload = json.loads(cached)
        await _log_call(session, "inflation", country, params, True, 200, payload)
        return {"cached": True, "results": payload}

    client = BrapiClient()
    try:
        payload = await client.inflation(country)
    except httpx.HTTPStatusError as e:
        body = {}
        try:
            body = e.response.json()
        except Exception:
            body = {"message": e.response.text}
        await _log_call(session, "inflation", country, params, False, e.response.status_code, body)
        return {"cached": False, "error": True, "status": e.response.status_code, "message": body.get("message"), "details": body}

    ttl = settings.cache_ttl_macro_seconds
    await r.set(key, json.dumps(payload, separators=(",", ":"), default=json_serializer), ex=ttl)

    _ok, _obj, _err = try_validate("app.openapi_models:MacroResponse", payload)

    await _log_call(session, "inflation", country, params, False, 200, payload)

    pts = _extract_macro("inflation", country, payload)
    if pts:
        session.add_all(pts)
        await session.commit()

    return {"cached": False, "results": payload}

async def get_prime_rate(session: AsyncSession, country: str) -> dict[str, Any]:
    r = await get_redis()
    params = {"country": country}
    key = make_cache_key("prime_rate", country, params)

    cached = await r.get(key)
    if cached:
        payload = json.loads(cached)
        await _log_call(session, "prime_rate", country, params, True, 200, payload)
        return {"cached": True, "results": payload}

    client = BrapiClient()
    try:
        payload = await client.prime_rate(country)
    except httpx.HTTPStatusError as e:
        body = {}
        try:
            body = e.response.json()
        except Exception:
            body = {"message": e.response.text}
        await _log_call(session, "prime_rate", country, params, False, e.response.status_code, body)
        return {"cached": False, "error": True, "status": e.response.status_code, "message": body.get("message"), "details": body}

    ttl = settings.cache_ttl_macro_seconds
    await r.set(key, json.dumps(payload, separators=(",", ":"), default=json_serializer), ex=ttl)

    _ok, _obj, _err = try_validate("app.openapi_models:MacroResponse", payload)

    await _log_call(session, "prime_rate", country, params, False, 200, payload)

    pts = _extract_macro("prime_rate", country, payload)
    if pts:
        session.add_all(pts)
        await session.commit()

    return {"cached": False, "results": payload}

async def _log_call(session: AsyncSession, endpoint: str, tickers: str | None, params: dict | None, cached: bool, status_code: int, response: dict | None):
    rec = ApiCall(endpoint=endpoint, tickers=tickers, params=normalize_for_json(params), cached=cached, status_code=status_code, response=normalize_for_json(response))
    session.add(rec)
    await session.commit()
