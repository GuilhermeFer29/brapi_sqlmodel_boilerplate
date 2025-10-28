30 perguntas para testar o MCP da brapi no plano free

Dica: foque nas tools públicas (listagens). Evite pedir preços/histórico/FX/prime-rate/inflação — isso aciona tools premium.

Ações / FIIs / BDRs (tool: get_available_stocks)

“Liste 20 ações do setor Technology Services, ordenadas por name (apenas ticker e nome). Não consulte preços.”

“Quais FIIs (type: fund) existem? Traga até 50 com segmento/descrição quando disponível, sem preços.”

“Mostre BDRs (type: bdr) com ordenação por name (A→Z); limite 30; só ticker e nome.”

“Quero ações do setor Energy Minerals; traga até 25 e inclua o código ISIN se houver, sem consultar cotações.”

“Filtre por type: stock e setor Finance, com busca = ‘ITAU’; liste ticker e nome.”

“Traga ações de Utilities paginadas: page=1, limit=20; retorne ticker, nome, setor.”

“Liste FIIs logísticos (tente buscar por ‘log’ no nome/descrição), limit=40, ordene por name.”

“Dê 10 BDRs de empresas de tecnologia (busca ‘tech’), ticker e nome, sem preço.”

“Quero uma lista mista de stocks e funds que contenham ‘BRASIL’ no nome; limit=30; ordene por name.”

“Liste ações small caps (use filtros/termos que ajudem a aproximar), limit=25; traga ticker, nome e setor.”

Exploração por ordenação e paginação

“Liste stocks ordenados por market_cap_basic (maior→menor), limit=20, page=1 — só ticker e nome.”

“Agora page=2 da mesma consulta (stocks por market cap), mesmo formato.”

“Traga funds ordenados por close (sem pedir preço; quero apenas a ordenação), limit=30.”

“Liste BDRs ordenados por name; limit=50; mostre ticker, nome.”

“Quero stocks com busca = ‘PETRO’ (ex.: Petrobras); limit=15; apenas ticker, nome e setor.”

Logos e metadados (sem preço)

“Liste 10 ações cujo nome contenha ‘VALE’ e inclua o campo de logo/URL do logo se a tool fornecer.”

“Quero FIIs com ‘Renda’ no nome; retorne ticker, nome e segmento (sem histórico/preço).”

“Mostre BDRs relacionados a ‘APPLE’ (busca por nome), ticker e nome, sem consultar preço.”

Moedas e Criptos (tools: get_available_currencies, get_available_cryptocurrencies)

“Liste todos os pares de moedas disponíveis envolvendo BRL (ex.: USD-BRL, EUR-BRL).”

“Quais pares de moedas com USD estão disponíveis? Traga os símbolos completos.”

“Liste criptomoedas disponíveis (símbolo e nome) aceitas pela brapi, limit=50.”

“Quero criptos cujo nome contenha ‘BIT’ (ex.: Bitcoin); liste símbolos e nomes.”

“Traga pares de moedas com EUR e mostre símbolo e uma breve descrição se houver.”

Países com dados de inflação (listagem pública)

“Quais países têm dados de inflação disponíveis? Somente a lista de países, sem pedir séries.”

“Filtre a lista de países de inflação para os que contenham ‘Uni’ (autocomplete/busca parcial).”

“Liste países de inflação ordenados alfabeticamente (se suportado) e devolva apenas o array de nomes.”

Consultas combinadas (descoberta sem preço)

“Quero stocks do setor Finance e funds (FIIs) cujo nome contenha ‘RENDA’; traga até 40 entradas (ticker, nome, setor/tipo), sem histórico.”

“Liste BDRs e stocks com palavra-chave ‘AMAZON’ (busca no nome); retorne ticker e nome; limit=30.”

“Filtre stocks por setor Consumer Non-Durables com limit=25 e page=1, em seguida me diga só os tickers.”

“Traga FIIs com possíveis segmentos ‘Shopping/Logística/Recebíveis’ (use busca textual no nome/descrição), limit=30; só ticker, nome, segmento.”

Observações rápidas

Se o agente tentar preço/histórico/FX/prime-rate/inflação em série, vai cair em tools premium → erro de permissão no free.

Use as palavras “não consulte preços”, “apenas listagem”, “somente metadados” nos prompts para evitar que o agente chame tools premium por engano.

Quando precisar de dados numéricos, você pode:

usar suas rotas do backend com caches/fallbacks;

ou considerar upgrade na brapi para liberar as tools premium no MCP.
