"""Shared HTTP client utilities."""
from __future__ import annotations

import asyncio
from typing import Optional

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

_client: Optional[httpx.AsyncClient] = None
_client_lock = asyncio.Lock()

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class RetryableHTTPStatusError(httpx.HTTPStatusError):
    """HTTPStatusError subclass used for retry decisions."""


async def send_request_with_retry(client: httpx.AsyncClient, request: httpx.Request, *, max_attempts: int = 4) -> httpx.Response:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(max_attempts),
        retry=retry_if_exception_type((httpx.TransportError, RetryableHTTPStatusError)),
        wait=wait_exponential_jitter(initial=0.5, max=5.0, exp_base=2),
        reraise=True,
    ):
        with attempt:
            response = await client.send(request)
            if response.status_code in {429, 500, 502, 503, 504}:
                raise RetryableHTTPStatusError("Retryable status", request=request, response=response)
            response.raise_for_status()
            return response
    raise RuntimeError("retry loop exhausted")


async def get_async_client() -> httpx.AsyncClient:
    """Return a shared AsyncClient instance with retry helper attached."""
    global _client
    if _client is not None:
        return _client

    async with _client_lock:
        if _client is None:
            _client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
        return _client


async def close_async_client() -> None:
    global _client
    async with _client_lock:
        if _client is not None:
            await _client.aclose()
            _client = None
