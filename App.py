import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import yfinance as yf
from transformers import pipeline
import pandas as pd
import io

# 1. Configurar o aspeto da página (Isto tem de ser sempre a 1ª linha do Streamlit)
st.set_page_config(page_title="IA Analista de Bolsa", page_icon="🔒", layout="wide")

# -------------------------------------------------------------------
# A. SISTEMA DE LOGIN / SEGURANÇA
# -------------------------------------------------------------------

# Aqui configuramos os acessos. 
# NOTA: Em ambiente profissional as passwords estariam encriptadas (hashing),
# mas para uma ferramenta de uso pessoal, este dicionário direto serve.
credenciais = {
    "credentials": {
        "usernames": {
            "joao": { # O seu nome de utilizador
                "email": "joao@email.com",
                "name": "João (Administrador)",
                # A password TEM de estar em formato Hash (encriptada).
                # Para simplificar agora, a password abaixo é "admin123" encriptada.
                "password": "$2b$12$4L.H/1wQ7pDkE1P2o.7V9eB1uF/tVv2t5v/1x8v.9oG1v.3w.5" 
            }
            # Poderia adicionar mais utilizadores aqui (amigos), separando por vírgulas.
        }
    },
    "cookie": {
        "expiry_days": 30,
        "key": "assinatura_secreta_da_nossa_app", # Chave aleatória para manter o login
        "name": "cookie_login_ia_bolsa"
    },
    "preauthorized": {
        "emails": []
    }
}

# Inicializar o Autenticador
autenticador = stauth.Authenticate(
    credenciais['credentials'],
    credenciais['cookie']['name'],
    credenciais['cookie']['key'],
    credenciais['cookie']['expiry_days'],
    credenciais['preauthorized']
)

# Criar a caixa de Login no ecrã principal
nome, estado_autenticacao, username = autenticador.login('Login', 'main')

if estado_autenticacao == False:
    st.error('Username ou password incorretos.')
    st.stop() # Pára o código aqui. O resto não corre.
elif estado_autenticacao == None:
    st.warning('Por favor, insira o seu username e password.')
    st.stop() # Pára o código aqui enquanto não houver login.

# SE O CÓDIGO CHEGAR AQUI, O UTILIZADOR FEZ LOGIN COM SUCESSO!
# -------------------------------------------------------------------

# 2. Carregar o FinBERT apenas uma vez
@st.cache_resource
def carregar_ia():
    return pipeline("sentiment-analysis", model="ProsusAI/finbert")

# Botão de Logout (colocado na barra lateral para conveniência)
with st.sidebar:
    st.write(f"Bem-vindo(a), *{nome}*")
    autenticador.logout('Sair', 'sidebar')
    st.divider()

st.title("🤖 O Seu Analista Financeiro Pessoal")
st.markdown("Insira uma ação e descubra a nota (0-10) dada pela nossa Inteligência Artificial baseada em fundamentos financeiros e sentimento de mercado.")

classificador_nlp = carregar_ia()

# 3. O nosso Motor (O mesmo de sempre)
def analisar_acao(ticker):
    try:
        acao = yf.Ticker(ticker)
        info = acao.info
        preco = info.get('currentPrice', 0)
        margem = info.get('profitMargins', 0)
        p_l = info.get('trailingPE', 0)
        
        titulos = [n.get('title') for n in acao.news if 'title' in n]
        pontos = 0.0
        if titulos:
            analises = classificador_nlp(titulos[:5])
            for a in analises:
                if a['label'] == 'positive': pontos += 0.5 * a['score']
                elif a['label'] == 'negative': pontos -= 0.6 * a['score']
                
        hist = acao.history(period="6mo")
        tendencia = preco > hist['Close'].iloc[0] if not hist.empty else False
        
        nota = 5.0 + max(-2.5, min(2.5, pontos))
        if margem > 0.15: nota += 1.5
        elif margem < 0: nota -= 2.0
        if 0 < p_l < 20: nota += 1.0
        elif p_l > 40: nota -= 1.0
        if tendencia: nota += 1.0
            
        return {
            "Ticker": ticker.upper(),
            "Preço": f"{preco:.2f}",
            "Margem": f"{margem*100:.1f}%" if margem else "N/A",
            "Nota (0-10)": round(max(0.0, min(10.0, nota)), 1)
        }
    except Exception as e:
        return {"Ticker": ticker.upper(), "Erro": "Não foi possível analisar (verifique o código)."}

# 4. Construir a Interface Visual (Sidebar)
with st.sidebar:
    st.header("⚙️ Configurações")
    ticker_principal = st.text_input("Ação Principal (ex: AAPL, GALP.LS):", "AAPL")
    concorrentes_texto = st.text_input("Concorrentes (separados por vírgula):", "MSFT, GOOGL")
    botao_analisar = st.button("🚀 Iniciar Análise da IA", use_container_width=True)

# 5. O que acontece quando clica no botão "Analisar"
if botao_analisar:
    st.divider()
    lista_tickers = [ticker_principal.strip()]
    if concorrentes_texto:
        lista_tickers += [t.strip() for t in concorrentes_texto.split(",")]
        
    resultados = []
    barra_progresso = st.progress(0)
    estado = st.empty()
    
    for i, t in enumerate(lista_tickers):
        estado.write(f"A recolher dados e ler notícias para **{t}**...")
        resultados.append(analisar_acao(t))
        barra_progresso.progress((i + 1) / len(lista_tickers))
        
    estado.write("✅ Análise Concluída!")
    df = pd.DataFrame(resultados)
    
    if "Nota (0-10)" in df.columns:
        df = df.sort_values(by="Nota (0-10)", ascending=False)
    
    st.dataframe(df, use_container_width=True)
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
        
    st.download_button(
        label="📥 Descarregar Relatório Completo (Excel)",
        data=buffer.getvalue(),
        file_name=f"analise_IA_{ticker_principal}.xlsx",
        mime="application/vnd.ms-excel"
    )
