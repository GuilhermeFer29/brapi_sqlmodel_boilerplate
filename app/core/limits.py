"""Async rate limiting helpers."""
from __future__ import annotations

from typing import Dict

from aiolimiter import AsyncLimiter

_DEFAULT_LIMITS: Dict[str, AsyncLimiter] = {}


def get_limiter(resource: str) -> AsyncLimiter:
    """Return (and cache) a limiter for given resource name."""
    if resource not in _DEFAULT_LIMITS:
        # default budget ~3 req/s with burst of 1 to stay safe on brapi free tier
        _DEFAULT_LIMITS[resource] = AsyncLimiter(max_rate=3, time_period=1)
    return _DEFAULT_LIMITS[resource]
