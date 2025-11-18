#!/usr/bin/env python3
"""Populate auxiliary datasets (macro, currencies, dividends, financials).

This script complements ``scripts/populate_all.py`` by focusing on tables that
are not filled automatically during the initial bootstrap:

* ``macro_points``
* ``currency_snapshots``
* ``dividends``
* ``financials_ttm``

It orchestrates existing service-layer helpers so the ingestion logic remains in
one place. Run it inside the API container so it shares the same environment and
network stack:

```
docker compose exec -T api python scripts/populate_extra_datasets.py \
  --macro-countries brazil united_states \
  --currency-pairs USD-BRL EUR-BRL BTC-BRL \
  --max-tickers 50
```
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Iterable, Sequence

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from sqlmodel import SQLModel, select

from app.db.session import AsyncSessionLocal, engine
from app.models import Asset
from app.services.macro_service import get_inflation, get_prime_rate
from app.services.currency_service import get_currency
from app.services.quote_service import fetch_and_enrich_asset

REQUIRED_TABLES = {
    "api_calls",
    "macro_points",
    "currency_snapshots",
    "dividends",
    "financials_ttm",
}


async def populate_macro(countries: Sequence[str], skip_external: bool) -> None:
    if not countries:
        return

    print("\n📰 Populando indicadores macroeconômicos...")
    async with AsyncSessionLocal() as session:
        for country in countries:
            country = country.strip()
            if not country:
                continue
            print(f"   🌎 {country} - inflação")
            await get_inflation(session, country)
            print(f"   🌎 {country} - taxa básica")
            await get_prime_rate(session, country)


async def populate_currencies(pairs: Sequence[str]) -> None:
    clean_pairs = [p.strip().upper() for p in pairs if p.strip()]
    if not clean_pairs:
        return

    print("\n💱 Populando snapshots de câmbio...")
    pairs_str = ",".join(clean_pairs)
    async with AsyncSessionLocal() as session:
        await get_currency(session, pairs_str)


async def populate_financials_and_dividends(
    *,
    max_tickers: int,
    types: Sequence[str],
    range_: str,
    interval: str,
) -> None:
    async with AsyncSessionLocal() as session:
        stmt = select(Asset.ticker).where(Asset.ticker.isnot(None))
        if types:
            stmt = stmt.where(Asset.type.in_(types))
        stmt = stmt.order_by(Asset.ticker)
        if max_tickers:
            stmt = stmt.limit(max_tickers)

        result = await session.execute(stmt)
        tickers = [row for row in result.scalars() if row]

    if not tickers:
        print("\n⚠️  Nenhum ticker disponível para enriquecer.")
        return

    print(
        f"\n📈 Enriquecendo dividendos e dados financeiros para {len(tickers)} ativos..."
    )
    processed = 0
    for ticker in tickers:
        try:
            await fetch_and_enrich_asset(
                ticker,
                range=range_,
                interval=interval,
                dividends=True,
                fundamental=True,
                modules=["financialData"],
                plan="free",
            )
            processed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"   ❌ {ticker}: erro durante enriquecimento ({exc})")

    print(f"\n✅ Enriquecimento concluído ({processed}/{len(tickers)} ativos).")


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Popula datasets auxiliares.")
    parser.add_argument(
        "--macro-countries",
        nargs="*",
        default=["brazil", "united_states"],
        help="Lista de países para inflação e taxa básica (default: brazil, united_states)",
    )
    parser.add_argument(
        "--currency-pairs",
        nargs="*",
        default=["USD-BRL", "EUR-BRL", "BTC-BRL", "GBP-BRL"],
        help="Pares cambiais (formato FROM-TO).",
    )
    parser.add_argument(
        "--max-tickers",
        type=int,
        default=30,
        help="Quantidade máxima de ativos para enriquecer com dividendos e financials.",
    )
    parser.add_argument(
        "--types",
        nargs="*",
        default=["stock", "fund", "bdr"],
        help="Tipos de ativos elegíveis (default: stock fund bdr).",
    )
    parser.add_argument(
        "--range",
        dest="range_",
        default="3mo",
        help="Range histórico para OHLCV (default: 3mo).",
    )
    parser.add_argument(
        "--interval",
        default="1d",
        help="Intervalo histórico para OHLCV (default: 1d).",
    )
    parser.add_argument(
        "--skip-macro",
        action="store_true",
        help="Não popular macro_points.",
    )
    parser.add_argument(
        "--skip-currency",
        action="store_true",
        help="Não popular currency_snapshots.",
    )
    parser.add_argument(
        "--skip-financials",
        action="store_true",
        help="Não enriquecer financials/dividends.",
    )
    return parser.parse_args(argv)


async def ensure_database_ready(max_attempts: int = 10, delay_seconds: int = 3) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
            print("\n✅ Conexão com o banco estabelecida.")
            return
        except Exception as exc:  # noqa: BLE001
            if attempt == max_attempts:
                raise RuntimeError("Não foi possível conectar ao banco de dados.") from exc
            print(
                f"\n⏳ Aguardando banco ficar disponível (tentativa {attempt}/{max_attempts}): {exc}"  # noqa: B950
            )
            await asyncio.sleep(delay_seconds)


async def ensure_required_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SHOW TABLES"))
        existing = {row[0] for row in result}

    missing = sorted(REQUIRED_TABLES.difference(existing))
    if missing:
        raise RuntimeError(
            "As seguintes tabelas não foram encontradas: " + ", ".join(missing)
        )


async def main(args: argparse.Namespace) -> None:
    await ensure_database_ready()
    await ensure_required_tables()

    if not args.skip_macro:
        await populate_macro(args.macro_countries)

    if not args.skip_currency:
        await populate_currencies(args.currency_pairs)

    if not args.skip_financials:
        await populate_financials_and_dividends(
            max_tickers=args.max_tickers,
            types=args.types,
            range_=args.range_,
            interval=args.interval,
        )

    print("\n🎉 População de datasets auxiliares finalizada.")


if __name__ == "__main__":
    cli_args = parse_args()
    asyncio.run(main(cli_args))
