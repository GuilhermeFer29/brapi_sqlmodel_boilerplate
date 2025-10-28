# brapi_sqlmodel_boilerplate
**Padrão de pastas organizado** + **SQLModel (async)** + **SDK oficial brapi** + **Redis cache** + **persistência MySQL** + **pipeline OpenAPI**.

## Estrutura
```
app/
  core/          # config, cache
  db/            # engine/AsyncSession
  models/        # SQLModel tables (ApiCall, QuoteSnapshot, ...)
  services/      # brapi client + regras (cache, persistência, validação)
  api/routes/    # rotas FastAPI
  utils/         # utilitários
  openapi_*      # schemas e modelos gerados (opcional)
scripts/         # fetch/generate OpenAPI
Dockerfile, docker-compose.yml, .env.example
```

## Como rodar
1) `cp .env.example .env` e ajuste `BRAPI_TOKEN` se necessário
2) `docker compose up --build`
3) `http://localhost:8000/docs`
4) Exemplos:
```bash
curl "http://localhost:8000/api/available"
curl "http://localhost:8000/api/quote?tickers=PETR4,VALE3&range=1mo&interval=1d"
curl "http://localhost:8000/api/crypto?coin=BTC,ETH&currency=USD"
curl "http://localhost:8000/api/currency?currency=USD-BRL,EUR-BRL"
curl "http://localhost:8000/api/inflation?country=brazil"
curl "http://localhost:8000/api/prime-rate?country=brazil"
```

## SQLModel (async)
- Engine: `mysql+asyncmy://...`
- Tabelas criadas no startup: `await create_all()`
- Inserções em lote: `session.add_all([...])` + `await session.commit()`

## OpenAPI (trazer schemas)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/fetch_openapi.py
bash scripts/generate_models.sh
```
Os serviços tentam validar payloads contra `app/openapi_models/*` se existir; caso contrário, seguem sem quebrar.

## Notas (coach mode)
- O design respeita o **free** (1 ativo/req + delay), com cache alinhado ao SLA. Quer intraday de verdade? Migre de plano e eu ajusto para **batch** (10–20 tickers/req) atrás de uma flag.
- Persistimos **payload bruto** (auditoria) + **snapshots normalizados** (consulta rápida); se isso virar gargalo, adicionamos índices e partição por data.
- Nunca exponha `BRAPI_TOKEN` no front — a API já funciona como proxy seguro.
