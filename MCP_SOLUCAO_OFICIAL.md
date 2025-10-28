# 🔧 Solução Oficial - brapi MCP (Documentação Oficial)

## Fonte: https://brapi.dev/docs/mcp

### ⚠️ PROBLEMA IDENTIFICADO

As ferramentas `get_available_*` não estavam retornando resultados porque os **filtros estavam incorretos**.

### ✅ SOLUÇÃO CORRETA

Os filtros devem usar os valores EXATOS conforme documentação oficial:

## Filtros Corretos para `get_available_stocks`

### 1. **Setores (sector)** - VALORES CORRETOS:
```
- Finance (Bancos e instituições financeiras)
- Energy Minerals (Petróleo e energia)
- Technology Services (Tecnologia)
- Health Services (Saúde)
- Retail Trade (Varejo)
- Utilities (Energia elétrica e saneamento)
```

❌ ERRADO: `sector="Bancos"` ou `sector="Energia"`
✅ CORRETO: `sector="Finance"` ou `sector="Energy Minerals"`

### 2. **Tipos (type)** - VALORES CORRETOS:
```
- stock (Ações ordinárias e preferenciais)
- fund (Fundos imobiliários - FIIs)
- bdr (Brazilian Depositary Receipts)
```

### 3. **Ordenação (sort)** - VALORES CORRETOS:
```
- volume (Volume de negociação)
- market_cap_basic (Valor de mercado)
- change (Variação percentual)
- close (Preço de fechamento)
- name (Ordem alfabética)
```

## Exemplos de Uso Correto

### Exemplo 1: Bancos mais negociados
```
Pergunta: "Quais são os bancos mais negociados?"
Ferramenta: get_available_stocks(sector='Finance', sort='volume')
Resultado: Lista de bancos ordenados por volume
```

### Exemplo 2: Ações de energia
```
Pergunta: "Mostre as ações de energia"
Ferramenta: get_available_stocks(sector='Energy Minerals')
Resultado: PETR4, VALE3, GGBR4, etc
```

### Exemplo 3: Fundos imobiliários
```
Pergunta: "Quais FIIs estão disponíveis?"
Ferramenta: get_available_stocks(type='fund')
Resultado: Lista de fundos imobiliários
```

### Exemplo 4: Ações de tecnologia ordenadas por market cap
```
Pergunta: "Empresas de tecnologia por valor de mercado"
Ferramenta: get_available_stocks(sector='Technology Services', sort='market_cap_basic')
Resultado: Empresas de tech ordenadas por market cap
```

## Ferramentas Disponíveis (Completas)

### Públicas (Sem Autenticação)
1. **get_available_stocks** - Lista ações com filtros
2. **get_available_currencies** - Lista pares de moedas
3. **get_available_cryptocurrencies** - Lista criptomoedas
4. **get_available_inflation_countries** - Lista países com inflação

### Premium (Requer Token)
1. **get_stock_quotes** - Cotações e históricos
2. **get_currency_rates** - Taxas de câmbio
3. **get_crypto_prices** - Preços de criptomoedas
4. **get_inflation_data** - Dados de inflação
5. **get_prime_rate_data** - Taxa Selic

## Configuração Correta no Agent

```python
system_prompt = (
    "FILTROS CORRETOS PARA get_available_stocks:\n"
    "Setores: Finance, Energy Minerals, Technology Services, Health Services, Retail Trade, Utilities\n"
    "Tipos: stock, fund, bdr\n"
    "Ordenação: volume, market_cap_basic, change, close, name\n"
)
```

## Testes Recomendados

### Teste 1: Descoberta de Bancos
```
Pergunta: "Quais são os bancos mais negociados?"
Esperado: Lista de bancos (ITUB4, BBAS3, BBDC4, SANB11, etc)
```

### Teste 2: Descoberta de Energia
```
Pergunta: "Mostre as ações de energia"
Esperado: Lista de ações de energia (PETR4, VALE3, GGBR4, etc)
```

### Teste 3: Cotação Específica
```
Pergunta: "Qual a cotação de PETR4?"
Esperado: Preço atual, variação, volume, etc
```

### Teste 4: Fundos Imobiliários
```
Pergunta: "Quais fundos imobiliários estão disponíveis?"
Esperado: Lista de FIIs
```

## Diferença Entre Ferramentas

| Ferramenta | Uso | Retorna |
|-----------|-----|---------|
| `get_available_stocks` | Descobrir ativos | Lista de símbolos |
| `get_stock_quotes` | Dados específicos | Preço, histórico, volume |
| `get_available_currencies` | Descobrir moedas | Lista de pares |
| `get_currency_rates` | Taxa específica | Preço da moeda |

## Checklist de Uso Correto

- ✅ Usar `sector='Finance'` (não "Bancos")
- ✅ Usar `sector='Energy Minerals'` (não "Energia")
- ✅ Usar `type='fund'` para FIIs
- ✅ Usar `sort='volume'` para ordenar por volume
- ✅ Usar `get_stock_quotes` para cotações específicas
- ✅ Passar token via Bearer header
- ✅ Usar `get_available_*` para descoberta
- ✅ Usar ferramentas premium para dados detalhados

## Recursos Oficiais

- Documentação MCP: https://brapi.dev/docs/mcp
- Documentação Geral: https://brapi.dev/docs
- Dashboard: https://brapi.dev/dashboard
- Status: https://brapi.dev/status

## Próximos Passos

1. Reiniciar o Streamlit
2. Testar com as perguntas do "Testes Recomendados"
3. Verificar se as ferramentas retornam dados agora
4. Usar os filtros corretos em todas as consultas
