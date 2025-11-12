from __future__ import annotations

from typing import Any, Dict, Iterable, List

from httpx import Request

from app.core.config import PLAN_FREE, settings
from app.core.http import get_async_client, send_request_with_retry
from app.core.limits import get_limiter


class BrapiClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.brapi_token
        self.base_url = settings.brapi_base_url.rstrip("/")
        self.plan_free = PLAN_FREE

    @staticmethod
    def _v2_path(*segments: str) -> str:
        cleaned = "/".join(part.strip("/") for part in segments if part)
        return f"/api/v2/{cleaned}" if cleaned else "/api/v2"

    def _build_params(
        self,
        base: dict[str, Any] | None,
        *,
        range: str | None,
        interval: str | None,
        dividends: bool | None,
        fundamental: bool | None,
        modules: List[str] | None,
        allow_modules: bool,
    ) -> dict[str, Any]:
        params = dict(base or {})
        if range is not None:
            params["range"] = range
        if interval is not None:
            params["interval"] = interval
        if dividends is True:
            params["dividends"] = "true"
        elif dividends is False:
            params["dividends"] = "false"
        fundamental_flag = None
        if fundamental is True:
            fundamental_flag = "true"
        elif fundamental is False:
            fundamental_flag = "false"
        if fundamental_flag and allow_modules:
            params["fundamental"] = fundamental_flag
        if modules and allow_modules:
            params["modules"] = ",".join(modules)
        return params

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _request_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        resource: str = "default",
        require_token: bool = False,
    ) -> dict[str, Any]:
        if require_token and not self.api_key:
            raise ValueError("BRAPI_TOKEN não configurado para este endpoint.")
        client = await get_async_client()
        limiter = get_limiter(resource)
        request = Request("GET", f"{self.base_url}{path}", params=params, headers=self._headers())
        async with limiter:
            response = await send_request_with_retry(client, request)
        return response.json()

    async def _fetch_quote(self, ticker: str, params: dict[str, Any]) -> dict[str, Any]:
        return await self._request_json(
            f"/api/quote/{ticker}",
            params=params,
            resource="quote",
        )

    async def _fetch_quote_batch(self, tickers: List[str], params: dict[str, Any]) -> dict[str, Any]:
        joined = ",".join(tickers)
        return await self._request_json(
            f"/api/quote/{joined}",
            params=params,
            resource="quote",
        )

    async def quote(
        self,
        tickers: Iterable[str],
        params: dict[str, Any] | None = None,
        *,
        range: str | None = None,
        interval: str | None = None,
        dividends: bool | None = None,
        fundamental: bool | None = None,
        modules: List[str] | None = None,
        plan: str | None = None,
    ) -> dict[str, Any]:
        tickers_list = [t.strip().upper() for t in tickers if t and t.strip()]
        if not tickers_list:
            return {"results": []}

        plan_normalized = plan.lower() if isinstance(plan, str) else None
        if plan_normalized is None:
            is_free_plan = self.plan_free
        else:
            is_free_plan = plan_normalized == "free"

        effective_params = self._build_params(
            params,
            range=range,
            interval=interval,
            dividends=dividends,
            fundamental=fundamental,
            modules=modules,
            allow_modules=not is_free_plan,
        )

        if is_free_plan:
            effective_params.pop("fundamental", None)
            effective_params.pop("modules", None)

        responses: List[dict[str, Any]] = []
        if not is_free_plan and len(tickers_list) > 1:
            responses.append(await self._fetch_quote_batch(tickers_list, effective_params))
        else:
            for ticker in tickers_list:
                responses.append(await self._fetch_quote(ticker, effective_params))

        if len(responses) == 1:
            return responses[0]

        merged: List[dict[str, Any]] = []
        aggregated: dict[str, Any] = {"results": merged}
        preferred_meta_keys = ("requestedAt", "usedRange", "usedInterval", "fromCache", "took")
        for payload in responses:
            stocks = (payload or {}).get("results") or (payload or {}).get("stocks") or []
            merged.extend(stocks)
            for key in preferred_meta_keys:
                if key in payload and key not in aggregated:
                    aggregated[key] = payload[key]
        return aggregated

    async def crypto(self, coins: list[str], currency: str) -> dict:
        params = {"coin": ",".join(coins), "currency": currency}
        return await self._request_json(
            self._v2_path("crypto"),
            params=params,
            resource="crypto",
            require_token=True,
        )

    async def currency(self, pairs: list[str]) -> dict:
        params = {"currency": ",".join(pairs)}
        return await self._request_json(
            self._v2_path("currency"),
            params=params,
            resource="currency",
        )

    async def inflation(self, country: str) -> dict:
        params = {"country": country}
        return await self._request_json(
            self._v2_path("inflation"),
            params=params,
            resource="macro",
        )

    async def prime_rate(self, country: str) -> dict:
        params = {"country": country}
        return await self._request_json(
            self._v2_path("prime-rate"),
            params=params,
            resource="macro",
        )

    async def currency_available(self, *, search: str | None = None) -> dict[str, Any]:
        params: Dict[str, Any] = {}
        if search:
            params["search"] = search
        return await self._request_json(
            self._v2_path("currency", "available"),
            params=params,
            resource="currency_available",
            require_token=True,
        )

    async def crypto_available(self, *, search: str | None = None) -> dict[str, Any]:
        params: Dict[str, Any] = {}
        if search:
            params["search"] = search
        return await self._request_json(
            self._v2_path("crypto", "available"),
            params=params,
            resource="crypto_available",
            require_token=True,
        )

    async def inflation_available(self, *, search: str | None = None) -> dict[str, Any]:
        params: Dict[str, Any] = {}
        if search:
            params["search"] = search
        return await self._request_json(
            self._v2_path("inflation", "available"),
            params=params,
            resource="inflation_available",
            require_token=True,
        )

    async def prime_rate_available(self, *, search: str | None = None) -> dict[str, Any]:
        params: Dict[str, Any] = {}
        if search:
            params["search"] = search
        return await self._request_json(
            self._v2_path("prime-rate", "available"),
            params=params,
            resource="prime_rate_available",
            require_token=True,
        )

    async def quote_list(
        self,
        *,
        type: str | None = None,
        sector: str | None = None,
        search: str | None = None,
        sort_by: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        params: Dict[str, Any] = {}
        if type:
            params["type"] = type
        if sector:
            params["sector"] = sector
        if search:
            params["search"] = search
        if sort_by:
            params["sortBy"] = sort_by
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["pageSize"] = page_size
        return await self._request_json(
            "/api/quote/list",
            params=params,
            resource="quote_list",
            require_token=True,
        )
