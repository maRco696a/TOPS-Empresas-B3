import streamlit as st
import yfinance as yf
import pandas as pd
from GoogleNews import GoogleNews
from datetime import datetime
import numpy as np

# NÚMERO DE DIAS DE PREGÃO EM 12 MESES (Aprox.)
MMS_LONG_PERIOD = 252 

# --- HELPER: GARANTE O SUFIXO .SA ---
def get_yf_ticker(ticker):
    """Garante o sufixo .SA para B3, mas respeita tickers internacionais (ex: AAPL)."""
    ticker = str(ticker).upper() 
    
    if '.' in ticker:
        return ticker
    
    return f"{ticker}.SA"

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Monitor B3", layout="wide")

st.title("📊 Monitor de Mercado B3: Altas, Baixas e Notícias")
st.markdown("Veja as ações que mais movimentaram hoje e entenda o motivo. Pesquise por outros ativos e veja o histórico de dividendos e fundamentos.")

# --- DISCLOSURE/CONTRIBUIÇÃO NA SIDEBAR (100% PT-BR) ---
with st.sidebar:
    st.header("💖 Apoie o Projeto")
    
    st.markdown("Desenvolvido por **Márcio Augusto Rodrigues de Oliveira**")
    st.markdown("---") 
    
    st.info("Este monitor é mantido com esforço próprio. Sua contribuição nos ajuda a pagar os custos de hospedagem e desenvolver novas funcionalidades.")
    
    st.subheader("Doação via PIX (Copia e Cola)")
    st.caption("Chave PIX para transferência:")
    
    chave_pix = "85a6e7bd-1056-4bf6-8d52-1aa4ab25431a"
    st.code(chave_pix) 
    
    st.caption("Basta copiar a chave acima e colar no seu aplicativo bancário.")
    st.caption("Qualquer valor é bem-vindo.")
    st.caption("Obrigado por seu apoio!")

# --- DISCLAIMER (REFORÇO DA RESPONSABILIDADE) ---
st.warning("⚠️ **Disclaimer:** Este monitor é apenas uma ferramenta de visualização de dados de mercado e notícias. Ele **não constitui recomendação de investimento**. O investidor é totalmente responsável por suas decisões.")

# --- LISTA DE AÇÕES PARA MONITORAR ---
tickers_monitor = [
    'PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'BBAS3.SA',
    'MGLU3.SA', 'VIIA3.SA', 'HAPV3.SA', 'WEGE3.SA', 'RENT3.SA',
    'PRIO3.SA', 'SUZB3.SA', 'GGBR4.SA', 'CSNA3.SA', 'ELET3.SA'
]

# --- FUNÇÃO OTIMIZADA PARA PEGAR DADOS DE COTAÇÃO (Calculo de variação com Pandas) ---
@st.cache_data(ttl=300) 
def carregar_dados_mercado(lista_tickers):
    dados = []
    
    try:
        df_historico = yf.download(lista_tickers, period="2d", progress=False)['Close']
        df_historico = df_historico.dropna(axis=1, how='all')
    except Exception as e:
        st.error(f"Erro ao carregar dados do yfinance: {e}")
        return pd.DataFrame()
    
    if len(df_historico) >= 2:
        variacoes = df_historico.pct_change().iloc[-1] * 100 
        precos_atuais = df_historico.iloc[-1]
    elif len(df_historico) == 1:
        variacoes = pd.Series(0.0, index=df_historico.columns)
        precos_atuais = df_historico.iloc[-1]
    else:
        return pd.DataFrame() 
        
    for ticker in df_historico.columns:
        preco = precos_atuais.get(ticker)
        variacao = variacoes.get(ticker)

        if pd.isna(preco) or pd.isna(variacao):
             continue
            
        dados.append({
            "Ativo": ticker.replace(".SA", ""),
            "Preço (R$)": round(preco, 2),
            "Variação %": round(variacao, 2),
        })
            
    df = pd.DataFrame(dados)
    return df

# --- FUNÇÃO DE ANÁLISE DE SENTIMENTO (SIMULADA) OTIMIZADA ---
def analisar_sentimento_noticia(titulo):
    """Classifica o sentimento do título da notícia com termos mais focados em eventos corporativos."""
    titulo = titulo.lower()
    
    positivas = [
        'alta', 'cresce', 'lucro', 'recorde', 'expansão', 'melhora', 
        'ganhos', 'supera', 'dividendos', 'juros sobre capital próprio', 
        'acordo', 'parceria', 'aprova', 'aquisição', 'receita'
    ]
    negativas = [
        'baixa', 'perdas', 'queda', 'cai', 'recuo', 'prejuízo', 'crise', 
        'problemas', 'alerta', 'risco', 'investigação', 'multa', 'venda de controle', 
        'rejeita', 'adiamento', 'dívida'
    ]
    
    score = 0
    for p in positivas:
        if p in titulo:
            score += 1
    for n in negativas:
        if n in titulo:
            score -= 1 
            
    return score

@st.cache_data(ttl=600) 
def buscar_noticias_e_sentimento(termo):
    """Busca notícias focadas em 'Fato Relevante' e calcula o sentimento médio."""
    googlenews = GoogleNews(lang='pt', region='BR')
    
    query = f'"Fato Relevante" {termo} OR notícias {termo} B3'
    googlenews.search(query) 
    
    results = googlenews.results(sort=True)
    
    noticias_detalhadas = []
    scores = []
    
    for noticia in results[:7]:
        score = analisar_sentimento_noticia(noticia.get('title', ''))
        scores.append(score)
        noticias_detalhadas.append({
            **noticia,
            "score": score
        })
        
    sentimento_medio = np.mean(scores) if scores else 0
    
    if sentimento_medio > 0.3:
        classificacao = "**Otimista**"
        emoji = "🟢"
    elif sentimento_medio < -0.3:
        classificacao = "**Pessimista**"
        emoji = "🔴"
    else:
        classificacao = "**Neutro**"
        emoji = "🟡"
        
    return noticias_detalhadas, classificacao, emoji

# --- FUNÇÕES PARA DIVIDENDOS E FUNDAMENTOS ---
@st.cache_data(ttl=3600 * 4) 
def carregar_dados_dividendos(ticker):
    try: 
        ticker_yf = get_yf_ticker(ticker)
        ativo = yf.Ticker(ticker_yf)
        
        preco_atual = ativo.fast_info.get('last_price') 
        if preco_atual is None:
            preco_atual = ativo.fast_info.get('regular_market_price', 0)
        
        one_year_ago = datetime.now() - pd.DateOffset(years=1)
        actions_df = ativo.actions
        if actions_df.empty:
            total_pago, dy_anual = 0, 0
        else:
            dividendos_df = actions_df.loc[actions_df.index >= one_year_ago]
            pagamentos = dividendos_df[dividendos_df['Dividends'] > 0]
            total_pago = pagamentos['Dividends'].sum()
            
            dy_anual = 0
            if preco_atual and preco_atual != 0:
                dy_anual = (total_pago / preco_atual) * 100
                 
        return preco_atual, total_pago, dy_anual 
        
    except Exception: 
        return 0, 0, 0
        
@st.cache_data(ttl=3600 * 4) 
def carregar_fundamentos_essenciais(ticker):
    try:
        ticker_yf = get_yf_ticker(ticker)
        ativo = yf.Ticker(ticker_yf)
        info = ativo.info
        
        pl = info.get('forwardPE') if info.get('forwardPE') is not None else info.get('trailingPE')
        pvpa = info.get('priceToBook')
        vpa = info.get('bookValue')
        
        return pl, pvpa, vpa
    except Exception:
        return None, None, None

# --- FUNÇÕES PARA O INDICADOR MMS 252 (LONGO PRAZO) ---
@st.cache_data(ttl=3600 * 12) 
def carregar_historico_longo(ticker):
    """Carrega dados para calcular indicadores de longo prazo (MMS 252 e IFR)."""
    ticker_yf = get_yf_ticker(ticker) 
    try:
        data = yf.download(ticker_yf, period="2y", progress=False)['Close']
        return data.dropna()
    except Exception:
        return pd.Series(dtype=float) 

# <<<< FUNÇÃO RENOMEADA PARA EVITAR CONFLITO DE NOME >>>>
def calcular_sinal_mms_252(df_historico):
    """Calcula e retorna o sinal de tendência com base na Média Móvel Simples de 252 dias."""
    
    if df_historico.empty or len(df_historico) < MMS_LONG_PERIOD:
        return f"Dados Insuficientes (Requer {MMS_LONG_PERIOD} dias de histórico)", "⚪", pd.Series(dtype=float)

    mms_series = df_historico.rolling(window=MMS_LONG_PERIOD).mean()
    
    if mms_series.empty or pd.isna(mms_series.iloc[-1]).item():
        return "Dados Insuficientes para Análise", "⚪", pd.Series(dtype=float)

    try:
        preco_atual = df_historico.iloc[-1].item()
        mms_longa = mms_series.iloc[-1].item()
    except Exception:
        return "Erro de Indexação", "⚪", pd.Series(dtype=float)

    diff = (preco_atual - mms_longa) / mms_longa * 100

    if preco_atual > mms_longa * 1.01: 
        sinal = f"**TENDÊNCIA DE ALTA** (Preço está {diff:.2f}% acima da MMS {MMS_LONG_PERIOD})"
        emoji = "🟢"
    elif preco_atual < mms_longa * 0.99: 
        sinal = f"**TENDÊNCIA DE BAIXA** (Preço está {abs(diff):.2f}% abaixo da MMS {MMS_LONG_PERIOD})"
        emoji = "🔴"
    else:
        sinal = f"**TENDÊNCIA NEUTRA** (Preço está próximo da MMS {MMS_LONG_PERIOD})"
        emoji = "🟡"
        
    return sinal, emoji, mms_series


# --- FUNÇÕES PARA O INDICADOR IFR (Índice de Força Relativa) ---
def calcular_rsi(df_historico, window=14):
    """Calcula o Índice de Força Relativa (IFR) para uma janela (padrão 14)."""
    if df_historico.empty or len(df_historico) < window + 1: 
        return pd.Series(dtype=float), None

    delta = df_historico.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.ewm(com=window - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=window - 1, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan) 
    rsi_series = 100 - (100 / (1 + rs))

    if not rsi_series.empty:
        try:
            rsi_last_value = rsi_series.iloc[-1].item() 
            if not pd.isna(rsi_last_value):
                rsi_atual = rsi_last_value
            else:
                rsi_atual = None
        except (ValueError, IndexError, AttributeError): 
            rsi_atual = None
    else:
        rsi_atual = None
    
    return rsi_series, rsi_atual

def calcular_sinal_rsi(rsi_atual):
    """Interpreta o sinal de sobrecompra/sobrevenda do IFR."""
    if pd.isna(rsi_atual) or rsi_atual is None:
        return "Dados Insuficientes para IFR", "⚪"

    if rsi_atual > 70:
        sinal = f"**SOBRECOMPRA** (IFR = {rsi_atual:.2f}). Risco de correção."
        emoji = "⚠️"
    elif rsi_atual < 30:
        sinal = f"**SOBREVENDA** (IFR = {rsi_atual:.2f}). Potencial de recuperação."
        emoji = "📈"
    else:
        sinal = f"**NEUTRO** (IFR = {rsi_atual:.2f}). Sem sinal extremo de sobrecompra/venda."
        emoji = "⚪"
        
    return sinal, emoji


# --- CARREGANDO E EXIBINDO DADOS INICIAIS ---
with st.spinner('Carregando cotações das Blue Chips...'):
    df_mercado = carregar_dados_mercado(tickers_monitor)

if not df_mercado.empty:
    def color_change(val):
        color = 'green' if val > 0 else 'red' if val < 0 else 'gray'
        return f'color: {color}'
        
    maiores_altas = df_mercado.sort_values(by="Variação %", ascending=False).head(5)
    maiores_baixas = df_mercado.sort_values(by="Variação %", ascending=True).head(5)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🚀 Maiores Altas (Top 5)")
        df_altas_style = maiores_altas.style.applymap(
                color_change, subset=['Variação %']
            ).format({
                "Variação %": "{:+.2f}%", 
                "Preço (R$)": "R$ {:.2f}"
            })
        st.dataframe(df_altas_style, use_container_width=True)

    with col2:
        st.subheader("🔻 Maiores Baixas (Top 5)")
        df_baixas_style = maiores_baixas.style.applymap(
                color_change, subset=['Variação %']
            ).format({
                "Variação %": "{:+.2f}%", 
                "Preço (R$)": "R$ {:.2f}"
            })
        st.dataframe(df_baixas_style, use_container_width=True)

st.divider()

# --- SEÇÃO DE PESQUISA E DETALHES ---
st.header("🕵️‍♂️ Investigar Outros Ativos")

col_input, col_btn = st.columns([3, 1])

with col_input:
    termo_busca = st.text_input("Digite o código do ativo (ex: AZUL4, TOTS3)", "", key="input_busca").strip().upper() 

with col_btn:
    st.markdown("<br>", unsafe_allow_html=True) 
    st.button("🔍 Pesquisar", key="btn_pesquisa", use_container_width=True)

# --- DETERMINAÇÃO DO ATIVO PARA ANÁLISE ---
ativo_analise = None 

if termo_busca:
    ativo_analise = termo_busca
        
elif not df_mercado.empty:
    st.subheader("Ou escolha um ativo da lista:")
    opcoes_select = df_mercado['Ativo'].unique()
    
    if len(opcoes_select) > 0:
        
        if "selectbox_selecionado" not in st.session_state or st.session_state["selectbox_selecionado"] not in opcoes_select:
             st.session_state["selectbox_selecionado"] = opcoes_select[0] 
            
        index_selecionado = list(opcoes_select).index(st.session_state["selectbox_selecionado"])

        ativo_analise = st.selectbox(
            "Escolha um ativo para ver detalhes:", 
            opcoes_select, 
            index=index_selecionado, 
            key="selectbox_selecionado"
        )

# --- BLOCO DE ANÁLISE DETALHADA ---
ticker_valido = False
ativo_analise_display = ativo_analise

if ativo_analise:
    ticker_yf_analise = get_yf_ticker(ativo_analise)
    
    try:
        info_teste = yf.Ticker(ticker_yf_analise).info 
        
        if info_teste and len(info_teste) >= 5 and 'regularMarketPrice' in info_teste: 
            ticker_valido = True
            
            if 'longName' in info_teste:
                 ativo_analise_display = f"{info_teste['longName']} ({ativo_analise})"
            
        else:
            raise ValueError("Ticker não encontrado ou sem dados suficientes.")
            
    except Exception:
        st.error(f"Não foi possível encontrar o ativo **{ativo_analise}** na base de dados do mercado. Verifique o código.")
        ticker_valido = False 
        
if ticker_valido:
    st.markdown(f"### Detalhes e Fundamentos de **{ativo_analise_display}**")
    
    def formatar_valor(valor, formato, eh_pl=False):
        if eh_pl:
            if valor is None or np.isinf(valor) or valor <= 0:
                return "N/A"
        elif valor is None or np.isinf(valor):
            return "N/A"
        
        try:
            return formato.format(valor).replace(',', 'X').replace('.', ',').replace('X', '.')
        except (ValueError, TypeError):
            return "N/A"
            
    # --- DADOS DE COTAÇÃO, DIVIDENDOS E FUNDAMENTOS ---
    preco_actual, total_div, dy_anual = carregar_dados_dividendos(ativo_analise)
    pl, pvpa, vpa = carregar_fundamentos_essenciais(ativo_analise)
    
    # PRIMEIRA LINHA DE MÉTRICAS (Preço e Dividendos)
    st.subheader("Informações de Preço e Renda")
    col_p1, col_p2, col_p3 = st.columns(3) 
    
    with col_p1:
        st.metric(label="Preço Atual (R$)", value=formatar_valor(preco_actual, "R$ {:.2f}"))
        
    with col_p2:
        st.metric(label="Total de Dividendos (12m)", value=formatar_valor(total_div, "R$ {:.2f}"))

    with col_p3:
        st.metric(label="Dividend Yield (DY) Anual", value=formatar_valor(dy_anual, "{:.2f}%"))
        
    st.markdown("---") 

    # SEGUNDA LINHA DE MÉTRICAS (Fundamentos e Sentimento)
    st.subheader("Indicadores de Valorização e Sentimento")
    
    noticias_detalhe, classificacao_sentimento, emoji_sentimento = buscar_noticias_e_sentimento(ativo_analise)

    col_f1, col_f2, col_f3, col_s = st.columns(4) 
    
    with col_f1:
        st.metric(label="P/L (Preço/Lucro)", value=formatar_valor(pl, "{:.2f}x", eh_pl=True))

    with col_f2:
        st.metric(label="P/VPA (Preço/Valor Patrimonial)", value=formatar_valor(pvpa, "{:.2f}x"))
        
    with col_f3:
        st.metric(label="VPA (Valor Patrimonial/Ação)", value=formatar_valor(vpa, "R$ {:.2f}"))
        
    with col_s:
        st.metric(label="Análise Sentimento (IA)", value=f"{emoji_sentimento} {classificacao_sentimento}")
        
    st.divider()
    
    ## --- BLOCO DE ANÁLISE TÉCNICA (MMS 252) ---
    st.subheader(f"📈 Análise Técnica ({ativo_analise})")
    
    # 1. Carrega histórico de LONGO prazo (2 anos)
    df_historico_longo = carregar_historico_longo(ativo_analise)
    
    # 2. MMS 252 (CHAMADA DA FUNÇÃO RENOMEADA)
    sinal_mms, emoji_mms, mms_series = calcular_sinal_mms_252(df_historico_longo)
        
    st.markdown(f"#### {emoji_mms} Média Móvel Simples de {MMS_LONG_PERIOD} Dias (Tendência Anual)")
    st.markdown(sinal_mms)
    st.caption("Compara o preço atual com a média dos últimos 12 meses (252 dias úteis) para identificar a tendência primária de longo prazo.")
    
    # EXIBIÇÃO DO GRÁFICO MMS 252
    if not df_historico_longo.empty and len(mms_series) > 0 and not mms_series.empty:
        st.markdown(f"##### Visualização da Tendência (MMS {MMS_LONG_PERIOD})")
        
        df_plot = pd.DataFrame({
            'Preço de Fechamento': df_historico_longo.values.ravel(),
            f'MMS {MMS_LONG_PERIOD} Períodos': mms_series.values.ravel() 
        }, index=df_historico_longo.index)
        
        df_plot = df_plot.dropna() 
        
        if not df_plot.empty:
            st.line_chart(df_plot.tail(MMS_LONG_PERIOD)) 
        else:
            st.info(f"Não foi possível carregar dados suficientes para plotar o MMS {MMS_LONG_PERIOD}.")

    else:
        st.info(f"Não foi possível carregar dados suficientes para calcular e plotar o MMS {MMS_LONG_PERIOD} (Requer 252 dias).")


    st.markdown("---")
    
    # --- BLOCO DE ANÁLISE IFR ---
    rsi_series, rsi_atual = calcular_rsi(df_historico_longo)
    sinal_rsi, emoji_rsi = calcular_sinal_rsi(rsi_atual)

    st.markdown(f"#### {emoji_rsi} Índice de Força Relativa (IFR 14)")
    st.markdown(sinal_rsi)
    st.caption("Valores acima de 70 indicam sobrecompra; abaixo de 30, sobrevenda.")
    
    # Exibição do Gráfico IFR
    if not rsi_series.empty:
        st.markdown("##### Visualização do IFR")
        
        df_rsi_plot = pd.DataFrame({
            'IFR 14': rsi_series.values.ravel(),
            'Sobrecompra (70)': np.full(len(rsi_series), 70),
            'Sobrevenda (30)': np.full(len(rsi_series), 30)
        }, index=rsi_series.index).tail(60)

        st.line_chart(df_rsi_plot)
    else:
        st.info("Não foi possível carregar dados suficientes para calcular e exibir o IFR.")
        
    st.divider()
    
    # --- NOTÍCIAS (Fatos Relevantes) ---
    st.subheader(f"📰 Últimas Notícias sobre {ativo_analise_display} (Foco em Fatos Relevantes)")
    
    if noticias_detalhe:
        for noticia in noticias_detalhe:
            
            score = noticia.get("score", 0)
            if score > 0:
                score_str = f"| **Sentimento:** Positivo ({score})"
            elif score < 0:
                score_str = f"| **Sentimento:** Negativo ({score})"
            else:
                score_str = "| **Sentimento:** Neutro"

            with st.expander(f"📰 {noticia['title']}"):
                fonte = noticia.get('media', 'Fonte Desconhecida')
                data = noticia.get('date', 'Data Desconhecida')
                
                st.write(f"**Fonte:** {fonte}")
                st.write(f"**Data:** {data} {score_str}")
                st.markdown(f"[Ler notícia completa]({noticia['link']})")
    else:
        st.warning(f"Nenhuma notícia recente focada em Fato Relevante encontrada para {ativo_analise_display}.")

else:
    if df_mercado.empty:
        st.error("Não foi possível carregar os dados iniciais do mercado. Verifique sua conexão ou tente mais tarde.")
    else:
        st.info("Digite um código de ativo ou escolha um da lista para iniciar a análise detalhada.")