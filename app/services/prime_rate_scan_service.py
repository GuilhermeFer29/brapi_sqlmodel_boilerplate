from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import asyncio
import json
import httpx

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.core.config import settings
from app.models import ApiCall, MacroPoint
from app.services.brapi_client import BrapiClient
from app.services.validation import try_validate
from app.services.utils.key import make_cache_key
from app.services.utils.json_serializer import json_serializer, normalize_for_json


# -------- utils --------

def _parse_date(s: Any) -> Optional[datetime]:
    """Aceita epoch em segundos/milissegundos, ISO e dd/MM/yyyy."""
    if not s:
        return None

    # epoch (s ou ms)
    if isinstance(s, (int, float)):
        try:
            x = float(s)
            # heurística: se muito grande, trata como ms
            if x > 1e12:
                x = x / 1000.0
            return datetime.fromtimestamp(x, tz=timezone.utc)
        except Exception:
            pass

    if isinstance(s, str):
        ss = s.strip()
        # normaliza 'Z' => +00:00
        if ss.endswith("Z"):
            ss = ss[:-1] + "+00:00"

        # tenta vários formatos comuns
        for fmt in (
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%d/%m/%Y",  # dd/MM/yyyy (ex.: 23/10/2025)
        ):
            try:
                dt = datetime.strptime(ss, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                continue

    return None


def _to_iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if isinstance(dt, datetime) else None


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
        params=normalize_for_json(params) if params else None,
        cached=cached,
        status_code=status_code,
        response=normalize_for_json(response) if response else None,
    )
    session.add(rec)
    await session.commit()


# -------- core fetchers --------

async def _fetch_available_countries() -> Dict[str, Any]:
    """
    GET /api/v2/prime-rate/available
    Requer token. Retorna lista de países suportados.
    """
    if not settings.brapi_token:
        raise ValueError("BRAPI_TOKEN não configurado para /prime-rate/available")

    url = f"{settings.brapi_base_url}/api/v2/prime-rate/available"
    headers = {"Authorization": f"Bearer {settings.brapi_token}"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        return r.json()


def _latest_from_payload(country: str, payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[float]]:
    """
    Suporta diferentes formatos da brapi, incluindo:
      - {"data":[...]}
      - {"results":[...]}
      - {"values":[...]} dentro de dict
      - {"prime-rate":[...]}  <-- observado no seu retorno
      - lista direta [...]
    Seleciona o ponto com maior data.
    """
    candidates: List[Any] = []

    # caminhos conhecidos em nível raiz
    for key in ("data", "results", "values", "points", "items", "series", "prime-rate"):
        v = payload.get(key)
        if isinstance(v, list):
            candidates.append(v)
        elif isinstance(v, dict):
            # casos aninhados
            for k2 in ("values", "points", "items", "series"):
                vv = v.get(k2)
                if isinstance(vv, list):
                    candidates.append(vv)

    # fallback: payload já ser lista
    if not candidates and isinstance(payload, list):
        candidates.append(payload)

    latest_date: Optional[datetime] = None
    latest_value: Optional[float] = None

    for data in candidates:
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue

            # datas possíveis: "date" (string dd/MM/yyyy ou ISO), "ref"/"time" ou "epochDate" (ms)
            d = _parse_date(item.get("date") or item.get("ref") or item.get("time") or item.get("epochDate"))

            # value pode vir como string "15.00" -> float
            v_raw = item.get("value") or item.get("val") or item.get("rate")
            try:
                v = float(str(v_raw).replace(",", ".")) if v_raw is not None else None
            except Exception:
                v = None

            if d is None:
                continue
            if latest_date is None or d > latest_date:
                latest_date = d
                latest_value = v

    return _to_iso(latest_date), latest_value


async def _fetch_latest_for_country(client: BrapiClient, country: str) -> Dict[str, Any]:
    """
    Usa o client para pegar prime-rate de 1 país, extraindo o último valor.
    """
    try:
        payload = await client.prime_rate(country)
        # validação opcional
        _ok, _obj, _err = try_validate("app.openapi_models:MacroResponse", payload)
    except httpx.HTTPStatusError as e:
        try:
            body = e.response.json()
        except Exception:
            body = {"message": e.response.text}
        return {"country": country, "error": True, "status": e.response.status_code, "message": body.get("message"), "details": body}
    except Exception as e:
        return {"country": country, "error": True, "status": 500, "message": str(e)}

    date_iso, value = _latest_from_payload(country, payload)
    return {"country": country, "date": date_iso, "value": value, "raw": payload}


# -------- public service --------

async def scan_prime_rate(
    session: AsyncSession,
    include_latest: bool = True,
    concurrency: int = 6,
) -> Dict[str, Any]:
    """
    1) Busca países disponíveis em /prime-rate/available
    2) (opcional) Busca último valor por país em paralelo (limite de concorrência)
    3) Cacheia e registra auditoria; persiste MacroPoint quando possível
    """
    r = await get_redis()

    params = {"include_latest": include_latest, "concurrency": int(concurrency)}

    # Usa uma "versão" na chave para invalidar cache antigo
    cache_key = make_cache_key("prime_rate_scan_v2", "all", params)

    cached = await r.get(cache_key)
    if cached:
        agg = json.loads(cached)
        await _log_call(session, "prime_rate_scan", None, params, True, 200, agg)
        return {"cached": True, **agg}

    # 1) países disponíveis
    available = await _fetch_available_countries()
    countries: List[str] = (
        available.get("countries")
        or available.get("results")
        or available.get("data")
        or []
    )
    countries = [c for c in countries if isinstance(c, str) and c.strip()]
    countries = sorted(set(countries))

    agg: Dict[str, Any] = {"countries": countries}

    # 2) últimos valores por país
    if include_latest and countries:
        client = BrapiClient()
        sem = asyncio.Semaphore(max(1, int(concurrency)))

        async def task(country: str):
            async with sem:
                return await _fetch_latest_for_country(client, country)

        results = await asyncio.gather(*[task(c) for c in countries], return_exceptions=False)
        agg["results"] = results

        # persiste MacroPoint apenas dos que vieram ok
        to_persist: List[MacroPoint] = []
        for res in results:
            if res.get("error"):
                continue
            date_iso = res.get("date")
            value = res.get("value")
            if date_iso is None:
                continue
            mp = MacroPoint(
                series="prime_rate",
                country=res["country"],
                ref_date=_parse_date(date_iso),
                value=value,
                raw=res.get("raw"),
            )
            to_persist.append(mp)

        if to_persist:
            session.add_all(to_persist)
            await session.commit()

    # 3) cache + audit (com serializador seguro)
    ttl = settings.cache_ttl_macro_seconds
    await r.set(cache_key, json.dumps(agg, separators=(",", ":"), default=json_serializer), ex=ttl)
    await _log_call(session, "prime_rate_scan", None, params, False, 200, agg)

    return {"cached": False, **agg}
