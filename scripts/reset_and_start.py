#!/usr/bin/env python3
"""
Script para resetar e iniciar todo o ambiente do zero.
Este script:
1. Para e remove containers Docker
2. Remove volumes e dados
3. Reconstrói e inicia containers
4. Aguarda serviços estarem prontos
5. Popula o banco com todos os dados
"""

import asyncio
import subprocess
import sys
import time
from pathlib import Path

def run_command(cmd, description, capture_output=True):
    """Executa comando shell com tratamento de erro."""
    print(f"🔄 {description}...")
    
    try:
        if capture_output:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ Erro: {result.stderr}")
                return False
        else:
            result = subprocess.run(cmd, shell=True)
            if result.returncode != 0:
                print(f"❌ Erro no comando")
                return False
        
        print(f"✅ {description} concluído")
        return True
        
    except Exception as e:
        print(f"❌ Erro executando {description}: {e}")
        return False

async def wait_for_api():
    """Aguarda a API estar disponível."""
    print("🔍 Aguardando API ficar disponível...")
    
    for attempt in range(60):
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get("http://localhost:8000/health")
                if response.status_code == 200:
                    print("✅ API está disponível!")
                    return True
        except:
            pass
        
        print(f"   Tentativa {attempt + 1}/60...")
        await asyncio.sleep(2)
    
    print("❌ API não ficou disponível a tempo")
    return False

async def main():
    """Função principal."""
    print("🚀 RESET COMPLETO E INICIALIZAÇÃO DO AMBIENTE")
    print("=" * 60)
    
    # Mudar para diretório do projeto
    project_root = Path(__file__).parent.parent
    import os
    os.chdir(project_root)
    print(f"📁 Diretório do projeto: {project_root}")
    
    # Passos do reset
    steps = [
        ("docker-compose down -v", "Parar e remover containers"),
        ("docker system prune -f", "Limpar sistema Docker"),
        ("docker-compose build --no-cache", "Reconstruir imagens"),
        ("docker-compose up -d", "Iniciar todos os serviços"),
    ]
    
    print("\n🔄 LIMPANDO E RESETANDO AMBIENTE")
    
    for cmd, description in steps:
        if not run_command(cmd, description):
            print(f"❌ Falha em: {description}")
            sys.exit(1)
    
    # Aguardar serviços subirem
    print("\n⏳ Aguardando serviços iniciarem...")
    await asyncio.sleep(10)
    
    # Verificar se containers estão rodando
    print("\n🔍 Verificando status dos containers...")
    run_command("docker-compose ps", "Status dos containers", capture_output=False)
    
    # Aguardar API
    if not await wait_for_api():
        print("❌ API não ficou disponível")
        sys.exit(1)
    
    # Popular banco
    print("\n📊 POPULANDO BANCO DE DADOS")
    
    populate_cmd = f"{sys.executable} scripts/populate_all.py"
    if not run_command(populate_cmd, "Executar população completa", capture_output=False):
        print("❌ Falha na população do banco")
        sys.exit(1)
    
    # Verificação final
    print("\n🎉 AMBIENTE INICIADO E POPULADO!")
    print("=" * 60)
    
    print("📊 Status final:")
    run_command("docker-compose ps", "Containers rodando")
    
    print("\n🔗 Endpoints disponíveis:")
    print("   📡 API: http://localhost:8000")
    print("   📚 Docs: http://localhost:8000/docs")
    print("   ❤️  Health: http://localhost:8000/health")
    print("   🗄️  MySQL: localhost:3310")
    print("   🔴 Redis: localhost:6379")
    print("   🌐 Streamlit: http://localhost:8501")
    
    print("\n🧪 Testes rápidos:")
    print("   curl http://localhost:8000/health")
    print("   curl http://localhost:8000/api/catalog/assets?type=stock&limit=5")
    print("   curl http://localhost:8000/api/ohlcv?ticker=PETR4&period=1mo")
    
    print("\n🎯 Próximos passos:")
    print("   1. Explore a API em http://localhost:8000/docs")
    print("   2. Execute jobs adicionais se necessário:")
    print("      python jobs/sync_catalog.py --all")
    print("      python jobs/backfill_ohlcv.py --tickers 'PETR4,VALE3'")
    print("   3. Monitore via tabela api_calls no banco")

if __name__ == "__main__":
    asyncio.run(main())
