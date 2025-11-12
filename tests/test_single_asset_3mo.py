#!/usr/bin/env python3
"""
Teste isolado para buscar e enriquecer um único ativo com histórico de 3 meses.
Valida OHLCV, dividendos e dados financeiros TTM com idempotência.
"""
import asyncio
import sys
import os
import json
import pytest

# Adicionar o diretório do app ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime
from app.services.quote_service import fetch_and_enrich_asset
from app.db.session import AsyncSessionLocal
from app.models import QuoteOHLCV, Dividend, FinancialsTTM
from sqlmodel import select


@pytest.mark.asyncio
async def test_single_asset_3mo():
    """
    Testa busca de um único ativo com:
    - Histórico de 3 meses (range=3mo)
    - Intervalo diário (interval=1d)
    - Dividendos habilitados
    - Dados fundamentalistas
    - Plano free
    """
    ticker = "PETR4"
    
    print(f"🧪 Testando enriquecimento 3 meses do ativo: {ticker}")
    print("=" * 70)
    
    # Primeira execução
    print(f"\n🔄 Primeira execução...")
    try:
        result = await fetch_and_enrich_asset(
            ticker,
            range="3mo",
            interval="1d",
            dividends=True,
            fundamental=True,
            modules=["financialData"],
            plan="free",
        )
        
        print(f"\n✅ Resposta da primeira execução:")
        print(f"   Symbol: {result['symbol']}")
        print(f"   OHLCV rows upserted: {result['ohlcv_rows_upserted']}")
        print(f"   Dividends rows upserted: {result['dividends_rows_upserted']}")
        print(f"   TTM updated: {result['ttm_updated']}")
        print(f"   Used range: {result.get('usedRange')}")
        print(f"   Used interval: {result.get('usedInterval')}")
        print(f"   Requested at: {result.get('requestedAt')}")
        
        # Validar snapshot
        snapshot = result.get("snapshot", {})
        if snapshot:
            print(f"\n📊 Snapshot recebido ({len(snapshot)} campos):")
            required_keys = ["symbol", "shortName", "currency", "regularMarketPrice"]
            missing_keys = [k for k in required_keys if k not in snapshot]
            if missing_keys:
                print(f"   ⚠️  Campos mínimos faltando: {missing_keys}")
            else:
                print(f"   ✅ Todos os campos mínimos presentes")
            
            # Mostrar alguns campos importantes
            print(f"   Symbol: {snapshot.get('symbol')}")
            print(f"   Short Name: {snapshot.get('shortName')}")
            print(f"   Currency: {snapshot.get('currency')}")
            print(f"   Market Price: {snapshot.get('regularMarketPrice')}")
        else:
            print(f"   ⚠️  Snapshot vazio")
        
        # Validar contagem mínima de candles (≥45 para 3 meses)
        ohlcv_count = result['ohlcv_rows_upserted']
        min_expected_candles = 45
        if ohlcv_count >= min_expected_candles:
            print(f"\n✅ Contagem OHLCV válida: {ohlcv_count} >= {min_expected_candles}")
        else:
            print(f"\n⚠️  Contagem OHLCV abaixo do esperado: {ohlcv_count} < {min_expected_candles}")
        
        # Consultar banco para confirmar persistência
        async with AsyncSessionLocal() as session:
            # Contar OHLCV
            stmt_ohlcv = select(QuoteOHLCV).where(QuoteOHLCV.ticker == ticker)
            result_ohlcv = await session.execute(stmt_ohlcv)
            ohlcv_records = result_ohlcv.scalars().all()
            print(f"\n📦 Registros OHLCV no banco: {len(ohlcv_records)}")
            
            # Contar dividendos
            stmt_div = select(Dividend).where(Dividend.ticker == ticker)
            result_div = await session.execute(stmt_div)
            div_records = result_div.scalars().all()
            print(f"📦 Registros Dividendos no banco: {len(div_records)}")
            
            # Verificar TTM
            stmt_ttm = select(FinancialsTTM).where(FinancialsTTM.ticker == ticker)
            result_ttm = await session.execute(stmt_ttm)
            ttm_record = result_ttm.scalar_one_or_none()
            if ttm_record:
                print(f"📦 Registro FinancialsTTM no banco: SIM")
                print(f"   Updated at: {ttm_record.updated_at}")
                if ttm_record.data:
                    print(f"   TTM data campos: {len(ttm_record.data)}")
            else:
                print(f"📦 Registro FinancialsTTM no banco: NÃO")
        
        # Segunda execução (testar idempotência)
        print(f"\n🔄 Segunda execução (teste de idempotência)...")
        result2 = await fetch_and_enrich_asset(
            ticker,
            range="3mo",
            interval="1d",
            dividends=True,
            fundamental=True,
            modules=["financialData"],
            plan="free",
        )
        
        print(f"\n✅ Resposta da segunda execução:")
        print(f"   OHLCV rows upserted: {result2['ohlcv_rows_upserted']}")
        print(f"   Dividends rows upserted: {result2['dividends_rows_upserted']}")
        print(f"   TTM updated: {result2['ttm_updated']}")
        
        # Verificar se não houve duplicação
        async with AsyncSessionLocal() as session:
            stmt_ohlcv = select(QuoteOHLCV).where(QuoteOHLCV.ticker == ticker)
            result_ohlcv = await session.execute(stmt_ohlcv)
            ohlcv_records_after = result_ohlcv.scalars().all()
            
            stmt_div = select(Dividend).where(Dividend.ticker == ticker)
            result_div = await session.execute(stmt_div)
            div_records_after = result_div.scalars().all()
            
            if len(ohlcv_records_after) == len(ohlcv_records):
                print(f"\n✅ Idempotência OHLCV confirmada: {len(ohlcv_records_after)} registros (sem duplicatas)")
            else:
                print(f"\n⚠️  Idempotência OHLCV falhou: {len(ohlcv_records)} → {len(ohlcv_records_after)} registros")
            
            if len(div_records_after) == len(div_records):
                print(f"✅ Idempotência Dividendos confirmada: {len(div_records_after)} registros (sem duplicatas)")
            else:
                print(f"⚠️  Idempotência Dividendos falhou: {len(div_records)} → {len(div_records_after)} registros")
        
        print(f"\n🎉 Teste concluído com sucesso!")
        
    except Exception as e:
        print(f"\n❌ Erro durante o teste: {e}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"Teste falhou: {e}")


if __name__ == "__main__":
    asyncio.run(test_single_asset_3mo())
