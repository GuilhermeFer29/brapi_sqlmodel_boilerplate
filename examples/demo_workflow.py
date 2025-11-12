#!/usr/bin/env python3
"""
Demonstração do fluxo completo de uso da API brapi_sqlmodel_boilerplate.

Este script mostra:
1. Sincronização do catálogo
2. Backfill de dados históricos
3. Consulta via API REST
4. Verificação de observabilidade

Execute após iniciar a API com `docker-compose up -d`
"""

import asyncio
import httpx
import time
from datetime import datetime, timedelta

# Configuração
API_BASE = "http://localhost:8000"
DEMO_TICKERS = ["PETR4", "VALE3", "MGLU3", "ITUB4"]  # 4 ações gratuitas


async def wait_for_api():
    """Aguarda a API estar disponível."""
    print("🔍 Aguardando API ficar disponível...")
    
    for attempt in range(30):
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{API_BASE}/health")
                if response.status_code == 200:
                    print("✅ API está disponível!")
                    return True
        except:
            pass
        
        print(f"   Tentativa {attempt + 1}/30...")
        await asyncio.sleep(2)
    
    print("❌ API não ficou disponível a tempo")
    return False


async def sync_catalog():
    """Sincroniza catálogo de ativos."""
    print("\n📊 Sincronizando catálogo de ações...")
    
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(f"{API_BASE}/api/catalog/sync/stock?limit=50")
        
        if response.status_code == 200:
            data = response.json()
            stats = data["stats"]
            print(f"✅ Catálogo sincronizado:")
            print(f"   Processados: {stats['processed']}")
            print(f"   Inseridos: {stats['inserted']}")
            print(f"   Erros: {stats['errors']}")
            return True
        else:
            print(f"❌ Erro na sincronização: {response.status_code}")
            print(response.text)
            return False


async def backfill_historical_data():
    """Preenche dados históricos OHLCV."""
    print(f"\n📈 Preenchendo dados históricos para {len(DEMO_TICKERS)} tickers...")
    
    tickers_str = ",".join(DEMO_TICKERS)
    
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{API_BASE}/api/ohlcv/backfill?"
            f"tickers={tickers_str}&range=3mo&concurrency=2"
        )
        
        if response.status_code == 200:
            data = response.json()
            stats = data["stats"]
            print(f"✅ Dados históricos preenchidos:")
            print(f"   Processados: {stats['processed']}")
            print(f"   Inseridos: {stats['inserted']}")
            print(f"   Atualizados: {stats['updated']}")
            print(f"   Erros: {stats['errors']}")
            return True
        else:
            print(f"❌ Erro no backfill: {response.status_code}")
            print(response.text)
            return False


async def query_catalog():
    """Consulta o catálogo via API."""
    print("\n🔍 Consultando catálogo de ativos...")
    
    async with httpx.AsyncClient(timeout=10) as client:
        # Listar ações
        response = await client.get(f"{API_BASE}/api/catalog/assets?type=stock&limit=10")
        
        if response.status_code == 200:
            data = response.json()
            assets = data["assets"]
            print(f"✅ Encontrados {len(assets)} ativos:")
            
            for asset in assets[:3]:  # Mostrar 3 exemplos
                print(f"   {asset['ticker']}: {asset['name']} ({asset['sector']})")
            
            return True
        else:
            print(f"❌ Erro na consulta: {response.status_code}")
            return False


async def query_ohlcv():
    """Consulta dados OHLCV via API."""
    print("\n📊 Consultando dados OHLCV...")
    
    for ticker in DEMO_TICKERS[:2]:  # Testar 2 tickers
        print(f"\n   📈 {ticker}:")
        
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{API_BASE}/api/ohlcv?ticker={ticker}&period=1mo")
            
            if response.status_code == 200:
                data = response.json()
                data_points = data["data"]
                
                if data_points:
                    latest = data_points[-1]  # Mais recente
                    print(f"      Último preço: R$ {latest['close']:.2f}")
                    print(f"      Data pontos: {len(data_points)}")
                    print(f"      Período: {data_points[0]['date'][:10]} a {data_points[-1]['date'][:10]}")
                else:
                    print("      Nenhum dado encontrado")
            else:
                print(f"      ❌ Erro: {response.status_code}")


async def check_observability():
    """Verifica dados de observabilidade."""
    print("\n📋 Verificando observabilidade...")
    
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{API_BASE}/health")
        
        if response.status_code == 200:
            health = response.json()
            print(f"✅ Status do sistema:")
            print(f"   Banco de dados: {health['db']}")
            print(f"   Cache Redis: {health['redis']}")
        
        # Nota: Em produção, você poderia consultar a tabela api_calls
        # via um endpoint admin ou diretamente no banco


async def performance_test():
    """Teste simples de performance."""
    print("\n⚡ Teste de performance (cache)...")
    
    # Primeira chamada (sem cache)
    start_time = time.time()
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{API_BASE}/api/catalog/assets?type=stock&limit=20")
    first_call = time.time() - start_time
    
    # Segunda chamada (com cache)
    start_time = time.time()
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{API_BASE}/api/catalog/assets?type=stock&limit=20")
    second_call = time.time() - start_time
    
    print(f"📊 Resultados:")
    print(f"   Primeira chamada: {first_call:.3f}s")
    print(f"   Segunda chamada: {second_call:.3f}s")
    
    if second_call < first_call:
        speedup = first_call / second_call
        print(f"   🚀 Cache acelerou em {speedup:.1f}x")
    else:
        print("   ⚠️  Cache pode não estar funcionando")


async def main():
    """Função principal da demonstração."""
    print("🚀 DEMO: brapi_sqlmodel_boilerplate")
    print("=" * 50)
    print(f"📅 Data/Hora: {datetime.now().isoformat()}")
    print(f"🎯 Tickers demonstração: {', '.join(DEMO_TICKERS)}")
    
    # Aguardar API
    if not await wait_for_api():
        return
    
    # Fluxo completo
    steps = [
        ("Sincronizar catálogo", sync_catalog),
        ("Preencher dados históricos", backfill_historical_data),
        ("Consultar catálogo", query_catalog),
        ("Consultar OHLCV", query_ohlcv),
        ("Verificar observabilidade", check_observability),
        ("Teste de performance", performance_test),
    ]
    
    results = []
    
    for step_name, step_func in steps:
        try:
            result = await step_func()
            results.append((step_name, result))
        except Exception as e:
            print(f"❌ Erro em {step_name}: {e}")
            results.append((step_name, False))
    
    # Resumo final
    print("\n" + "=" * 50)
    print("📈 RESUMO DA DEMONSTRAÇÃO")
    
    for step_name, success in results:
        status = "✅" if success else "❌"
        print(f"   {status} {step_name}")
    
    success_count = sum(1 for _, success in results if success)
    print(f"\n🎉 Sucesso: {success_count}/{len(results)} etapas concluídas")
    
    if success_count == len(results):
        print("\n✨ Demonstração concluída com sucesso!")
        print("\n🔗 Próximos passos:")
        print("   - Explore os outros endpoints da API")
        print("   - Configure seus próprios tickers em jobs/tickers_example.txt")
        print("   - Agende os jobs ETL para execução automática")
        print("   - Monitore via tabela api_calls no banco")
    else:
        print(f"\n⚠️  {len(results) - success_count} etapas falharam. Verifique os logs.")


if __name__ == "__main__":
    asyncio.run(main())
