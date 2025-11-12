#!/usr/bin/env python3
"""
Teste isolado para buscar e enriquecer um único ativo da Brapi API.
"""
import asyncio
import sys
import os
import json

# Adicionar o diretório do app ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from datetime import datetime
from app.services.brapi_client import BrapiClient
from app.services.catalog_service import _enrich_asset, _needs_enrichment
from app.models.catalog import Asset
from app.services.utils.json_serializer import normalize_for_json

def utcnow():
    return datetime.now()

async def test_single_asset():
    """Testa busca de um único ativo com enriquecimento."""
    ticker = "PETR4"
    
    print(f"🧪 Testando enriquecimento do ativo: {ticker}")
    print("=" * 50)
    
    # Criar ativo básico
    asset = Asset(
        ticker=ticker,
        name=None,
        type=None,
        sector=None,
        segment=None,
        isin=None,
        logo_url=None,
        raw=None
    )
    
    print(f"📊 Estado inicial do ativo:")
    print(f"   Ticker: {asset.ticker}")
    print(f"   Name: {asset.name}")
    print(f"   Type: {asset.type}")
    print(f"   Sector: {asset.sector}")
    print(f"   Segment: {asset.segment}")
    print(f"   ISIN: {asset.isin}")
    print(f"   Logo URL: {asset.logo_url}")
    print(f"   Precisa enriquecimento? {_needs_enrichment(asset)}")
    
    # Criar cliente e enriquecer
    client = BrapiClient()
    
    try:
        print(f"\n🔄 Buscando dados da API...")
        
        # Teste direto da API primeiro
        response = await client.quote([ticker], {"fundamental": "true"})
        print(f"📦 Resposta da API (chaves): {list(response.keys())}")
        
        items = (response.get("results") or response.get("stocks") or []) if isinstance(response, dict) else []
        if items:
            info = items[0]
            print(f"📦 Primeiro item (chaves): {list(info.keys())}")
            print(f"📦 Logo URL: {info.get('logourl')}")
            print(f"📦 Market Cap: {info.get('marketCap')}")
        
        await _enrich_asset(asset, client)
        
        print(f"\n✅ Estado após enriquecimento:")
        print(f"   Ticker: {asset.ticker}")
        print(f"   Name: {asset.name}")
        print(f"   Type: {asset.type}")
        print(f"   Sector: {asset.sector}")
        print(f"   Segment: {asset.segment}")
        print(f"   ISIN: {asset.isin}")
        print(f"   Logo URL: {asset.logo_url}")
        print(f"   Precisa enriquecimento? {_needs_enrichment(asset)}")
        
        # Mostrar dados brutos salvos
        if asset.raw and isinstance(asset.raw, dict):
            print(f"\n📦 Dados brutos salvos ({len(asset.raw)} campos):")
            # Converter datetime para string para exibição
            raw_display = {}
            for key, value in asset.raw.items():
                if hasattr(value, 'isoformat'):
                    raw_display[key] = value.isoformat()
                else:
                    raw_display[key] = value
            print(json.dumps(raw_display, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ Erro durante o teste: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_single_asset())
