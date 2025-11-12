# Teste de Enriquecimento 3 Meses

## Objetivo

Teste isolado para validar o processo completo de busca e persistência de dados de um ativo com histórico de 3 meses, incluindo:

- ✅ **OHLCV**: Dados históricos de preços (Open, High, Low, Close, Volume)
- ✅ **Dividendos**: Histórico de pagamentos de dividendos
- ✅ **TTM Financials**: Dados financeiros Trailing Twelve Months
- ✅ **Idempotência**: Garantia de que execuções repetidas não geram duplicatas

## Validações

### 1. Snapshot
- Retorna campos mínimos essenciais:
  - `symbol`, `shortName`, `longName`, `currency`
  - `regularMarketPrice`, `regularMarketPreviousClose`
  - `regularMarketChange`, `regularMarketChangePercent`
  - `regularMarketTime`, `regularMarketDayHigh`, `regularMarketDayLow`
  - `regularMarketVolume`, `marketCap`, `priceEarnings`

### 2. OHLCV
- Mínimo de **45 candles** para 3 meses (≈63 dias úteis)
- Validação de persistência no banco
- Teste de idempotência (sem duplicatas)

### 3. Dividendos
- Extração de dados de `dividendsData.cashDividends`
- Persistência com constraint único em `(ticker, ex_date)`
- Teste de idempotência

### 4. TTM Financials
- Extração de `financialData` quando módulo é solicitado
- Persistência em tabela `financials_ttm`
- Constraint único por `ticker`

## Como Executar

### Opção 1: Script Shell (Recomendado)
```bash
./run_test_3mo.sh
```

### Opção 2: Docker Compose Direto
```bash
docker compose exec api python tests/test_single_asset_3mo.py
```

### Opção 3: Ambiente Local
```bash
python tests/test_single_asset_3mo.py
```

## Output Esperado

```
🧪 Testando enriquecimento 3 meses do ativo: PETR4
======================================================================

🔄 Primeira execução...
📡 Buscando dados para PETR4 (range=3mo, interval=1d)...
📊 Dados extraídos: 63 candles OHLCV, 5 dividendos
💾 Persistido: 63 OHLCV, 5 dividendos, TTM=True

✅ Resposta da primeira execução:
   Symbol: PETR4
   OHLCV rows upserted: 63
   Dividends rows upserted: 5
   TTM updated: True
   Used range: 3mo
   Used interval: 1d
   Requested at: 2025-11-11T22:45:30.123456+00:00

📊 Snapshot recebido (14 campos):
   ✅ Todos os campos mínimos presentes
   Symbol: PETR4
   Short Name: PETROBRAS PN
   Currency: BRL
   Market Price: 38.50

✅ Contagem OHLCV válida: 63 >= 45

📦 Registros OHLCV no banco: 63
📦 Registros Dividendos no banco: 5
📦 Registro FinancialsTTM no banco: SIM
   Updated at: 2025-11-11 22:45:30.456789+00:00
   TTM data campos: 45

🔄 Segunda execução (teste de idempotência)...
📡 Buscando dados para PETR4 (range=3mo, interval=1d)...
📊 Dados extraídos: 63 candles OHLCV, 5 dividendos
💾 Persistido: 63 OHLCV, 5 dividendos, TTM=True

✅ Resposta da segunda execução:
   OHLCV rows upserted: 63
   Dividends rows upserted: 5
   TTM updated: True

✅ Idempotência OHLCV confirmada: 63 registros (sem duplicatas)
✅ Idempotência Dividendos confirmada: 5 registros (sem duplicatas)

🎉 Teste concluído com sucesso!
```

## Estrutura de Dados

### QuoteOHLCV
```python
class QuoteOHLCV(SQLModel, table=True):
    id: int
    ticker: str
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    adj_close: float
    raw: dict
    # UniqueConstraint("ticker", "date")
```

### Dividend
```python
class Dividend(SQLModel, table=True):
    id: int
    ticker: str
    ex_date: datetime
    payment_date: datetime
    amount: float
    currency: str
    type: str
    raw: dict
    # UniqueConstraint("ticker", "ex_date")
```

### FinancialsTTM
```python
class FinancialsTTM(SQLModel, table=True):
    id: int
    ticker: str  # unique
    data: dict
    updated_at: datetime
```

## Troubleshooting

### Erro: Menos de 45 candles
```
⚠️  Aviso: Esperado ≥45 candles para 3mo, recebido 35
```
**Causa**: Ativo com poucos dias de negociação ou feriados/finais de semana  
**Solução**: Normal para ativos novos ou períodos com muitos feriados

### Erro: Idempotência falhou
```
⚠️  Idempotência OHLCV falhou: 63 → 126 registros
```
**Causa**: Constraint UNIQUE não está funcionando  
**Solução**: Verificar migrações do banco e índices

### Erro: TTM não atualizado
```
📦 Registro FinancialsTTM no banco: NÃO
```
**Causa**: Módulo `financialData` não foi solicitado ou não disponível no plano free  
**Solução**: Verificar se `modules=["financialData"]` está sendo passado

## Próximos Passos

1. ✅ Testar com outros ativos (VALE3, ITSA4, etc.)
2. ✅ Validar com ranges diferentes (6mo, 1y)
3. ✅ Adicionar testes pytest formais
4. ✅ Criar job de atualização diária
5. ✅ Implementar cache inteligente

## Referências

- [Brapi API Docs](https://brapi.dev/docs)
- [SQLModel Docs](https://sqlmodel.tiangolo.com/)
- [Pytest Async](https://pytest-asyncio.readthedocs.io/)
