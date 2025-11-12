from fastapi import FastAPI
import asyncio
from app.db.session import create_all, check_db
from app.core.cache import check_redis_connection
from app.api.routes.quote import router as quote_router
from app.api.routes.crypto import router as crypto_router
from app.api.routes.currency import router as currency_router
from app.api.routes.macro import router as macro_router
from app.api.routes.available import router as available_router
from app.api.routes.history import router as history_router
from app.api.routes.prime_rate_scan import router as prime_rate_scan_router
from app.api.routes.catalog import router as catalog_router
from app.api.routes.ohlcv import router as ohlcv_router
app = FastAPI(title="brapi Boilerplate (SQLModel + SDK + Cache)")

async def wait_for(predicate, name: str, attempts: int = 90, delay: int = 2):
    for _ in range(attempts):
        if await predicate():
            return True
        await asyncio.sleep(delay)
    raise RuntimeError(f"{name} não ficou pronto após {attempts * delay}s")

@app.on_event("startup")
async def on_startup():
    await wait_for(check_db, "MySQL")
    await create_all()
    await wait_for(check_redis_connection, "Redis")

app.include_router(quote_router)
app.include_router(crypto_router)
app.include_router(currency_router)
app.include_router(macro_router)
app.include_router(available_router)
app.include_router(history_router)
app.include_router(prime_rate_scan_router)
app.include_router(catalog_router)
app.include_router(ohlcv_router)

@app.get("/health")
async def health():
    db_ok = await check_db()
    redis_ok = await check_redis_connection()
    return {"db": "ok" if db_ok else "down", "redis": "ok" if redis_ok else "down"}
