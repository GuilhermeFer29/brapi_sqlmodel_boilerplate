#!/usr/bin/env python3
"""
Job de atualização diária de dados.

Uso:
python jobs/update_daily.py [--tickers "PETR4,VALE3"] [--concurrency 3]
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
from sqlmodel import select, func
from app.db.session import AsyncSessionLocal, check_db
from app.services.ohlcv_service import update_ohlcv_latest
from app.core.config import settings
from datetime import datetime, timedelta

async def get_recent_tickers(session: AsyncSession, days: int = 7) -> list[str]:
    """
    Obtém tickers que tiveram atividade nos últimos N dias.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    try:
        # Buscar tickers distintos com dados recentes
        query = (
            select(func.distinct(QuoteOHLCV.ticker))
            .where(QuoteOHLCV.date >= cutoff_date)
            .order_by(QuoteOHLCV.ticker)
        )
        
        result = await session.execute(query)
        tickers = result.scalars().all()
        
        return list(tickers)
        
    except Exception as e:
        print(f"❌ Erro ao buscar tickers recentes: {e}")
        return []

async def get_all_tickers(session: AsyncSession) -> list[str]:
    """
    Obtém todos os tickers com dados OHLCV.
    """
    try:
        query = select(func.distinct(QuoteOHLCV.ticker)).order_by(QuoteOHLCV.ticker)
        result = await session.execute(query)
        tickers = result.scalars().all()
        return list(tickers)
    except Exception as e:
        print(f"❌ Erro ao buscar todos os tickers: {e}")
        return []

async def main():
    parser = argparse.ArgumentParser(description="Atualização diária de dados")
    parser.add_argument("--tickers", type=str, 
                       help="Lista específica de tickers separados por vírgula")
    parser.add_argument("--recent", action="store_true", 
                       help="Atualizar apenas tickers com atividade recente (7 dias)")
    parser.add_argument("--concurrency", type=int, default=3, 
                       help="Máximo de requisições simultâneas (default: 3)")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Apenas mostrar o que seria atualizado")
    
    args = parser.parse_args()
    
    print("🔄 Job de atualização diária")
    print(f"📅 Data/Hora: {datetime.now().isoformat()}")
    print(f"⚙️  Concorrência: {args.concurrency}")
    
    # Verificar conexão com banco
    print("🔍 Verificando conexão com banco...")
    if not await check_db():
        print("❌ Banco de dados não está disponível")
        sys.exit(1)
    print("✅ Banco de dados OK")
    
    # Determinar tickers para atualizar
    tickers = []
    
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        print(f"📋 Tickers informados: {len(tickers)}")
    else:
        async with AsyncSessionLocal() as session:
            if args.recent:
                tickers = await get_recent_tickers(session)
                print(f"📈 Tickers recentes (7 dias): {len(tickers)}")
            else:
                tickers = await get_all_tickers(session)
                print(f"📊 Todos os tickers: {len(tickers)}")
    
    if not tickers:
        print("❌ Nenhum ticker encontrado para atualizar")
        sys.exit(1)
    
    print(f"📝 Amostra: {', '.join(tickers[:10])}{'...' if len(tickers) > 10 else ''}")
    
    # Dry run
    if args.dry_run:
        print(f"\n🔍 DRY RUN: Atualizaria {len(tickers)} tickers")
        print("   Nenhuma requisição será feita à API")
        return
    
    # Confirmar se muitos tickers
    if len(tickers) > 200:
        print(f"⚠️  Atenção: {len(tickers)} tickers podem consumir muitas requisições")
        response = input("Continuar? (y/N): ")
        if response.lower() != 'y':
            print("❌ Operação cancelada")
            sys.exit(0)
    
    # Executar atualização
    print(f"\n🔄 Iniciando atualização...")
    start_time = datetime.now()
    
    async with AsyncSessionLocal() as session:
        try:
            stats = await update_ohlcv_latest(
                session=session,
                tickers=tickers,
                max_concurrency=args.concurrency
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Resultados
            print(f"\n✅ Atualização concluída em {duration:.1f}s")
            print(f"📊 ESTATÍSTICAS:")
            print(f"   Solicitados: {stats['total_requested']}")
            print(f"   Processados: {stats['processed']}")
            print(f"   Inseridos: {stats['inserted']}")
            print(f"   Atualizados: {stats['updated']}")
            print(f"   Erros: {stats['errors']}")
            
            if stats['processed'] > 0:
                print(f"   Velocidade: {stats['processed']/duration:.2f} tickers/s")
            
            # Taxa de sucesso
            if stats['total_requested'] > 0:
                success_rate = (stats['processed'] - stats['errors']) / stats['total_requested'] * 100
                print(f"   Taxa de sucesso: {success_rate:.1f}%")
            
            if stats["errors"] > 0:
                print(f"\n⚠️  {stats['errors']} erros ocorreram")
                sys.exit(1)
            else:
                print(f"\n🎉 Atualização concluída com sucesso!")
                
        except KeyboardInterrupt:
            print(f"\n❌ Operação interrompida pelo usuário")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Erro na atualização: {e}")
            sys.exit(1)

# Import necessário para a função
from app.models import QuoteOHLCV

if __name__ == "__main__":
    asyncio.run(main())
