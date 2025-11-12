#!/usr/bin/env python3
"""
Script completo para popular o banco do zero com todos os dados.
Este script:
1. Limpa o banco existente
2. Sincroniza o catálogo completo
3. Preenche dados históricos para tickers populares
4. Verifica a população
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import Optional, Any

# Adicionar projeto ao path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlmodel import SQLModel, select
from app.db.session import AsyncSessionLocal, engine
from app.services.catalog_service import sync_assets
from app.services.quote_service import fetch_and_enrich_asset
from app.models import Asset
from datetime import datetime

async def drop_all_tables():
    """Remove todas as tabelas do banco."""
    print("🗑️  Removendo todas as tabelas...")
    
    async with engine.begin() as conn:
        # Desabilitar foreign keys para MySQL
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        
        # Drop de todas as tabelas SQLModel
        await conn.run_sync(SQLModel.metadata.drop_all)
        
        # Reabilitar foreign keys
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    
    print("✅ Tabelas removidas com sucesso")
    return True

async def create_all_tables():
    """Cria todas as tabelas."""
    print("🏗️  Criando todas as tabelas...")
    
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    print("✅ Tabelas criadas com sucesso")
    return True

async def populate_catalog():
    """Popula o catálogo completo."""
    print("\n📊 Populando catálogo de ativos...")

    # Sincronizar apenas tipos suportados no plano gratuito
    asset_types = ["stock", "fund", "bdr"]
    total_stats = {"processed": 0, "inserted": 0, "updated": 0, "errors": 0, "pages": 0}

    async with AsyncSessionLocal() as session:
        for asset_type in asset_types:
            print(f"\n   🔄 Sincronizando {asset_type}...")

            try:
                stats = await sync_assets(session, asset_type, 200)
                print(
                    "      ✅ {t}: {p} processados, {i} inseridos, {u} atualizados".format(
                        t=asset_type.upper(), p=stats["processed"], i=stats["inserted"], u=stats["updated"]
                    )
                )

                for key in total_stats:
                    total_stats[key] += stats[key]

            except Exception as e:
                print(f"      ❌ Erro ao sincronizar {asset_type}: {e}")
                total_stats["errors"] += 1

    print("\n📈 Catálogo completo:")
    print(f"   Total processados: {total_stats['processed']}")
    print(f"   Total inseridos: {total_stats['inserted']}")
    print(f"   Total atualizados: {total_stats['updated']}")
    print(f"   Total erros: {total_stats['errors']}")

    return total_stats["errors"] == 0

async def populate_historical_data(range_period: str = "3mo", interval: str = "1d", max_assets: Optional[int] = None):
    """Popula dados históricos, dividendos e TTM para os ativos do catálogo."""
    async with AsyncSessionLocal() as session:
        try:
            tickers_result = await session.execute(
                select(Asset.ticker)
                .where(Asset.type.in_(["stock", "fund", "bdr"]))
                .order_by(Asset.ticker)
            )
            all_tickers = [row[0] for row in tickers_result.fetchall() if row[0]]

            if max_assets:
                all_tickers = all_tickers[:max_assets]

            print(f"\n📈 Enriquecendo dados históricos para {len(all_tickers)} ativos...")
            if not all_tickers:
                print("⚠️  Nenhum ativo encontrado no catálogo. Pulei o enriquecimento.")
                return True

            processed = 0
            errors = 0
            total_ohlcv = 0
            total_dividends = 0
            total_ttm = 0

            for ticker in all_tickers:
                try:
                    params: dict[str, Any] = {
                        "range": range_period,
                        "interval": interval,
                        "dividends": False,
                        "fundamental": False,
                        "modules": None,
                        "plan": "free",
                    }
                    result = await fetch_and_enrich_asset(
                        ticker,
                        range=params["range"],
                        interval=params["interval"],
                        dividends=params["dividends"],
                        fundamental=params["fundamental"],
                        modules=params["modules"],
                        plan=params["plan"],
                    )

                    total_ohlcv += result.get("ohlcv_rows_upserted", 0)
                    total_dividends += result.get("dividends_rows_upserted", 0)
                    if result.get("ttm_updated"):
                        total_ttm += 1

                    snapshot = result.get("snapshot", {})
                    missing_fields = [field for field in ("sector", "segment", "isin") if not snapshot.get(field)]
                    if missing_fields:
                        print(
                            f"   ⚠️  {ticker}: campos ausentes no snapshot: {', '.join(missing_fields)}"
                        )

                    processed += 1
                    if processed % 25 == 0:
                        print(
                            f"   -> Progresso: {processed}/{len(all_tickers)} | OHLCV {total_ohlcv} | Dividends {total_dividends} | TTM atualizados {total_ttm}"
                        )

                except Exception as e:
                    errors += 1
                    print(f"   ❌ {ticker}: erro durante enriquecimento ({e})")

                    await asyncio.sleep(0.5)

            print("\n✅ Enriquecimento concluído:")
            print(f"   Ativos processados: {processed}/{len(all_tickers)}")
            print(f"   Total OHLCV upsertados: {total_ohlcv}")
            print(f"   Total dividendos upsertados: {total_dividends}")
            print(f"   TTM atualizados: {total_ttm}")
            print(f"   Erros: {errors}")

            return errors == 0

        except Exception as e:
            print(f"❌ Erro no enriquecimento: {e}")
            return False

async def verify_population():
    """Verifica se a população foi bem-sucedida."""
    print("\n🔍 Verificando população do banco...")
    
    async with AsyncSessionLocal() as session:
        try:
            # Contar assets
            from app.models import Asset, QuoteOHLCV, ApiCall
            
            assets_count = await session.execute(text("SELECT COUNT(*) FROM assets"))
            assets_total = assets_count.scalar()
            
            ohlcv_count = await session.execute(text("SELECT COUNT(*) FROM quote_ohlcv"))
            ohlcv_total = ohlcv_count.scalar()
            
            api_calls_count = await session.execute(text("SELECT COUNT(*) FROM api_calls"))
            api_calls_total = api_calls_count.scalar()
            
            print(f"📊 Resumo da população:")
            print(f"   Assets: {assets_total}")
            print(f"   Registros OHLCV: {ohlcv_total}")
            print(f"   Chamadas API: {api_calls_total}")
            
            # Verificar tipos de assets
            types_query = await session.execute(text("SELECT type, COUNT(*) FROM assets WHERE type IS NOT NULL GROUP BY type"))
            types = types_query.fetchall()
            
            print(f"   Tipos de assets:")
            for asset_type, count in types:
                print(f"      {asset_type}: {count}")
            
            # Verificar tickers com dados OHLCV
            tickers_query = await session.execute(text("SELECT ticker, COUNT(*) FROM quote_ohlcv GROUP BY ticker ORDER BY COUNT(*) DESC LIMIT 10"))
            tickers = tickers_query.fetchall()
            
            print(f"   Top 10 tickers com dados:")
            for ticker, count in tickers:
                print(f"      {ticker}: {count} registros")
            
            return assets_total > 0 and ohlcv_total > 0
            
        except Exception as e:
            print(f"❌ Erro na verificação: {e}")
            return False

async def main():
    """Função principal."""
    print("🚀 POPULAÇÃO COMPLETA DO BANCO brapi_sqlmodel_boilerplate")
    print("=" * 60)
    print(f"📅 Data/Hora: {datetime.now().isoformat()}")
    async with AsyncSessionLocal() as session:
        asset_count_result = await session.execute(text("SELECT COUNT(*) FROM assets WHERE type IN ('stock', 'fund', 'etf', 'bdr')"))
        asset_count = asset_count_result.scalar() or 0
    print(f"🎯 Ativos cadastrados para histórico: {asset_count}")
    results = {
        "drop_tables": False,
        "create_tables": False,
        "populate_catalog": False,
        "populate_historical": False,
        "verify": False
    }
    
    results["drop_tables"] = await drop_all_tables()
    results["create_tables"] = await create_all_tables()
    results["populate_catalog"] = await populate_catalog()
    results["populate_historical"] = await populate_historical_data()
    results["verify"] = await verify_population()
    
    print("\n" + "=" * 60)
    print("📋 RESUMO DA POPULAÇÃO")
    print("=" * 60)
    
    for step, success in results.items():
        status = "✅ SUCESSO" if success else "❌ FALHOU"
        step_name = {
            "drop_tables": "Dropar tabelas",
            "create_tables": "Criar tabelas",
            "populate_catalog": "Popular catálogo",
            "populate_historical": "Popular dados históricos",
            "verify": "Verificar população"
        }.get(step, step)
        print(f"{step_name}: {status}")
    
    all_success = all(results.values())
    if all_success:
        print("\n🎉 População concluída com sucesso!")
    else:
        print("\n⚠️  Alguns passos falharam. Verifique os logs acima.")
    
    return all_success

if __name__ == "__main__":
    asyncio.run(main())
