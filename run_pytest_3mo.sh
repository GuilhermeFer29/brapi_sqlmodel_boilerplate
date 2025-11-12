#!/bin/bash
# Script para executar apenas o teste test_single_asset_3mo.py via pytest

echo "🚀 Executando teste test_single_asset_3mo.py via pytest..."
echo "=========================================="

docker compose exec api pytest tests/test_single_asset_3mo.py -v

echo ""
echo "✅ Teste concluído!"
