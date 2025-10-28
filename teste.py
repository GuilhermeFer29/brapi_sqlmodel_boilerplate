import os
import sys
import time
import requests

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, os.pardir))
sys.path.append(project_root)


import streamlit as st
from streamlit_extras.colored_header import colored_header
from streamlit_extras.add_vertical_space import add_vertical_space
from streamlit_lottie import st_lottie

from src.llm_interactions import ask_question
from src.config import APP_TITLE, APP_DESCRIPTION, APP_VERSION, VECTOR_DB_PATH # Importe VECTOR_DB_PATH
from src.data_processing import process_and_store_documents 
# --- Configuração da Página Streamlit ---
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
    # theme="dark"
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
        background-color: #1E1E1E !important;
        color: #E0E0E0 !important;
    }
    .stApp {
        background-color: #1E1E1E !important;
        color: #E0E0E0 !important;
    }
    
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Estilos para as mensagens do chat (balões) */
    .stChatMessage [data-testid="stChatMessageContent"] {
        border-radius: 10px;
        padding: 10px;
        margin: 5px 0;
        box-shadow: 0 1px 2px rgba(0,0,0,0.3);
        color: #E0E0E0 !important;
    }
    .stChatMessage.st-emotion-cache-user-message [data-testid="stChatMessageContent"] {
        background-color: #2C3E50 !important; 
    }
    .stChatMessage.st-emotion-cache-assistant-message [data-testid="stChatMessageContent"] {
        background-color: #1F3A3D !important;
    }
    p, li, div {
        color: #E0E0E0 !important;
    }

    /* Estilo para botões */
    .stButton>button {
        background-color: #388E3C;
        color: white;
        border-radius: 8px;
        border: none;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #43A047;
        box-shadow: 0 2px 5px rgba(0,0,0,0.4);
    }

    /* Estilo para labels de selectbox, text input e expander */
    .stSelectbox label, .stTextInput label, .stExpander label {
        color: #B0BEC5 !important;
        font-weight: 500;
    }
    .stTextInput [data-testid="stTextInput"] div div input {
        background-color: #2D2D2D !important;
        color: #E0E0E0 !important;
    }

    /* Sidebar */
    div[data-testid="stSidebar"] {
        background-color: #121212 !important;
        border-right: 1px solid #333333;
        color: #E0E0E0 !important;
    }
    .sidebar-title {
        font-size: 1.2rem;
        font-weight: 600;
        margin-bottom: 1rem;
        color: #90CAF9 !important;
    }
    .clear-button {
        color: #FF5252;
        cursor: pointer;
        text-align: center;
        text-decoration: underline;
        margin-top: 1rem;
    }

    /* Expander "Como usar este assistente" */
    div[data-testid="stExpander"] {
        background-color: #2D2D2D !important;
        border-radius: 5px;
        margin-bottom: 10px;
        border: 1px solid #333333;
    }
    div[data-testid="stExpander"] div[data-testid="stMarkdownContainer"] p,
    div[data-testid="stExpander"] div[data-testid="stMarkdownContainer"] li {
        color: #E0E0E0 !important;
    }
    div[data-testid="stExpander"] .st-emotion-cache-16idsys p {
        color: #90CAF9 !important;
    }

    /* Estilo para st.info (bloco "Sobre") */
    div[data-testid="stInfo"] {
        background-color: #2C3E50 !important;
        color: #E0E0E0 !important;
        border-left: 3px solid #90CAF9 !important;
    }
    div[data-testid="stInfo"] p {
        color: #E0E0E0 !important;
    }
    
    /* Estilo para st.warning (alerta de DB) */
    div[data-testid="stWarning"] {
        background-color: #4A4A20 !important;
        color: #FFD700 !important;
        border-left: 3px solid #FFD700 !important;
    }
    div[data-testid="stWarning"] p {
        color: #FFD700 !important;
    }
    div[data-testid="stWarning"] code {
        background-color: #5A5A30 !important;
        color: #FFFFF0 !important;
    }

    /* Ajustes para o rodapé */
    .footer-text {
        color: #888 !important;
    }

    /* Ajustes para o input de chat */
    div[data-testid="stChatInput"] > div {
        background-color: #2D2D2D !important;
        border-radius: 10px !important;
        padding: 5px !important;
    }
    div[data-testid="stChatInput"] input {
        background-color: #2D2D2D !important;
        color: #E0E0E0 !important;
    }
    div[data-testid="stChatInput"] button {
        background-color: #388E3C !important;
        color: white !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Inicialização de Variáveis de Estado ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_started" not in st.session_state:
    st.session_state.conversation_started = False

# --- Aplicar CSS Personalizado ---
apply_custom_css()

# --- Configuração da Sidebar ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/artificial-intelligence.png", width=80)
    st.markdown("<div class='sidebar-title'>Assistente FastAPI</div>", unsafe_allow_html=True)
    
    st.caption(f"Versão: {APP_VERSION}")
    add_vertical_space(1)
    
    idioma_selecionado = st.selectbox(
        "Idioma da resposta",
        ("Português do Brasil", "English"),
        index=0 # Português como padrão
    )
    
    lottie_coding = load_lottieurl("https://assets5.lottiefiles.com/packages/lf20_fcfjwiyb.json")
    if lottie_coding:
        st_lottie(lottie_coding, height=200)
    
    st.markdown("### Sobre")
    st.info(
        "Este assistente usa tecnologia RAG para responder suas dúvidas sobre FastAPI com base em documentação oficial."
    )
    
    if st.button("Limpar Histórico", use_container_width=True):
        clear_chat_history()
    
    st.markdown("---")
    st.caption("Desenvolvido por Guilherme Fernandes do Bem")
    st.caption("[LinkedIn](https://linkedin.com/in/guilherme-fernandes-do-bem)")

# --- Funções de Chat ---
def clear_chat_history():
    """Limpa o histórico de mensagens e reinicia a conversa."""
    st.session_state.messages = []
    st.session_state.conversation_started = False
    st.rerun()

# --- CONDIÇÃO PARA POPULAR O BANCO DE DADOS NO DEPLOY ---
# Esta função será executada apenas uma vez na primeira vez que o aplicativo for implantado
# ou quando o cache for limpo e o aplicativo for reiniciado no Streamlit Cloud.
@st.cache_resource
def setup_vector_db():
    if not os.path.exists(VECTOR_DB_PATH):
        st.info("Primeira vez carregando a base de conhecimento. Isso pode levar alguns minutos...")
        try:
            process_and_store_documents()
            st.success("Base de conhecimento carregada com sucesso!")
        except Exception as e:
            st.error(f"Erro ao carregar a base de conhecimento: {e}. Verifique seus documentos e chaves de API.")
            st.stop() # Parar a execução se o DB não puder ser populado
    else:
        st.info("Base de conhecimento já carregada.")

# Chame a função de setup ao iniciar o app
setup_vector_db()

# --- Conteúdo Principal da Aplicação ---
colored_header(
    label=APP_TITLE,
    description=APP_DESCRIPTION,
    color_name="green-70"
)

# Guia do usuário
with st.expander("📖 Como usar este assistente", expanded=not st.session_state.get("conversation_started", False)):
    st.markdown("""
    ### 👋 Bem-vindo ao Assistente FastAPI!
    
    Este assistente foi projetado para ajudar você com suas dúvidas sobre FastAPI. Siga estas dicas para obter melhores resultados:
    
    1. **Perguntas específicas**: Quanto mais específica for sua pergunta, melhor será a resposta.
    2. **Contexto**: Inclua contexto relevante na sua pergunta para obter respostas mais precisas.
    3. **Código**: Você pode incluir trechos de código nas suas perguntas.
    4. **Idioma**: Selecione o idioma da resposta na barra lateral.
    5. **Histórico**: Suas conversas ficam salvas durante a sessão atual.
    
    **Exemplos de perguntas:**
    - "Como criar um endpoint POST com validação de dados no FastAPI?"
    - "Como configurar autenticação JWT no FastAPI?"
    - "Qual a diferença entre Path e Query parameters no FastAPI?"
    """)

# Exibe o histórico de mensagens no chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Entrada do usuário e lógica de resposta
if user_question := st.chat_input("Pergunte algo sobre FastAPI..."):
    st.session_state.conversation_started = True
    st.session_state.messages.append({"role": "user", "content": user_question})
    
    with st.chat_message("user"):
        st.markdown(user_question)
    
    with st.chat_message("assistant"):
        with st.spinner("Gerando resposta..."):
            try:
                response_content = ask_question(user_question, idioma_desejado=idioma_selecionado)
                st.markdown(response_content)
                st.session_state.messages.append({"role": "assistant", "content": response_content})
            except Exception as e:
                error_message = f"Erro ao gerar a resposta: {str(e)}\n\nPor favor, tente novamente ou verifique as configurações da API/DB."
                st.error(error_message)
                st.session_state.messages.append({"role": "assistant", "content": error_message})

# --- Rodapé ---
st.markdown("---")
footer_cols = st.columns([1, 2, 1])
with footer_cols[1]:
    st.markdown(
        "<div style='text-align: center; color: #888;' class='footer-text'>"
        "Powered by LangChain + DeepSeek + Streamlit"
        "</div>",
        unsafe_allow_html=True
    )