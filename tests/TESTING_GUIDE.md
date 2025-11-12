# Guia de Testes

## Visão Geral

O projeto possui dois tipos de testes para `test_single_asset_3mo.py`:

### 1. ✅ Teste Standalone (Recomendado para desenvolvimento)
```bash
./run_test_3mo.sh
```

**Vantagens:**
- Controle total do event loop
- Output mais limpo e colorido
- Execução mais rápida
- Ideal para debugging

**Como funciona:**
- Usa `asyncio.run()` diretamente
- Gerencia seu próprio event loop
- Não interfere com outros testes

### 2. 🧪 Teste via pytest (Para CI/CD)
```bash
./run_pytest_3mo.sh
# ou
docker compose exec api pytest tests/test_single_asset_3mo.py -v
```

**Vantagens:**
- Integração com suite de testes
- Reports estruturados
- Compatível com CI/CD pipelines

**Como funciona:**
- Usa `pytest-asyncio` para gerenciar event loop
- Compartilha recursos entre testes
- Usa fixtures de cleanup automático

## Status Atual dos Testes

### ✅ Testes Funcionando (14 passed)
- `test_single_asset_3mo.py` - **standalone apenas** ✅
- Testes de parsing de timestamp
- Testes de extração OHLCV
- Alguns testes de cache

### ⚠️ Testes com Problemas (15 failed)
Os testes antigos precisam de atualização após refatorações:

1. **`test_catalog_service.py`** (9 falhas)
   - `_normalize_asset_type` mudou comportamento
   - Mocks async não awaitados
   - `httpx` removido do módulo

2. **`test_ohlcv_service.py`** (5 falhas)
   - Mocks async não awaitados
   - Session.execute não sendo awaited

3. **`test_single_asset_3mo.py` via pytest** (1 falha)
   - ⚠️ Event loop fechado prematuramente
   - **Solução**: Use `./run_test_3mo.sh` em vez de pytest por enquanto

## Como Rodar Testes

### Teste Específico 3mo (Standalone) ✅
```bash
./run_test_3mo.sh
```

### Teste Específico 3mo (Pytest) ⚠️
```bash
./run_pytest_3mo.sh
```

### Suite Completa
```bash
docker compose exec api pytest
```

### Com Coverage
```bash
docker compose exec api pytest --cov=app --cov-report=html
```

### Apenas Testes Funcionando
```bash
docker compose exec api pytest -k "not catalog_service and not test_single_asset_3mo"
```

## Troubleshooting

### Erro: "Event loop is closed"
**Causa**: AsyncLimiter reutilizado entre event loops  
**Solução**: Use `./run_test_3mo.sh` standalone ou aguarde fix do conftest.py

### Erro: "AsyncLimiter instance is being re-used"
**Causa**: Limiter global não está sendo limpo entre testes  
**Status**: ✅ Fixado no `conftest.py` com `cleanup_resources` fixture

### Erro: "coroutine object has no attribute 'ticker'"
**Causa**: Mock async não está sendo awaited  
**Solução**: Testes antigos precisam de atualização (fora do escopo atual)

### Erro: "module 'catalog_service' has no attribute 'httpx'"
**Causa**: Refatoração removeu `httpx` do módulo  
**Solução**: Testes antigos precisam usar novos imports (fora do escopo atual)

## Estrutura de Testes

```
tests/
├── test_single_asset_3mo.py       # ✅ Novo teste 3mo (standalone OK, pytest WIP)
├── test_catalog_service.py        # ⚠️ Precisa atualização
├── test_ohlcv_service.py          # ⚠️ Precisa atualização  
├── test_crypto_service.py         # Status desconhecido
├── test_currency_service.py       # Status desconhecido
└── README_3MO_TEST.md            # Documentação do teste 3mo
```

## Fixtures Disponíveis

### `cleanup_resources` (autouse)
Limpa recursos globais entre testes:
- HTTP client singleton
- AsyncLimiter instances
- Event loops

**Uso:** Automático, não precisa declarar

## Próximas Melhorias

1. ✅ ~~Criar teste standalone 3mo~~
2. ✅ ~~Adicionar logging e validações~~
3. ✅ ~~Implementar idempotência~~
4. ⚠️ Corrigir event loop no pytest (em andamento)
5. 🔄 Atualizar testes antigos (backlog)
6. 📋 Adicionar testes de integração E2E
7. 📋 Coverage >= 80%

## Comandos Úteis

```bash
# Rodar apenas testes async
docker compose exec api pytest -k "asyncio"

# Rodar com verbose + stacktrace
docker compose exec api pytest -vv --tb=long

# Rodar e parar no primeiro erro
docker compose exec api pytest -x

# Rodar em paralelo (requer pytest-xdist)
docker compose exec api pytest -n auto

# Limpar cache pytest
docker compose exec api pytest --cache-clear
```

## Referências

- [pytest-asyncio docs](https://pytest-asyncio.readthedocs.io/)
- [AsyncLimiter docs](https://aiolimiter.readthedocs.io/)
- [httpx testing](https://www.python-httpx.org/advanced/#testing)
