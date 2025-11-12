from typing import Any, Dict, Iterable

import json
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.services.brapi_client import BrapiClient
from app.services.utils.json_serializer import json_serializer, normalize_for_json
from app.services.utils.key import make_cache_key
from app.models import ApiCall


AVAILABLE_TTL_SECONDS = 86400


def _merge_available_payloads(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza o payload de disponibilidade agrupando por domínio."""
    def _unique(items: Iterable[Any]) -> list[str]:
        uniq = {str(item).strip() for item in items if isinstance(item, str) and str(item).strip()}
        return sorted(uniq)

    return {
        "stocks": _unique(data.get("stocks") or []),
        "indexes": _unique(data.get("indexes") or []),
        "availableSectors": _unique(data.get("availableSectors") or data.get("stock_sectors") or []),
        "availableStockTypes": _unique(data.get("availableStockTypes") or data.get("stock_types") or []),
        "currencies": _unique(data.get("currencies") or []),
        "coins": _unique(data.get("coins") or []),
        "inflation_countries": _unique(data.get("inflation_countries") or []),
        "prime_rate_countries": _unique(data.get("prime_rate_countries") or []),
    }


async def get_available(session: AsyncSession) -> dict[str, Any]:
    redis = await get_redis()
    key = make_cache_key("available", "all", {})

    cached = await redis.get(key)
    if cached:
        payload = json.loads(cached)
        await _log_call(session, cached=True, status_code=200, response=payload)
        return {"cached": True, "results": payload}

    client = BrapiClient()

    try:
        stocks_payload = await client.quote_list()
        currencies_payload = await client.currency_available()
        crypto_payload = await client.crypto_available()
        inflation_payload = await client.inflation_available()
        prime_payload = await client.prime_rate_available()
    except ValueError as e:
        message = str(e) or "Token brapi ausente para endpoints /available"
        await _log_call(session, cached=False, status_code=401, response={"message": message})
        return {
            "cached": False,
            "error": True,
            "status": 401,
            "message": message,
        }
    except httpx.HTTPStatusError as e:
        body: Dict[str, Any] = {}
        try:
            body = e.response.json()
        except Exception:
            body = {"message": e.response.text}
        await _log_call(session, cached=False, status_code=e.response.status_code, response=body)
        return {
            "cached": False,
            "error": True,
            "status": e.response.status_code,
            "message": body.get("message"),
            "details": body,
        }

    merged: Dict[str, Any] = {
        "stocks": (stocks_payload.get("stocks") or []),
        "indexes": (stocks_payload.get("indexes") or []),
        "availableSectors": stocks_payload.get("availableSectors") or [],
        "availableStockTypes": stocks_payload.get("availableStockTypes") or [],
        "currencies": currencies_payload.get("currencies") or [],
        "coins": crypto_payload.get("coins") or [],
        "inflation_countries": (
            inflation_payload.get("countries")
            or inflation_payload.get("results")
            or inflation_payload.get("data")
            or []
        ),
        "prime_rate_countries": (
            prime_payload.get("countries")
            or prime_payload.get("results")
            or prime_payload.get("data")
            or []
        ),
    }

    normalized = _merge_available_payloads(merged)

    await redis.set(key, json.dumps(normalized, separators=(",", ":"), default=json_serializer), ex=AVAILABLE_TTL_SECONDS)
    await _log_call(session, cached=False, status_code=200, response=normalized)
    return {"cached": False, "results": normalized}


async def _log_call(
    session: AsyncSession,
    *,
    cached: bool,
    status_code: int,
    response: Dict[str, Any] | None,
) -> None:
    record = ApiCall(
        endpoint="available",
        tickers=None,
        params=None,
        cached=cached,
        status_code=status_code,
        response=normalize_for_json(response) if response else None,
    )
    session.add(record)
    await session.commit()
