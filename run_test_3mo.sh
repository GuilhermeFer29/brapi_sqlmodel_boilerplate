#!/bin/bash
# Script para executar o teste de enriquecimento 3 meses dentro do container Docker

echo "🚀 Executando teste de enriquecimento 3 meses (PETR4)..."
echo "=========================================="

docker compose exec api python tests/test_single_asset_3mo.py

echo ""
echo "✅ Teste concluído!"
