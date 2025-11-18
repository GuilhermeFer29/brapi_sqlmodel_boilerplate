#!/usr/bin/env python3
"""Populate the database end-to-end using only brapi.free-plan friendly endpoints.

This script is intended to be the single entry point to bootstrap every table that can
be filled with the free tier of brapi.dev. It performs the following steps:

1. (Optional) Reset the database schema
2. Ensure tables exist
3. Synchronise the asset catalogue (stock, fund, bdr)
4. Fetch OHLCV + dividend data for every asset in the catalogue (TTM disabled for free plan)
5. Print a compact summary of inserted rows

Usage inside the API container:

```
docker compose exec -T api python scripts/populate_free_plan.py --reset
```

Parameters are available via ``--help`` to fine tune ranges, asset types and throttling.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Iterable, Sequence

from sqlalchemy import text
from sqlmodel import SQLModel, select

# Ensure project root is importable when executed via ``python scripts/...``
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.models import Asset
from app.services.catalog_service import sync_assets
from app.services.quote_service import fetch_and_enrich_asset

SUPPORTED_TYPES = ("stock", "fund", "bdr")
FREE_PLAN_RANGE = "3mo"
FREE_PLAN_INTERVAL = "1d"
FREE_PLAN_MODULES: tuple[str, ...] = ()


async def ensure_database_ready(max_attempts: int = 12, delay_seconds: int = 5) -> None:
    """Block until the database accepts connections."""
    for attempt in range(1, max_attempts + 1):
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
            return
        except Exception as exc:  # noqa: BLE001
            if attempt == max_attempts:
                raise RuntimeError("Não foi possível conectar ao banco de dados.") from exc
            await asyncio.sleep(delay_seconds)


def ensure_brapi_token() -> None:
    token = (settings.brapi_token or "").strip()
    if not token:
        raise RuntimeError(
            "BRAPI_TOKEN não definido. Cadastre um token gratuito em https://brapi.dev e adicione-o ao .env"
        )


def normalise_types(types: Sequence[str] | None) -> list[str]:
    values: Iterable[str] = types or SUPPORTED_TYPES
    cleaned = []
    for entry in values:
        candidate = (entry or "").strip().lower()
        if candidate and candidate in SUPPORTED_TYPES:
            cleaned.append(candidate)
    return cleaned or list(SUPPORTED_TYPES)


async def drop_all_tables() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


async def create_all_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def sync_catalog(asset_types: Sequence[str], page_size: int) -> dict[str, int]:
    """Synchronise the asset catalogue for the provided asset types."""
    totals = {"processed": 0, "inserted": 0, "updated": 0, "errors": 0, "pages": 0}

    async with AsyncSessionLocal() as session:
        for asset_type in asset_types:
            print(f"\n🔄 Sincronizando catálogo para {asset_type}...")
            try:
                stats = await sync_assets(session, asset_type, limit=page_size)
            except Exception as exc:  # noqa: BLE001
                print(f"   ❌ Falha ao sincronizar {asset_type}: {exc}")
                totals["errors"] += 1
                continue

            for key, value in stats.items():
                if key in totals:
                    totals[key] += value

            print(
                "   ✅ {t}: {p} processados, {i} inseridos, {u} atualizados".format(
                    t=asset_type.upper(),
                    p=stats.get("processed", 0),
                    i=stats.get("inserted", 0),
                    u=stats.get("updated", 0),
                )
            )

    return totals


async def fetch_catalog_tickers(asset_types: Sequence[str], limit: int | None) -> list[str]:
    async with AsyncSessionLocal() as session:
        stmt = select(Asset.ticker).where(Asset.ticker.isnot(None))
        if asset_types:
            stmt = stmt.where(Asset.type.in_(asset_types))
        stmt = stmt.order_by(Asset.ticker)
        if limit:
            stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        return [ticker for ticker in result.scalars() if ticker]


async def enrich_assets(
    tickers: Sequence[str],
    *,
    range_: str,
    interval: str,
    include_dividends: bool,
    include_fundamental: bool,
    modules: tuple[str, ...],
    sleep_seconds: float,
) -> dict[str, int]:
    totals = {
        "tickers": 0,
        "ohlcv": 0,
        "dividends": 0,
        "ttm": 0,
        "errors": 0,
    }

    for ticker in tickers:
        try:
            result = await fetch_and_enrich_asset(
                ticker,
                range=range_,
                interval=interval,
                dividends=include_dividends,
                fundamental=include_fundamental,
                modules=list(modules) if modules else None,
                plan="free",
            )
        except Exception as exc:  # noqa: BLE001
            print(f"   ❌ {ticker}: erro durante enriquecimento ({exc})")
            totals["errors"] += 1
        else:
            totals["tickers"] += 1
            totals["ohlcv"] += result.get("ohlcv_rows_upserted", 0)
            totals["dividends"] += result.get("dividends_rows_upserted", 0)
            totals["ttm"] += 1 if result.get("ttm_updated") else 0

        if sleep_seconds:
            await asyncio.sleep(sleep_seconds)

    return totals


async def summarise_tables() -> dict[str, int]:
    queries = {
        "assets": "SELECT COUNT(*) FROM assets",
        "quote_ohlcv": "SELECT COUNT(*) FROM quote_ohlcv",
        "dividends": "SELECT COUNT(*) FROM dividends",
        "financials_ttm": "SELECT COUNT(*) FROM financials_ttm",
        "macro_points": "SELECT COUNT(*) FROM macro_points",
        "currency_snapshots": "SELECT COUNT(*) FROM currency_snapshots",
    }

    summary: dict[str, int] = {}
    async with AsyncSessionLocal() as session:
        for key, statement in queries.items():
            result = await session.execute(text(statement))
            summary[key] = int(result.scalar() or 0)
    return summary


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Popula todas as tabelas suportadas no plano free.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Dropa e recria todas as tabelas antes de popular.",
    )
    parser.add_argument(
        "--asset-types",
        nargs="*",
        default=list(SUPPORTED_TYPES),
        help="Tipos de ativos para sincronizar (default: stock fund bdr).",
    )
    parser.add_argument(
        "--sync-page-size",
        type=int,
        default=200,
        help="Quantidade de registros por página ao sincronizar catálogo (default: 200).",
    )
    parser.add_argument(
        "--max-assets",
        type=int,
        default=None,
        help="Limita a quantidade de tickers enriquecidos (default: todos).",
    )
    parser.add_argument(
        "--range",
        dest="range_",
        default=FREE_PLAN_RANGE,
        help="Período histórico para OHLCV (default: 3mo).",
    )
    parser.add_argument(
        "--interval",
        default=FREE_PLAN_INTERVAL,
        help="Intervalo histórico para OHLCV (default: 1d).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Delay (segundos) entre chamadas do enriquecimento para evitar rate limiting.",
    )
    parser.add_argument(
        "--dividends",
        action="store_true",
        help="Habilita busca de dividendos (requer plano com acesso ao recurso).",
    )
    parser.add_argument(
        "--fundamental",
        action="store_true",
        help="Habilita dados fundamentalistas/modules (requer plano pago).",
    )
    parser.add_argument(
        "--modules",
        nargs="*",
        default=list(FREE_PLAN_MODULES),
        help="Lista de módulos adicionais para o endpoint quote (premium).",
    )
    return parser.parse_args(argv)


async def main(args: argparse.Namespace) -> None:
    await ensure_database_ready()
    ensure_brapi_token()

    if args.reset:
        print("\n🗑️  Resetando banco de dados...")
        await drop_all_tables()
        await create_all_tables()
    else:
        print("\n🏗️  Garantindo schema...")
        await create_all_tables()

    asset_types = normalise_types(args.asset_types)
    print("\n📊 Etapa 1/3 — Sincronizando catálogo")
    catalog_stats = await sync_catalog(asset_types, page_size=args.sync_page_size)

    print("\n📈 Etapa 2/3 — Enriquecendo ativos")
    tickers = await fetch_catalog_tickers(asset_types, args.max_assets)
    if not tickers:
        print("⚠️  Nenhum ticker encontrado no catálogo. Encerrando.")
        return
    enrichment_stats = await enrich_assets(
        tickers,
        range_=args.range_,
        interval=args.interval,
        include_dividends=args.dividends,
        include_fundamental=args.fundamental,
        modules=tuple(args.modules or FREE_PLAN_MODULES),
        sleep_seconds=max(args.sleep, 0.0),
    )

    print("\n📋 Etapa 3/3 — Resumo")
    summary = await summarise_tables()

    print("\n=== RESULTADOS ===")
    print("Catálogo:")
    print(
        "  Processados: {processed} | Inseridos: {inserted} | Atualizados: {updated} | Erros: {errors}".format(
            **catalog_stats
        )
    )
    print("Enriquecimento:")
    print(
        "  Tickers: {tickers} | OHLCV upsertados: {ohlcv} | Dividendos upsertados: {dividends} | TTM atualizados: {ttm} | Erros: {errors}".format(
            **enrichment_stats
        )
    )
    print("Tabelas preenchidas:")
    for table, count in summary.items():
        print(f"  {table}: {count}")

    print("\n🎉 População concluída (plano free).")


if __name__ == "__main__":
    ARGS = parse_args()
    asyncio.run(main(ARGS))
