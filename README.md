# brapi_sqlmodel_boilerplate

API FastAPI com SQLModel e Redis para integração com dados financeiros da [brapi.dev](https://brapi.dev).

## 🚀 Features

- **Catálogo de Ativos**: Organização por setor/tipo (stocks, funds, BDRs, ETFs)
- **Dados Históricos**: Séries OHLCV com até 3 meses de histórico (plano free)
- **Cache Redis**: Cache inteligente com TTL configurável e rotinas de limpeza assíncronas
- **Rate Limiting**: Respeita limites do plano free (1 ticker/requisição)
- **Observabilidade**: Auditoria completa de chamadas via tabela `ApiCall`
- **ETL Jobs**: Scripts de sincronização automatizados
- **Docker Ready**: Ambiente completo com MySQL, Redis e API

## 📋 Pré-requisitos

- Python 3.11+
- Docker & Docker Compose
- Token brapi.dev (opcional para testes com 4 ações gratuitas)

## 🛠️ Setup Rápido

### 1. Clonar e Configurar

```bash
git clone <repository>
cd brapi_sqlmodel_boilerplate

# Copiar arquivo de ambiente
cp .env.example .env

# Editar .env com seu token (opcional)
# BRAPI_TOKEN=seu_token_aqui
```

### 2. Iniciar com Docker

```bash
# Iniciar todos os serviços
docker-compose up -d

# Aguardar serviços estarem prontos
docker-compose logs -f api
```

### 3. Setup Local (alternativa)

```bash
# Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou .venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt
pip install -r requirements-test.txt

# Iniciar MySQL e Redis
docker-compose up -d mysql redis

# Rodar migrações
python -c "from app.db.session import create_all; import asyncio; asyncio.run(create_all())"

# Iniciar API
uvicorn app.main:app --reload
```

## 📊 Endpoints da API

### Catálogo de Ativos

#### Listar Ativos
```http
GET /api/catalog/assets?type=stock&sector=Petróleo&page=1&limit=50&sort_by=name
```

**Parâmetros:**
- `type`: stock, fund, bdr, etf, index
- `sector`: Filtrar por setor
- `search`: Buscar por nome ou ticker
- `page`: Número da página (default: 1)
- `limit`: Itens por página (1-100)
- `sort_by`: name, ticker, sector, updated_at

**Response:**
```json
{
  "assets": [
    {
      "ticker": "PETR4",
      "name": "PETROBRAS PN",
      "type": "stock",
      "sector": "Petróleo, Gás e Biocombustíveis",
      "segment": "Petróleo, Gás e Biocombustíveis",
      "isin": "BRPETRACNOR11",
      "logo_url": "https://icons.brapi.dev/logos/PETR4.png",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 1250,
    "pages": 25
  }
}
```

#### Detalhe do Ativo
```http
GET /api/catalog/assets/{ticker}
```

#### Sincronizar Catálogo
```http
POST /api/catalog/sync/{type}?limit=100
```

#### Tipos e Setores Disponíveis
```http
GET /api/catalog/types
GET /api/catalog/sectors
```

### Dados Históricos OHLCV

#### Buscar Dados OHLCV
```http
GET /api/ohlcv?ticker=PETR4&period=3mo&interval=1d
```

**Parâmetros:**
- `ticker`: Símbolo do ativo (obrigatório)
- `period`: 1mo, 3mo, 6mo, 1y, 2y, max
- `interval`: 1d, 1wk, 1mo
- `start_date`: Data inicial (YYYY-MM-DD)
- `end_date`: Data final (YYYY-MM-DD)
- `limit`: Limite de registros (1-1000)

**Response:**
```json
{
  "ticker": "PETR4",
  "data": [
    {
      "date": "2024-01-15T00:00:00Z",
      "open": 38.20,
      "high": 39.00,
      "low": 37.80,
      "close": 38.50,
      "volume": 45678901,
      "adj_close": 38.50
    }
  ],
  "count": 65
}
```

#### Datas Disponíveis
```http
GET /api/ohlcv/dates/{ticker}
```

#### Backfill de Dados
```http
POST /api/ohlcv/backfill?tickers=PETR4,VALE3&range=3mo&concurrency=3
```

#### Atualização Recente
```http
POST /api/ohlcv/update?tickers=PETR4,VALE3&concurrency=3
```

## 🔄 Jobs ETL

### Rotinas de Limpeza

As rotinas abaixo ajudam a manter o banco e o cache enxutos. Execute-as periodicamente (cron, Airflow, etc.) usando um evento assíncrono:

```bash
python - <<'PY'
import asyncio
from app.db.session import AsyncSessionLocal
from app.services.quote_service import cleanup_quote_artifacts
from app.services.crypto_service import cleanup_crypto_artifacts
from app.services.currency_service import cleanup_currency_artifacts

async def main():
    async with AsyncSessionLocal() as session:
        quote_stats = await cleanup_quote_artifacts(session)
        crypto_stats = await cleanup_crypto_artifacts(session)
        currency_stats = await cleanup_currency_artifacts(session)
    print({
        "quote": quote_stats,
        "crypto": crypto_stats,
        "currency": currency_stats,
    })

asyncio.run(main())
PY
```

## 📚 Database Schema Documentation

The project uses **SQLModel** to model the relational schema. Below is a summary of each table, its purpose, columns and mapping to the brapi.dev API (free plan).

### `assets`
| Column | Type | Description | brapi.dev mapping |
|---|---|---|---|
| id | Integer PK | Internal identifier | – |
| ticker | String | Symbol (e.g. PETR4) | `symbol` |
| name | String | Full name | `name` |
| type | String | `stock`, `fund`, `bdr` (free plan) | `type` |
| sector | String | Economic sector | `sector` |
| segment | String | Sub‑sector | `segment` |
| isin | String | ISIN code | `isin` |
| logo_url | String | Logo URL | `logo` |
| raw | JSON | Raw payload snapshot | – |
| created_at / updated_at | datetime | Timestamps | – |

### `quote_ohlcv`
| Column | Type | Description | brapi.dev mapping |
|---|---|---|---|
| id | Integer PK | – | – |
| ticker | String | FK to `assets.ticker` | `symbol` |
| date | datetime | Candle date | `date` |
| open | Float | Opening price | `open` |
| high | Float | Highest price | `high` |
| low | Float | Lowest price | `low` |
| close | Float | Closing price | `close` |
| adj_close | Float (opt) | Adjusted close | `adjClose` |
| volume | Integer | Traded volume | `volume` |
| raw | JSON | Full candle payload | – |

### `dividend`
| Column | Type | Description | brapi.dev mapping |
|---|---|---|---|
| id | Integer PK | – | – |
| ticker | String | FK to `assets.ticker` | `symbol` |
| ex_date | datetime | Ex‑date | `exDate` |
| payment_date | datetime | Payment date | `paymentDate` |
| amount | Float | Dividend amount | `amount` |
| currency | String | Currency | `currency` |
| type | String | Dividend type | `type` |
| raw | JSON | Full payload | – |

### `financials_ttm`
| Column | Type | Description | brapi.dev mapping |
|---|---|---|---|
| id | Integer PK | – | – |
| ticker | String | FK to `assets.ticker` | `symbol` |
| data | JSON | TTM financial indicators (e.g. `priceEarnings`) | `financialData` |
| updated_at | datetime | Last refresh | – |

### `api_calls`
| Column | Type | Description |
|---|---|---|
| id | Integer PK | – |
| endpoint | String | API endpoint name |
| tickers | String | Comma‑separated tickers |
| params | JSON | Request parameters |
| cached | Boolean | From Redis cache |
| status_code | Integer | HTTP status |
| error | String (opt) | Error message |
| response | JSON (opt) | API payload |
| created_at | datetime | Timestamp |

**Note:** The free plan only supports `stock`, `fund` and `bdr` asset types; attempts to request `etf` or `index` return HTTP 417. Parameters `fundamental` and `dividends` are rejected (HTTP 403). The code enforces these limits in `catalog_service`, `populate_all.py` and the CLI job.

### References
- **Listar Cotações** – <https://brapi.dev/docs/acoes/list>
- **Detalhes da Cotação** – <https://brapi.dev/docs/acoes/quote>
- **Limitações do Plano Free** – <https://brapi.dev/en/docs/plan#free>
- **Código de erro 417** – <https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/417>
- **Código de erro 403** – <https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403>

```

> Dica: os padrões de chave incluem um trecho humano (`quote:PETR4:...`), facilitando inspeções manuais no Redis.

### Sincronizar Catálogo

```bash
# Sincronizar todos os tipos
python jobs/sync_catalog.py --all

# Sincronizar tipo específico
python jobs/sync_catalog.py --type stock --limit 100

# Sincronizar fundos imobiliários
python jobs/sync_catalog.py --type fund
```

### Preencher Dados Históricos

```bash
# Usar tickers específicos
python jobs/backfill_ohlcv.py --tickers "PETR4,VALE3,MGLU3" --range 3mo

# Usar arquivo com tickers
python jobs/backfill_ohlcv.py --file jobs/tickers_example.txt

# Por tipo de ativo
python jobs/backfill_ohlcv.py --type stock --limit 50

# Controlar concorrência
python jobs/backfill_ohlcv.py --tickers "PETR4,VALE3" --concurrency 2
```

### Atualização Diária

```bash
# Atualizar todos os tickers
python jobs/update_daily.py

# Apenas tickers recentes (7 dias)
python jobs/update_daily.py --recent

# Tickers específicos
python jobs/update_daily.py --tickers "PETR4,VALE3"

# Dry run (simulação)
python jobs/update_daily.py --dry-run
```

## 🧪 Testes

### Ambientes recomendados

- **Local isolado**: exporte `ENV=test` e utilize um banco dedicado (`DATABASE_URL=mysql+asyncmy://.../brapi_test`).
- **Docker**: suba apenas MySQL/Redis (`docker-compose up -d mysql redis`) e use o mesmo comando de testes.
- **CI**: configure variáveis de retenção (veja abaixo) para garantir que as rotinas de limpeza sejam cobertas.

```bash
# Instalar dependências de teste
pip install -r requirements-test.txt

# Rodar todos os testes
pytest

# Rodar com coverage
pytest --cov=app --cov-report=html

# Rodar testes específicos
pytest tests/test_catalog_service.py -v
pytest tests/test_ohlcv_service.py -v
```

## 📈 Limites do Plano Free

- **15.000 requisições/mês**
- **1 ticker por requisição** (não usar múltiplos tickers)
- **Histórico de até 3 meses**
- **4 ações gratuitas**: PETR4, MGLU3, VALE3, ITUB4
- **Intervalo mínimo**: 1d

### Boas Práticas

- Use semáforo com max_concurrency=3-5
- Adicione jitter entre chamadas (0.2-0.6s)
- Implemente retry exponencial para HTTP 429
- Prefira dados em cache do que requisições diretas

## 🔧 Configuração

### Variáveis de Ambiente

```bash
# brapi
BRAPI_BASE_URL=https://brapi.dev
BRAPI_TOKEN=seu_token_aqui

# Banco de dados
DATABASE_URL=mysql+asyncmy://user:pass@localhost:3306/brapi_db

# Cache Redis
REDIS_URL=redis://localhost:6379/0

# TTL Cache (segundos)
CACHE_TTL_QUOTE_SECONDS=1800
CACHE_TTL_CURRENCY_SECONDS=3600
CACHE_TTL_OHLCV_SECONDS=30

# Retenção (dias)
RETENTION_DAYS_SNAPSHOTS=30
RETENTION_DAYS_CRYPTO=30
RETENTION_DAYS_CURRENCY=30
RETENTION_DAYS_MACRO=365
RETENTION_DAYS_OHLCV=730
RETENTION_DAYS_API_CALLS=14
```

### Configuração de Rate Limiting

```python
# Nos jobs ETL
MAX_CONCURRENCY = 3  # Máximo de requisições simultâneas
BASE_DELAY = 0.2     # Delay base entre chamadas
JITTER_RANGE = 0.4   # Variação aleatória do delay
MAX_RETRIES = 3      # Máximo de tentativas com retry
```

## 📊 Monitoramento

### Health Check

```http
GET /health
```

**Response:**
```json
{
  "db": "ok",
  "redis": "ok"
}
```

### Observabilidade

A tabela `api_calls` registra todas as chamadas:

```sql
SELECT 
    endpoint,
    COUNT(*) as total_calls,
    SUM(CASE WHEN cached THEN 1 ELSE 0 END) as cache_hits,
    AVG(status_code) as avg_status
FROM api_calls 
WHERE created_at >= NOW() - INTERVAL 1 HOUR
GROUP BY endpoint;
```

## 🐛 Troubleshooting

### Problemas Comuns

#### "Ativo não encontrado no catálogo"
```bash
# Sincronizar catálogo primeiro
python jobs/sync_catalog.py --type stock
```

#### "Rate limit exceeded"
```bash
# Reduzir concorrência e aumentar delays
python jobs/backfill_ohlcv.py --concurrency 1
```

#### "Datetime not JSON serializable"
- Verifique se está usando `json_serializer` ou `normalize_for_json()`
- Todas as respostas HTTP devem converter datetime para ISO string

#### Cache não está funcionando
```bash
# Verificar Redis
docker-compose exec redis redis-cli ping

# Limpar cache
docker-compose exec redis redis-cli FLUSHALL
```

## 📝 Exemplos de Uso

### curl Examples

```bash
# Listar ações do setor de petróleo
curl "http://localhost:8000/api/catalog/assets?type=stock&sector=Petróleo"

# Buscar dados históricos da PETR4
curl "http://localhost:8000/api/ohlcv?ticker=PETR4&period=3mo"

# Sincronizar catálogo de fundos
curl -X POST "http://localhost:8000/api/catalog/sync/fund?limit=100"

# Backfill para tickers específicos
curl -X POST "http://localhost:8000/api/ohlcv/backfill?tickers=PETR4,VALE3&range=3mo"
```

### Python Client

```python
import httpx

# Listar ativos
response = httpx.get("http://localhost:8000/api/catalog/assets?type=stock")
assets = response.json()

# Buscar OHLCV
response = httpx.get("http://localhost:8000/api/ohlcv?ticker=PETR4&period=3mo")
ohlcv = response.json()

print(f"Found {len(ohlcv['data'])} data points for {ohlcv['ticker']}")
```

## 🏗️ Arquitetura

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Client    │───▶│   FastAPI   │───▶│    Redis    │
└─────────────┘    └─────────────┘    └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │ SQLModel +  │
                   │   MySQL     │
                   └─────────────┘
                          ▲
                          │
                   ┌─────────────┐
                   │  brapi.dev  │
                   │    API      │
                   └─────────────┘
```

### Models Principais

- **Asset**: Catálogo de ativos (ticker, name, type, sector)
- **QuoteOHLCV**: Séries históricas (date, open, high, low, close, volume)
- **Dividend**: Dados de dividendos (ex_date, payment_date, amount)
- **ApiCall**: Auditoria (endpoint, params, status, cache_hit)

## 🔗 Links Úteis

- [Documentação brapi.dev](https://brapi.dev/docs)
- [Dashboard brapi.dev](https://brapi.dev/dashboard)
- [Status da API](https://brapi.dev/status)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---


