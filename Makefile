# Makefile para brapi_sqlmodel_boilerplate

.PHONY: help install test run docker-build docker-up docker-down docker-logs sync backfill update demo clean reset populate-all reset-and-start

# Variáveis
PYTHON := python3
PIP := pip3
DOCKER_COMPOSE := docker-compose

help: ## Exibe ajuda
	@echo "Comandos disponíveis:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Instala dependências
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-test.txt

test: ## Roda testes
	pytest -v --cov=app --cov-report=html

test-fast: ## Roda testes rápidos (sem coverage)
	pytest -v

run: ## Inicia API localmente
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker-build: ## Build da imagem Docker
	docker build -t brapi-sqlmodel .

docker-up: ## Inicia todos os serviços com Docker
	$(DOCKER_COMPOSE) up -d

docker-down: ## Para todos os serviços
	$(DOCKER_COMPOSE) down

docker-logs: ## Mostra logs da API
	$(DOCKER_COMPOSE) logs -f api

sync: ## Sincroniza catálogo de ativos
	$(PYTHON) jobs/sync_catalog.py --type stock

sync-all: ## Sincroniza todos os tipos de ativos
	$(PYTHON) jobs/sync_catalog.py --all

backfill: ## Preenche dados históricos (ações populares)
	$(PYTHON) jobs/backfill_ohlcv.py --tickers "PETR4,VALE3,MGLU3,ITUB4,WEGE3,BBAS3" --range 3mo

backfill-file: ## Preenche dados usando arquivo de exemplo
	$(PYTHON) jobs/backfill_ohlcv.py --file jobs/tickers_example.txt --range 3mo

update: ## Atualiza dados recentes
	$(PYTHON) jobs/update_daily.py --recent

demo: ## Executa demonstração completa
	$(PYTHON) examples/demo_workflow.py

clean: ## Limpa cache e arquivos temporários
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .coverage htmlcov/
	$(DOCKER_COMPOSE) exec redis redis-cli FLUSHALL || true

# Comandos de desenvolvimento
dev-setup: install docker-up ## Setup completo para desenvolvimento
	@echo "Aguardando serviços..."
	sleep 10
	@echo "Verificando saúde..."
	curl -f http://localhost:8000/health || (echo "API não está pronta" && exit 1)
	@echo "Setup concluído! API disponível em http://localhost:8000"

# Comandos de banco de dados
db-shell: ## Acessa shell do MySQL
	$(DOCKER_COMPOSE) exec mysql mysql -u brapi_user -pbrapi_pass brapi_db

redis-shell: ## Acessa shell do Redis
	$(DOCKER_COMPOSE) exec redis redis-cli

# Comandos de monitoramento
logs: docker-logs
status: ## Verifica status dos serviços
	$(DOCKER_COMPOSE) ps
	@echo "\n--- Health Check ---"
	curl -s http://localhost:8000/health | jq . || echo "API não disponível"

# Comandos de produção (exemplos)
deploy-staging: ## Exemplo de deploy para staging
	@echo "Este é um exemplo. Adaptar para seu ambiente de deploy."
	# docker build -t registry.com/brapi:staging .
	# docker push registry.com/brapi:staging
	# kubectl apply -f k8s/staging/

backup-db: ## Backup do banco de dados
	$(DOCKER_COMPOSE) exec mysql mysqldump -u brapi_user -pbrapi_pass brapi_db > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "Backup criado"

# Utilitários
format: ## Formata código Python
	black app/ jobs/ tests/ examples/
	isort app/ jobs/ tests/ examples/

lint: ## Verifica lint do código
	flake8 app/ jobs/ tests/ examples/
	mypy app/ --ignore-missing-imports

security: ## Verifica segurança das dependências
	safety check
	bandit -r app/

# Comandos de reset e população
reset: ## Reseta ambiente Docker (remove containers e volumes)
	$(DOCKER_COMPOSE) down -v
	docker system prune -f
	@echo "✅ Ambiente resetado"

populate-all: ## Popula banco com catálogo e dados históricos
	$(PYTHON) scripts/populate_all.py

reset-and-start: ## Reseta tudo e popula do zero (comando completo)
	$(PYTHON) scripts/reset_and_start.py

# Comando de desenvolvimento completo
full-setup: reset-and-start ## Alias para setup completo do zero
