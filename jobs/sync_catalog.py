#!/usr/bin/env python3
"""
Job para sincronizar catálogo de ativos da brapi.

Uso:
python jobs/sync_catalog.py [--type stock] [--limit 100]

Tipos disponíveis: stock, fund, bdr, etf, index
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path

# Adicionar projeto ao path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal, check_db
from app.services.catalog_service import sync_assets
from app.core.config import settings
from datetime import datetime

async def main():
    parser = argparse.ArgumentParser(description="Sincronizar catálogo de ativos")
    parser.add_argument("--type", choices=["stock", "fund", "bdr", "etf", "index"], 
                       help="Tipo de ativo para sincronizar")
    parser.add_argument("--limit", type=int, default=100, 
                       help="Limite de ativos por página (default: 100)")
    parser.add_argument("--all", action="store_true", 
                       help="Sincronizar todos os tipos")
    
    args = parser.parse_args()
    
    print("🚀 Iniciando sincronização do catálogo brapi")
    print(f"📅 Data/Hora: {datetime.now().isoformat()}")
    
    # Verificar conexão com banco
    print("🔍 Verificando conexão com banco...")
    if not await check_db():
        print("❌ Banco de dados não está disponível")
        sys.exit(1)
    print("✅ Banco de dados OK")
    
    # Determinar tipos para sincronizar
    if args.all:
        types = ["stock", "fund", "bdr", "etf", "index"]
    elif args.type:
        types = [args.type]
    else:
        # Default: sincronizar ações
        types = ["stock"]
    
    print(f"📊 Tipos a sincronizar: {', '.join(types)}")
    print(f"⚙️  Limite por página: {args.limit}")
    
    # Sincronizar cada tipo
    total_stats = {
        "processed": 0,
        "inserted": 0,
        "updated": 0,
        "errors": 0,
        "pages": 0
    }
    
    async with AsyncSessionLocal() as session:
        for asset_type in types:
            print(f"\n🔄 Sincronizando {asset_type}...")
            
            try:
                stats = await sync_assets(session, asset_type, args.limit)
                
                print(f"✅ {asset_type}:")
                print(f"   Processados: {stats['processed']}")
                print(f"   Inseridos: {stats['inserted']}")
                print(f"   Atualizados: {stats['updated']}")
                print(f"   Erros: {stats['errors']}")
                print(f"   Páginas: {stats['pages']}")
                
                # Acumular estatísticas
                for key in total_stats:
                    total_stats[key] += stats[key]
                    
            except Exception as e:
                print(f"❌ Erro ao sincronizar {asset_type}: {e}")
                total_stats["errors"] += 1
    
    # Resumo final
    print(f"\n📈 RESUMO DA SINCRONIZAÇÃO")
    print(f"   Total processados: {total_stats['processed']}")
    print(f"   Total inseridos: {total_stats['inserted']}")
    print(f"   Total atualizados: {total_stats['updated']}")
    print(f"   Total erros: {total_stats['errors']}")
    print(f"   Total páginas: {total_stats['pages']}")
    
    if total_stats["errors"] > 0:
        print(f"\n⚠️  Atenção: {total_stats['errors']} erros ocorreram")
        sys.exit(1)
    else:
        print(f"\n🎉 Sincronização concluída com sucesso!")

if __name__ == "__main__":
    asyncio.run(main())
