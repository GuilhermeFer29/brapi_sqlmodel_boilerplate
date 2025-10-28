from __future__ import annotations

import os
import asyncio
from agno.agent import Agent
from agno.tools.mcp import MCPTools, StreamableHTTPClientParams
from agno.models.google import Gemini

__all__ = ["build_agent", "build_agent_sync", "run_sync"]

# Tentar importar o config_loader, mas não falhar se não estiver disponível
try:
    from app.config_loader import config as app_config
    USE_CONFIG_LOADER = True
except ImportError:
    USE_CONFIG_LOADER = False


def build_agent() -> Agent:
    """
    Agente Agno usando Gemini 2.5 Flash + MCP brapi (remoto).
    Suporta múltiplas fontes de configuração: Streamlit Secrets, TOML, .env
    """
    # Usar config_loader se disponível, caso contrário fallback para os.getenv
    if USE_CONFIG_LOADER:
        brapi_mcp_url = app_config.brapi.mcp_url
        brapi_token = app_config.brapi.api_key
        gemini_api_key = app_config.llm.gemini_api_key
    else:
        brapi_mcp_url = os.getenv("BRAPI_MCP_URL", "https://brapi.dev/api/mcp/mcp")
        brapi_token = os.getenv("BRAPI_API_KEY", "")
        gemini_api_key = os.getenv("GEMINI_API_KEY", "")

    if not brapi_token:
        raise RuntimeError("BRAPI_API_KEY não configurado. Configure via Streamlit Secrets, config.toml ou .env")

    if not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY não configurado. Configure via Streamlit Secrets, config.toml ou .env")

    model = Gemini(
        id="gemini-2.5-flash-lite-preview-09-2025", 
        api_key=gemini_api_key,
        max_output_tokens=60000  # Aumentar limite de tokens para respostas longas
    )

    system_prompt = (
        "Você é um analista financeiro especializado em dados do mercado brasileiro.\n\n"
        "FERRAMENTAS MCP DISPONÍVEIS (brapi.dev/docs/mcp):\n"
        "📊 Públicas: get_available_stocks, get_available_currencies, get_available_cryptocurrencies, get_available_inflation_countries\n"
        "💎 Premium: get_stock_quotes, get_currency_rates, get_crypto_prices, get_inflation_data, get_prime_rate_data\n\n"
        "FILTROS CORRETOS PARA get_available_stocks:\n"
        "Setores (sector):\n"
        "  - Finance (Bancos e instituições financeiras)\n"
        "  - Energy Minerals (Petróleo e energia)\n"
        "  - Technology Services (Tecnologia)\n"
        "  - Health Services (Saúde)\n"
        "  - Retail Trade (Varejo)\n"
        "  - Utilities (Energia elétrica e saneamento)\n\n"
        "Tipos (type):\n"
        "  - stock (Ações)\n"
        "  - fund (Fundos imobiliários - FIIs)\n"
        "  - bdr (Brazilian Depositary Receipts)\n\n"
        "Ordenação (sort):\n"
        "  - volume (Volume de negociação)\n"
        "  - market_cap_basic (Valor de mercado)\n"
        "  - change (Variação percentual)\n"
        "  - close (Preço de fechamento)\n"
        "  - name (Ordem alfabética)\n\n"
        "ESTRATÉGIA DE USO:\n"
        "1. Para DESCOBERTA (listar ativos):\n"
        "   - Use get_available_stocks com filtros corretos\n"
        "   - Exemplo: sector='Finance' para bancos\n"
        "   - Exemplo: sector='Energy Minerals' para energia\n"
        "   - Exemplo: sort='volume' para ordenar por volume\n\n"
        "2. Para COTAÇÕES E DADOS:\n"
        "   - Use get_stock_quotes com ticker específico\n"
        "   - Use get_currency_rates com par (USD-BRL, EUR-BRL, etc)\n"
        "   - Use get_crypto_prices com símbolo (BTC, ETH, etc)\n\n"
        "EXEMPLOS DE CONSULTAS CORRETAS:\n"
        "- 'Quais são os bancos mais negociados?' → get_available_stocks(sector='Finance', sort='volume')\n"
        "- 'Ações de energia com maior volume' → get_available_stocks(sector='Energy Minerals', sort='volume')\n"
        "- 'Qual a cotação de PETR4?' → get_stock_quotes(tickers='PETR4')\n"
        "- 'Fundos imobiliários disponíveis' → get_available_stocks(type='fund')\n\n"
        "FORMATO DE RESPOSTA:\n"
        "- Use markdown para formatar\n"
        "- SEMPRE execute as ferramentas MCP para obter dados reais\n"
        "- SEMPRE mostre TODOS os resultados obtidos das ferramentas\n"
        "- Quando listar ativos, mostre em formato de tabela markdown com colunas: Ticker | Nome | Setor (se aplicável)\n"
        "- Se o usuário pedir N itens, mostre EXATAMENTE N itens (ou todos se houver menos)\n"
        "- Formate listas grandes em tabelas markdown com colunas relevantes\n"
        "- Não resuma ou omita resultados - mostre tudo que a ferramenta retornar\n"
        "- Não faça suposições - sempre use as ferramentas para obter dados reais\n"
        "- Não mostre erros internos de ferramentas, apenas resultados úteis\n"
        "- Após executar a ferramenta, SEMPRE mostre a lista completa de resultados"
    )

    server_params = StreamableHTTPClientParams(
        url=brapi_mcp_url,
        headers={"Authorization": f"Bearer {brapi_token}"}
    )

    # Create MCPTools without context manager - it will be managed by the Agent
    brapi_mcp = MCPTools(transport="streamable-http", server_params=server_params)
    
    agent = Agent(
        name="finance-buddy",
        model=model,
        tools=[brapi_mcp],
        instructions=system_prompt,
        markdown=True,
    )
    return agent


def run_sync(agent: Agent, message: str) -> str:
    """
    Versão síncrona para uso no Streamlit.
    Executa o agente e retorna a resposta completa com resultados das ferramentas.
    """
    try:
        # Use agent.run() for synchronous execution without streaming
        result = agent.run(message, stream=False)
        
        # Extract the content from the RunOutput object
        if hasattr(result, 'content'):
            content = result.content
            if content is not None:
                return str(content)
        
        # Fallback para string representation
        return str(result) if result is not None else "Nenhuma resposta disponível"
    except Exception as e:
        import traceback
        error_msg = f"Erro ao processar requisição: {str(e)}"
        print(f"❌ {error_msg}")
        traceback.print_exc()
        return error_msg


# Alias for backward compatibility
build_agent_sync = build_agent
