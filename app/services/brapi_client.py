from typing import Any
from app.core.config import settings
from brapi import AsyncBrapi
import json
import httpx

class BrapiClient:
    def __init__(self, api_key: str | None = None, timeout: float | None = None, max_retries: int | None = None):
        self.api_key = api_key or settings.brapi_token
        self.timeout = timeout or 10.0
        self.max_retries = max_retries or 2

    async def quote(self, tickers: list[str], params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = dict(params or {})
        tickers = [t.strip().upper() for t in tickers if t and t.strip()]
        if not tickers:
            return {"results": []}
        async with AsyncBrapi(api_key=self.api_key, timeout=self.timeout, max_retries=self.max_retries) as client:
            import asyncio
            async def fetch_one(t: str):
                resp = await client.quote.retrieve(tickers=t, **params)
                try:
                    # by_alias=True para manter os nomes originais da API (camelCase)
                    return resp.model_dump(by_alias=True)
                except Exception:
                    if hasattr(resp, "__dict__") and resp.__dict__:
                        return json.loads(json.dumps(resp, default=lambda o: o.__dict__))
                    return resp
            per_ticker = await asyncio.gather(*[fetch_one(t) for t in tickers], return_exceptions=False)
        merged = []
        for item in per_ticker:
            stocks = (item or {}).get("results") or (item or {}).get("stocks") or []
            merged.extend(stocks)
        return {"results": merged}

    async def crypto(self, coins: list[str], currency: str) -> dict:
        # /api/v2/crypto requer token
        if not self.api_key:
            raise ValueError("BRAPI_TOKEN não configurado: /api/v2/crypto requer autenticação.")
        url = f"{settings.brapi_base_url}/api/v2/crypto"
        params = {"coin": ",".join(coins), "currency": currency}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(url, params=params, headers=headers)
            r.raise_for_status()
            return r.json()

    async def currency(self, pairs: list[str]) -> dict:
        url = f"{settings.brapi_base_url}/api/v2/currency"
        params = {"currency": ",".join(pairs)}
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(url, params=params, headers=headers)
            r.raise_for_status()
            return r.json()

    async def inflation(self, country: str) -> dict:
        url = f"{settings.brapi_base_url}/api/v2/inflation"
        params = {"country": country}
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(url, params=params, headers=headers)
            r.raise_for_status()
            return r.json()

    async def prime_rate(self, country: str) -> dict:
        url = f"{settings.brapi_base_url}/api/v2/prime-rate"
        params = {"country": country}
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(url, params=params, headers=headers)
            r.raise_for_status()
            return r.json()

    async def available(self) -> dict:
        url = f"{settings.brapi_base_url}/api/available"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            return r.json()
