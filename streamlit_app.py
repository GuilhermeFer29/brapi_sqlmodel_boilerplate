from __future__ import annotations

import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from app.agent.mcp_agent import build_agent_sync, run_sync

# --- Configuração da Página Streamlit ---
st.set_page_config(
    page_title="Assistente Financeiro IA",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Funções Auxiliares ---
@st.cache_data
def load_lottieurl(url: str):
    """Carrega dados de animações Lottie de uma URL."""
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

def apply_custom_css():
    """Aplica estilos CSS personalizados para o modo escuro e layout do chat."""
    st.markdown("""
    <style>
    /* Estilos globais e de fundo */
    body {
        background-color: #0E1117 !important;
        color: #FAFAFA !important;
    }
    .stApp {
        background-color: #0E1117 !important;
        color: #FAFAFA !important;
    }
    
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }

    /* Estilos para as mensagens do chat (balões) */
    .stChatMessage [data-testid="stChatMessageContent"] {
        border-radius: 15px;
        padding: 15px;
        margin: 8px 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.4);
        color: #FAFAFA !important;
    }
    .stChatMessage.st-emotion-cache-user-message [data-testid="stChatMessageContent"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border-left: 4px solid #667eea;
    }
    .stChatMessage.st-emotion-cache-assistant-message [data-testid="stChatMessageContent"] {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%) !important;
        border-left: 4px solid #0f3460;
    }
    p, li, div {
        color: #FAFAFA !important;
    }

    /* Estilo para código dentro das mensagens */
    code {
        background-color: #1e1e1e !important;
        color: #ce9178 !important;
        padding: 2px 6px;
        border-radius: 4px;
    }
    
    pre {
        background-color: #1e1e1e !important;
        padding: 10px;
        border-radius: 8px;
        border-left: 3px solid #667eea;
    }

    /* Estilo para botões */
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }

    /* Sidebar */
    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%) !important;
        border-right: 1px solid #0f3460;
        color: #FAFAFA !important;
    }
    .sidebar-title {
        font-size: 1.5rem;
        font-weight: 700;
        margin-bottom: 1rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    /* Expander */
    div[data-testid="stExpander"] {
        background-color: #1a1a2e !important;
        border-radius: 10px;
        margin-bottom: 15px;
        border: 1px solid #0f3460;
    }
    div[data-testid="stExpander"] div[data-testid="stMarkdownContainer"] p,
    div[data-testid="stExpander"] div[data-testid="stMarkdownContainer"] li {
        color: #FAFAFA !important;
    }

    /* Estilo para st.info */
    div[data-testid="stInfo"] {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%) !important;
        color: #FAFAFA !important;
        border-left: 4px solid #667eea !important;
        border-radius: 8px;
    }
    div[data-testid="stInfo"] p {
        color: #FAFAFA !important;
    }
    
    /* Estilo para st.success */
    div[data-testid="stSuccess"] {
        background-color: #1a3d2e !important;
        color: #4ade80 !important;
        border-left: 4px solid #4ade80 !important;
        border-radius: 8px;
    }
    
    /* Estilo para st.error */
    div[data-testid="stError"] {
        background-color: #3d1a1a !important;
        color: #f87171 !important;
        border-left: 4px solid #f87171 !important;
        border-radius: 8px;
    }

    /* Input de chat */
    div[data-testid="stChatInput"] > div {
        background-color: #1a1a2e !important;
        border-radius: 15px !important;
        padding: 8px !important;
        border: 2px solid #0f3460 !important;
    }
    div[data-testid="stChatInput"] input {
        background-color: #1a1a2e !important;
        color: #FAFAFA !important;
        font-size: 1rem;
    }
    div[data-testid="stChatInput"] button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border-radius: 10px !important;
    }

    /* Título principal */
    h1 {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-weight: 800;
    }

    /* Métricas */
    div[data-testid="stMetric"] {
        background-color: #1a1a2e;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #0f3460;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Inicialização de Variáveis de Estado ---
if "agent" not in st.session_state:
    with st.spinner("🚀 Inicializando assistente financeiro..."):
        try:
            st.session_state.agent = build_agent_sync()
        except Exception as e:
            st.error(f"❌ Falha ao iniciar agente: {e}")
            st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "conversation_started" not in st.session_state:
    st.session_state.conversation_started = False

# --- Aplicar CSS Personalizado ---
apply_custom_css()

# --- Funções de Chat ---
def clear_chat_history():
    """Limpa o histórico de mensagens e reinicia a conversa."""
    st.session_state.messages = []
    st.session_state.conversation_started = False
    st.rerun()

# --- Configuração da Sidebar ---
with st.sidebar:
    st.markdown("<div class='sidebar-title'>📊 Assistente Financeiro</div>", unsafe_allow_html=True)
    st.caption("Powered by Agno + brapi MCP")
    
    st.markdown("---")
    
    # Animação Lottie
    try:
        lottie_finance = load_lottieurl("https://lottie.host/d7956a2b-3b5d-4b6e-ae8a-65b8d0e0f7a3/cWKLGh6eKd.json")
        if lottie_finance:
            from streamlit_lottie import st_lottie
            st_lottie(lottie_finance, height=200)
    except:
        st.image("https://img.icons8.com/fluency/96/stock-market.png", width=100)
    
    st.markdown("### 🎯 Sobre")
    st.info(
        "Assistente de IA especializado em análise financeira do mercado brasileiro. "
        "Consulte cotações, analise ações, compare setores e muito mais!"
    )
    
    st.markdown("---")
    
    st.markdown("### 📈 Capacidades")
    st.markdown("""
    - ✅ Cotações de ações
    - ✅ Análise setorial
    - ✅ Taxas de câmbio
    - ✅ Criptomoedas
    - ✅ Dados de inflação
    - ✅ Taxa Selic
    """)
    
    st.markdown("---")
    
    # Estatísticas da sessão
    if st.session_state.messages:
        user_msgs = len([m for m in st.session_state.messages if m["role"] == "user"])
        st.metric("Perguntas feitas", user_msgs)
    
    st.markdown("---")
    
    if st.button("🗑️ Limpar Histórico", use_container_width=True):
        clear_chat_history()
    
    st.markdown("---")
    st.caption("Desenvolvido com ❤️")
    st.caption("brapi.dev | Agno AI")

# --- Conteúdo Principal ---
st.title("📊 Assistente Financeiro Inteligente")
st.caption("Análise de mercado com IA • Dados em tempo real da B3")

# Guia do usuário
with st.expander("📖 Como usar este assistente", expanded=not st.session_state.get("conversation_started", False)):
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 👋 Bem-vindo!
        
        Este assistente foi projetado para ajudar você com análises financeiras do mercado brasileiro.
        
        **Como obter melhores resultados:**
        1. 🎯 Seja específico nas perguntas
        2. 📊 Mencione os símbolos das ações (PETR4, VALE3, etc)
        3. 🔍 Use filtros setoriais quando necessário
        4. 📈 Peça comparações e análises
        """)
    
    with col2:
        st.markdown("""
        ### 💡 Exemplos de Perguntas
        
        **Cotações:**
        - "Qual a cotação da PETR4?"
        - "Mostre o histórico de VALE3 nos últimos 3 meses"
        
        **Análise Setorial:**
        - "Quais são os bancos mais negociados?"
        - "Mostre as ações de energia com maior volume"
        
        **Comparações:**
        - "Compare PETR4 com o setor de energia"
        - "Qual é a taxa de câmbio USD-BRL?"
        """)

st.markdown("---")

# Exibe o histórico de mensagens no chat
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar="👤" if message["role"] == "user" else "🤖"):
        st.markdown(message["content"])

# Entrada do usuário e lógica de resposta
if user_question := st.chat_input("💬 Pergunte sobre ações, câmbio, criptomoedas..."):
    st.session_state.conversation_started = True
    st.session_state.messages.append({"role": "user", "content": user_question})
    
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_question)
    
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("🔍 Analisando dados..."):
            try:
                response_content = run_sync(st.session_state.agent, user_question)
                st.markdown(response_content)
                st.session_state.messages.append({"role": "assistant", "content": response_content})
            except Exception as e:
                error_message = f"❌ Erro ao gerar a resposta: {str(e)}\n\nPor favor, tente novamente ou verifique as configurações."
                st.error(error_message)
                st.session_state.messages.append({"role": "assistant", "content": error_message})

# --- Rodapé ---
if not st.session_state.messages:
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; padding: 20px;'>
        <h3>🚀 Comece sua análise agora!</h3>
        <p>Digite uma pergunta no campo acima para começar a explorar o mercado financeiro brasileiro.</p>
    </div>
    """, unsafe_allow_html=True)
