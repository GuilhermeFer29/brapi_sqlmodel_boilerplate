#!/usr/bin/env python3
"""
Job para preencher dados históricos OHLCV dos ativos.

Uso:
python jobs/backfill_ohlcv.py --tickers "PETR4,VALE3,MGLU3" --range 3mo
python jobs/backfill_ohlcv.py --type stock --limit 50
python jobs/backfill_ohlcv.py --file tickers.txt
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
from sqlmodel import select
from app.db.session import AsyncSessionLocal, check_db
from app.services.ohlcv_service import backfill_ohlcv
from app.services.catalog_service import list_assets
from app.core.config import settings
from datetime import datetime

async def load_tickers_from_file(file_path: str) -> list[str]:
    """Carrega tickers de um arquivo de texto."""
    try:
        with open(file_path, 'r') as f:
            tickers = [line.strip().upper() for line in f if line.strip()]
        return tickers
    except FileNotFoundError:
        print(f"❌ Arquivo não encontrado: {file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erro ao ler arquivo: {e}")
        sys.exit(1)

async def get_tickers_by_type(session: AsyncSession, asset_type: str, limit: int = None) -> list[str]:
    """Obtém tickers do catálogo por tipo."""
    try:
        result = await list_assets(
            session=session,
            asset_type=asset_type,
            page=1,
            limit=limit or 1000,
            sort_by="ticker"
        )
        
        tickers = [asset["ticker"] for asset in result["assets"]]
        return tickers
        
    except Exception as e:
        print(f"❌ Erro ao obter tickers do tipo {asset_type}: {e}")
        return []

async def main():
    parser = argparse.ArgumentParser(description="Preencher dados históricos OHLCV")
    parser.add_argument("--tickers", type=str, 
                       help="Lista de tickers separados por vírgula")
    parser.add_argument("--file", type=str, 
                       help="Arquivo de texto com um ticker por linha")
    parser.add_argument("--type", choices=["stock", "fund", "bdr", "etf", "index"], 
                       help="Tipo de ativo para processar")
    parser.add_argument("--limit", type=int, default=50, 
                       help="Limite de tickers (default: 50)")
    parser.add_argument("--range", type=str, default="3mo", 
                       choices=["1mo", "3mo", "6mo", "1y", "2y"],
                       help="Período histórico (default: 3mo)")
    parser.add_argument("--interval", type=str, default="1d", 
                       choices=["1d", "1wk", "1mo"],
                       help="Intervalo dos dados (default: 1d)")
    parser.add_argument("--concurrency", type=int, default=3, 
                       help="Máximo de requisições simultâneas (default: 3)")
    
    args = parser.parse_args()
    
    print("🚀 Iniciando backfill OHLCV")
    print(f"📅 Data/Hora: {datetime.now().isoformat()}")
    print(f"📊 Período: {args.range}")
    print(f"⏱️  Intervalo: {args.interval}")
    print(f"🔄 Concorrência: {args.concurrency}")
    
    # Verificar conexão com banco
    print("🔍 Verificando conexão com banco...")
    if not await check_db():
        print("❌ Banco de dados não está disponível")
        sys.exit(1)
    print("✅ Banco de dados OK")
    
    # Determinar tickers para processar
    tickers = []
    
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        print(f"📋 Tickers informados: {len(tickers)}")
    elif args.file:
        tickers = await load_tickers_from_file(args.file)
        print(f"📁 Tickers do arquivo: {len(tickers)}")
    elif args.type:
        async with AsyncSessionLocal() as session:
            tickers = await get_tickers_by_type(session, args.type, args.limit)
        print(f"🏷️  Tickers do tipo {args.type}: {len(tickers)}")
    else:
        print("❌ Especifique --tickers, --file ou --type")
        parser.print_help()
        sys.exit(1)
    
    if not tickers:
        print("❌ Nenhum ticker encontrado para processar")
        sys.exit(1)
    
    print(f"📈 Processando {len(tickers)} tickers:")
    print(f"   Exemplos: {', '.join(tickers[:5])}{'...' if len(tickers) > 5 else ''}")
    
    # Confirmar operação
    if len(tickers) > 100:
        print(f"⚠️  Atenção: {len(tickers)} tickers podem consumir muitas requisições da API")
        response = input("Continuar? (y/N): ")
        if response.lower() != 'y':
            print("❌ Operação cancelada")
            sys.exit(0)
    
    # Executar backfill
    print(f"\n🔄 Iniciando backfill...")
    start_time = datetime.now()
    
    async with AsyncSessionLocal() as session:
        try:
            stats = await backfill_ohlcv(
                session=session,
                tickers=tickers,
                range=args.range,
                interval=args.interval,
                max_concurrency=args.concurrency
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Resultados
            print(f"\n✅ Backfill concluído em {duration:.1f}s")
            print(f"📊 ESTATÍSTICAS:")
            print(f"   Solicitados: {stats['total_requested']}")
            print(f"   Processados: {stats['processed']}")
            print(f"   Inseridos: {stats['inserted']}")
            print(f"   Atualizados: {stats['updated']}")
            print(f"   Erros: {stats['errors']}")
            
            if stats['processed'] > 0:
                print(f"   Média por ticker: {stats['inserted'] + stats['updated']:.1f} registros")
                print(f"   Velocidade: {stats['processed']/duration:.2f} tickers/s")
            
            if stats["errors"] > 0:
                print(f"\n⚠️  {stats['errors']} erros ocorreram")
                sys.exit(1)
            else:
                print(f"\n🎉 Backfill concluído com sucesso!")
                
        except KeyboardInterrupt:
            print(f"\n❌ Operação interrompida pelo usuário")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Erro no backfill: {e}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
