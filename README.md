# Guia de Uso da API brapi com MCP

## Ferramentas Disponíveis via MCP

### 📊 Ferramentas Públicas (Sem Autenticação)

#### 1. get_available_stocks

Lista ações e índices brasileiros com filtros avançados.

**Parâmetros**:

- `sector`: Filtrar por setor (ex: "Energia", "Tecnologia", "Bancos")
- `type`: Tipo de ativo (ex: "stock", "index", "fii", "etf", "bdr")
- `search`: Buscar por nome ou símbolo
- `sort`: Ordenação (ex: "name", "market_cap", "volume")

**Exemplos de Uso**:

```
"Liste todas as ações de bancos brasileiros"
"Quais são as ações do setor de energia?"
"Mostre os fundos imobiliários (FIIs) disponíveis"
"Liste as ações ordenadas por volume de negociação"
```

#### 2. get_available_currencies

Lista pares de moedas disponíveis para consulta.

**Exemplos de Uso**:

```
"Quais pares de moedas estão disponíveis?"
"Mostre as moedas que posso consultar"
```

#### 3. get_available_cryptocurrencies

Lista criptomoedas disponíveis.

**Exemplos de Uso**:

```
"Quais criptomoedas estão disponíveis?"
"Liste as principais criptomoedas"
```

#### 4. get_available_inflation_countries

Lista países com dados de inflação disponíveis.

**Exemplos de Uso**:

```
"Quais países têm dados de inflação disponíveis?"
```

---

### 💎 Ferramentas Premium (Requer Autenticação)

#### 1. get_stock_quotes

Obtém cotações e dados históricos de ações.

**Parâmetros**:

- `tickers`: Símbolo(s) da ação (ex: "PETR4", "VALE3")
- `range`: Período histórico (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
- `interval`: Granularidade (1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo, 3mo)
- `fundamental`: Boolean para incluir dados fundamentalistas
- `dividends`: Boolean para incluir histórico de dividendos

**Exemplos de Uso**:

```
"Qual a cotação da PETR4?"
"Mostre o histórico de MGLU3 nos últimos 3 meses"
"Cotação de VALE3 com dados fundamentalistas"
"Histórico de dividendos da ITUB4 nos últimos 2 anos"
```

#### 2. get_currency_rates

Obtém taxas de câmbio em tempo real.

**Parâmetros**:

- `pair`: Par de moedas (ex: "USD-BRL", "EUR-BRL")

**Exemplos de Uso**:

```
"Qual a taxa de câmbio USD-BRL?"
"Cotação do Euro em Reais"
"Mostre as principais moedas em relação ao Real"
```

#### 3. get_crypto_prices

Obtém preços de criptomoedas.

**Parâmetros**:

- `symbol`: Símbolo da criptomoeda (ex: "BTC", "ETH")

**Exemplos de Uso**:

```
"Preço do Bitcoin em Reais"
"Cotação da Ethereum"
"Compare os preços de BTC, ETH e ADA"
```

#### 4. get_inflation_data

Obtém dados de inflação.

**Parâmetros**:

- `country`: País (ex: "BR" para Brasil)
- `index`: Tipo de índice (ex: "IPCA", "IGP-M")

**Exemplos de Uso**:

```
"Qual foi a inflação do último mês?"
"Histórico de IPCA"
"Dados de inflação do Brasil"
```

#### 5. get_prime_rate_data

Obtém dados da taxa básica de juros (Selic).

**Exemplos de Uso**:

```
"Qual é a taxa Selic atual?"
"Histórico da taxa Selic"
```

---

## Fluxo Recomendado de Uso

1. **Descoberta**: Use ferramentas públicas (`get_available_*`) para explorar dados
2. **Consulta**: Use ferramentas premium para obter dados específicos
3. **Análise**: Combine múltiplas consultas para análises completas

### Exemplo de Fluxo Completo

```
Usuário: "Analise as ações do setor de energia"

Agent:
1. Usa get_available_stocks(sector="Energia") para descobrir ações
2. Usa get_stock_quotes para obter cotações de PETR4, VALE3, etc
3. Formata resposta com análise e comparação
```

---

## Autenticação

O token de API está configurado em `.env`:

```
BRAPI_API_KEY=seu_token_aqui
```

**Métodos de Autenticação Suportados**:

- Header: `Authorization: Bearer sua_chave_api`
- Header: `Authorization: sua_chave_api`
- Query Parameter: `?token=sua_chave_api`

Para obter um token:

1. Acesse https://brapi.dev/dashboard
2. Crie uma conta ou faça login
3. Copie seu token de API
4. Adicione ao arquivo `.env`

---

## Problemas Comuns e Soluções

### ❌ Ferramenta Retorna Lista Vazia

**Causa**: As ferramentas `get_available_*` podem retornar vazias ou erro

**Solução - Use as Ferramentas Premium Diretamente**:

#### Para Criptomoedas:

```
❌ "Liste para mim as criptomoedas disponíveis"
   → Pode retornar vazio

✅ "Qual é o preço do Bitcoin em Reais?"
   → Usa get_crypto_prices com BTC

✅ "Mostre os preços de BTC, ETH, LTC em Reais"
   → Consulta múltiplas criptomoedas
```

**Criptomoedas Conhecidas para Consultar**:

- BTC (Bitcoin)
- ETH (Ethereum)
- LTC (Litecoin)
- XRP (Ripple)
- ADA (Cardano)
- SOL (Solana)
- DOGE (Dogecoin)
- USDT (Tether)
- BNB (Binance Coin)

#### Para Moedas/Câmbio:

```
❌ "Quais pares de moedas estão disponíveis?"
   → Pode retornar vazio

✅ "Qual a taxa de câmbio USD-BRL?"
   → Usa get_currency_rates com USD-BRL

✅ "Mostre as taxas de EUR-BRL, GBP-BRL, JPY-BRL"
   → Consulta múltiplos pares
```

**Pares de Moedas Conhecidos para Consultar**:

- USD-BRL (Dólar Americano)
- EUR-BRL (Euro)
- GBP-BRL (Libra Esterlina)
- JPY-BRL (Iene Japonês)
- AUD-BRL (Dólar Australiano)
- CAD-BRL (Dólar Canadense)
- CHF-BRL (Franco Suíço)

#### Para Ações:

```
❌ "Liste todas as ações de bancos brasileiros"
   → Pode retornar vazio

✅ "Qual a cotação da PETR4?"
   → Usa get_stock_quotes com PETR4

✅ "Mostre o histórico de VALE3, ITUB4, MGLU3 nos últimos 3 meses"
   → Consulta múltiplas ações
```

**Ações Conhecidas para Consultar**:

- PETR4 (Petrobras)
- VALE3 (Vale)
- ITUB4 (Itaú Unibanco)
- MGLU3 (Magazine Luiza)
- WEGE3 (WEG)
- BBAS3 (Banco do Brasil)
- ABEV3 (Ambev)
- JBSS3 (JBS)
- LREN3 (Lojas Renner)
- RADL3 (Raiadrogasil)

#### Para Inflação:

```
❌ "Quais países têm dados de inflação?"
   → Pode retornar vazio

✅ "Qual foi a inflação do Brasil no último mês?"
   → Usa get_inflation_data com país BR
```

### 🔧 Estratégia Recomendada

**Se uma ferramenta `get_available_*` retornar vazia:**

1. **Não desista** - Use a ferramenta premium correspondente
2. **Seja específico** - Forneça símbolos/pares/tickers conhecidos
3. **Combine consultas** - Pergunte sobre múltiplos ativos de uma vez

**Exemplos de Perguntas Eficazes**:

```
✅ "Qual a cotação atual de PETR4, VALE3 e ITUB4?"
✅ "Mostre o histórico de MGLU3 nos últimos 3 meses"
✅ "Compare os preços de BTC, ETH e LTC em Reais"
✅ "Qual é a taxa de câmbio USD-BRL, EUR-BRL e GBP-BRL?"
✅ "Mostre os dados de inflação do Brasil"
✅ "Qual é a taxa Selic atual?"
```

### 🔐 Verificação de Autenticação

Se receber erro de autenticação:

1. Verifique o token em `.env`:

   ```
   BRAPI_API_KEY=seu_token_aqui
   ```

2. Confirme que o token é válido em https://brapi.dev/dashboard

3. Teste com uma ação conhecida:
   ```
   "Qual a cotação da PETR4?"
   ```

### 📊 Erro: "Error: " (Vazio)

**Causas Possíveis**:

1. Token de API inválido ou expirado
2. Limite de requisições atingido
3. Ferramenta MCP não está respondendo
4. Símbolo/par não existe

**Solução**:

- Verifique o token em `.env`
- Tente novamente após alguns segundos
- Use símbolos conhecidos da lista acima
- Verifique o status da API em https://brapi.dev/status

---

## Recursos Adicionais

- Documentação oficial MCP: https://brapi.dev/docs/mcp
- Documentação API REST: https://brapi.dev/docs
- Dashboard: https://brapi.dev/dashboard
- Status da API: https://brapi.dev/status
