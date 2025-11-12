from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.cache import get_redis
from app.services.brapi_client import BrapiClient
from app.services.utils.key import make_cache_key
from app.services.utils.json_serializer import json_serializer, normalize_for_json
from app.models import ApiCall
import json
import httpx

async def get_available(session: AsyncSession) -> dict[str, Any]:
    r = await get_redis()
    key = make_cache_key("available", "all", {})

    cached = await r.get(key)
    if cached:
        payload = json.loads(cached)
        await _log_call(session, "available", None, {}, True, 200, payload)
        return {"cached": True, "results": payload}

    client = BrapiClient()
    try:
        payload = await client.available()
    except httpx.HTTPStatusError as e:
        body = {}
        try:
            body = e.response.json()
        except Exception:
            body = {"message": e.response.text}
        await _log_call(session, "available", None, {}, False, e.response.status_code, body)
        return {"cached": False, "error": True, "status": e.response.status_code, "message": body.get("message"), "details": body}

    await r.set(key, json.dumps(payload, separators=(",", ":"), default=json_serializer), ex=86400)
    await _log_call(session, "available", None, {}, False, 200, payload)
    return {"cached": False, "results": payload}

async def _log_call(session: AsyncSession, endpoint: str, tickers: str | None, params: dict | None, cached: bool, status_code: int, response: dict | None):
    rec = ApiCall(endpoint=endpoint, tickers=tickers, params=normalize_for_json(params) if params else None, cached=cached, status_code=status_code, response=normalize_for_json(response) if response else None)
    session.add(rec)
    await session.commit()
