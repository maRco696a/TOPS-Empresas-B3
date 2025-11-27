import streamlit as st
import yfinance as yf
import pandas as pd
from GoogleNews import GoogleNews
from datetime import datetime
import numpy as np # Adicionado para uso em checagens de valores

# --- HELPER: GARANTE O SUFIXO .SA ---
def get_yf_ticker(ticker):
    """Garante que o ticker da B3 tenha o sufixo .SA, se necessário."""
    # Garante que não haja sufixo duplicado
    ticker = ticker.upper().replace(".SA", "")
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
    st.caption("Qualquer valor é bem-vindo.") # Pequena correção gramatical
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
        # Pega as colunas 'Close' para os 2 últimos dias
        df_historico = yf.download(lista_tickers, period="2d", progress=False)['Close']
        df_historico = df_historico.dropna(axis=1, how='all')
    except Exception as e:
        st.error(f"Erro ao carregar dados do yfinance: {e}")
        return pd.DataFrame()
    
    # Otimização: Cálculo vetorial de variação
    if len(df_historico) >= 2:
        # Calcula a variação percentual entre os 2 dias e pega a última linha (do dia atual em relação ao anterior)
        # Note: A variação do último dia para o penúltimo é a coluna de interesse
        variacoes = df_historico.pct_change().iloc[-1] * 100 
        precos_atuais = df_historico.iloc[-1]
    elif len(df_historico) == 1:
        # Se só tiver um dia de dados (ex: dia de feriado), a variação é zero
        variacoes = pd.Series(0.0, index=df_historico.columns)
        precos_atuais = df_historico.iloc[-1]
    else:
        return pd.DataFrame() 
        
    for ticker in df_historico.columns:
        # Ignora tickers sem dados (usando .get para evitar KeyError e pd.isna para NaN)
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

# --- FUNÇÃO PARA PEGAR DADOS HISTÓRICOS PARA O GRÁFICO ---
@st.cache_data(ttl=3600) 
def carregar_dados_historicos(ticker, periodo):
    try:
        ticker_yf = get_yf_ticker(ticker) # Usando o helper
        data = yf.download(ticker_yf, period=periodo, progress=False)
        return data['Close']
    except Exception:
        # Retorna uma Series vazia ou DataFrame vazio, consistente com a checagem abaixo
        return pd.Series(dtype=float) 

# --- FUNÇÃO PARA PEGAR DADOS DE DIVIDENDOS NO ÚLTIMO ANO ---
@st.cache_data(ttl=3600 * 4) 
def carregar_dados_dividendos(ticker):
    try:
        ticker_yf = get_yf_ticker(ticker) # Usando o helper
        ativo = yf.Ticker(ticker_yf)
        
        # Pega o preço atual de forma mais segura
        preco_atual = ativo.fast_info.get('last_price') 
        if preco_atual is None:
             preco_atual = ativo.fast_info.get('regular_market_price', 0)
        
        # Pega o histórico de dividendos do último ano ('1y')
        # Filtra por data
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
        
# --- FUNÇÃO PARA PEGAR FUNDAMENTOS ESSENCIAIS ---
@st.cache_data(ttl=3600 * 4) 
def carregar_fundamentos_essenciais(ticker):
    try:
        ticker_yf = get_yf_ticker(ticker) # Usando o helper
        ativo = yf.Ticker(ticker_yf)
        info = ativo.info
        
        # P/L: Usa forwardPE (expectativa) se disponível, senão trailingPE (histórico)
        pl = info.get('forwardPE') if info.get('forwardPE') is not None else info.get('trailingPE')
        pvpa = info.get('priceToBook')
        vpa = info.get('bookValue')
        
        return pl, pvpa, vpa
    except Exception:
        # Retorna None para os indicadores em caso de erro
        return None, None, None


# --- FUNÇÃO PARA PEGAR NOTÍCIAS (Busca refinada) ---
@st.cache_data(ttl=600) 
def buscar_noticias(termo):
    googlenews = GoogleNews(lang='pt', region='BR')
    # Busca refinada para o mercado brasileiro
    googlenews.search(f"Notícias {termo} B3") 
    result = googlenews.results(sort=True)
    return result[:5]

# --- CARREGANDO E EXIBINDO DADOS INICIAIS ---
with st.spinner('Carregando cotações das Blue Chips...'):
    df_mercado = carregar_dados_mercado(tickers_monitor)

# Verifica se o DataFrame não está vazio
if not df_mercado.empty:
    # Ordenando
    maiores_altas = df_mercado.sort_values(by="Variação %", ascending=False).head(5)
    maiores_baixas = df_mercado.sort_values(by="Variação %", ascending=True).head(5)

    # --- LAYOUT DAS TABELAS ---
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🚀 Maiores Altas (Top 5)")
        # Corrigido o formatador para aceitar um ponto flutuante em vez de string
        st.dataframe(maiores_altas.style.format({"Variação %": "{:.2f}%", "Preço (R$)": "R$ {:.2f}"}), use_container_width=True)

    with col2:
        st.subheader("🔻 Maiores Baixas (Top 5)")
        st.dataframe(maiores_baixas.style.format({"Variação %": "{:.2f}%", "Preço (R$)": "R$ {:.2f}"}), use_container_width=True)

st.divider()

# --- SEÇÃO DE PESQUISA, DETALHES, GRÁFICO E NOTÍCIAS ---
st.header("🕵️‍♂️ Investigar Outros Ativos")

# 1. Campo de Pesquisa para qualquer ativo
search_col, _ = st.columns([1, 3])
with search_col:
    # O helper get_yf_ticker já cuida do replace e uppercase, mas mantemos o básico na UI
    termo_busca = st.text_input("Digite o código do ativo (ex: AZUL4, TOTS3)", "").strip().upper() 

# Determina o ativo para análise
ativo_analise = None
if termo_busca:
    ativo_analise = termo_busca
else:
    st.subheader("Ou escolha um ativo da lista:")
    # Garante que o df_mercado não esteja vazio antes de tentar o selectbox
    if not df_mercado.empty:
        # Verifica se o ativo da lista está disponível (caso a lista seja grande e o último tenha saído)
        opcoes = df_mercado['Ativo'].unique()
        if len(opcoes) > 0:
            ativo_analise = st.selectbox("Escolha um ativo para ver detalhes:", opcoes, index=0)
    
# Inicia a análise se houver um ativo válido
if ativo_analise:
    ticker_yf_analise = get_yf_ticker(ativo_analise)
    
    # 🌟 Tratamento de Erro para Ticker Inválido
    try:
        # Tentativa de carregar info para testar a validade do ticker
        info_teste = yf.Ticker(ticker_yf_analise).info 
        # Uma checagem adicional: se o dict 'info' for muito pequeno, pode ser um ticker inválido (ex: 'Não Encontrado')
        if not info_teste or len(info_teste) < 5: 
             raise ValueError("Ticker não encontrado ou sem dados suficientes.")
            
    except Exception:
        st.error(f"Não foi possível encontrar o ativo **{ativo_analise}** na base de dados do mercado. Verifique o código.")
        ativo_analise = None # Para parar a execução do bloco
        
if ativo_analise: # Repete a verificação após o teste de erro
    st.markdown(f"### Detalhes e Fundamentos de **{ativo_analise}**")
    
    # --- 3. DADOS DE COTAÇÃO, DIVIDENDOS E FUNDAMENTOS ---
    preco_atual, total_div, dy_anual = carregar_dados_dividendos(ativo_analise)
    pl, pvpa, vpa = carregar_fundamentos_essenciais(ativo_analise)
    
    # CORREÇÃO/OTIMIZAÇÃO: Esta função precisava de ajustes para P/L negativo/zero.
    def formatar_valor(valor, formato, eh_pl=False):
        # Para P/L (eh_pl=True), considera None, inf e valores <= 0 como "N/A"
        if eh_pl:
            if valor is None or np.isinf(valor) or valor <= 0:
                return "N/A"
        # Para outros valores (P/VPA, VPA), considera None ou inf como "N/A"
        elif valor is None or np.isinf(valor):
            return "N/A"
        
        # Formata o valor se for um número válido
        try:
            return formato.format(valor)
        except (ValueError, TypeError):
             return "N/A"
        
    # PRIMEIRA LINHA DE MÉTRICAS (Preço e Dividendos)
    st.subheader("Informações de Preço e Renda")
    col_p1, col_p2, col_p3 = st.columns(3)
    
    with col_p1:
        st.metric(label="Preço Atual (R$)", value=formatar_valor(preco_atual, "R$ {:.2f}"))
        
    with col_p2:
        st.metric(label="Total de Dividendos (12m)", value=formatar_valor(total_div, "R$ {:.2f}"))

    with col_p3:
        st.metric(label="Dividend Yield (DY) Anual", value=formatar_valor(dy_anual, "{:.2f}%"))
        
    st.markdown("---") 

    # SEGUNDA LINHA DE MÉTRICAS (Fundamentos)
    st.subheader("Indicadores de Valorização")
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        # Usando eh_pl=True para tratar P/L de forma especial
        st.metric(label="P/L (Preço/Lucro)", value=formatar_valor(pl, "{:.2f}x", eh_pl=True))

    with col_f2:
        st.metric(label="P/VPA (Preço/Valor Patrimonial)", value=formatar_valor(pvpa, "{:.2f}x"))
        
    with col_f3:
        st.metric(label="VPA (Valor Patrimonial/Ação)", value=formatar_valor(vpa, "R$ {:.2f}"))
        
    st.divider()
    
    # --- GRÁFICO ---
    st.subheader(f"📈 Desempenho Histórico de {ativo_analise}")
    
    periodo_grafico = st.selectbox(
        "Selecione o período do gráfico:",
        options=["1mo", "3mo", "6mo", "1y", "5y", "max"],
        format_func=lambda x: {
            "1mo": "1 Mês", "3mo": "3 Meses", "6mo": "6 Meses",
            "1y": "1 Ano", "5y": "5 Anos", "max": "Máximo"
        }.get(x, x),
        key="periodo_grafico_detalhe"
    )
    
    df_historico_ativo = carregar_dados_historicos(ativo_analise, periodo_grafico)
    
    # Checagem mais robusta (pd.Series também tem .empty)
    if not df_historico_ativo.empty and len(df_historico_ativo) > 1:
        st.line_chart(df_historico_ativo)
    else:
        st.info(f"Não foi possível carregar o histórico de preços para {ativo_analise} no período selecionado.")

    st.divider()
    
    # --- NOTÍCIAS ---
    st.subheader(f"📰 Últimas Notícias sobre {ativo_analise}")
    st.write(f"Buscando últimas notícias sobre **{ativo_analise}** no Google News...")
    
    noticias = buscar_noticias(ativo_analise)
    
    if noticias:
        for noticia in noticias:
            with st.expander(f"📰 {noticia['title']}"):
                # O GoogleNews pode não retornar 'media' ou 'date'
                fonte = noticia.get('media', 'Fonte Desconhecida')
                data = noticia.get('date', 'Data Desconhecida')
                
                st.write(f"**Fonte:** {fonte}")
                st.write(f"**Data:** {data}")
                st.markdown(f"[Ler notícia completa]({noticia['link']})")
    else:
        st.warning(f"Nenhuma notícia recente encontrada para {ativo_analise} nas últimas horas.")

else:
    # Mensagem se o DataFrame inicial estiver vazio (ex: yfinance fora do ar)
    if df_mercado.empty:
        st.error("Não foi possível carregar os dados iniciais do mercado. Tente novamente mais tarde.")
    elif termo_busca:
         # Mensagem mais clara se o usuário tentou buscar, mas falhou
         pass # A mensagem de erro específica já foi exibida acima
    else:
        st.info("Digite um código de ativo ou escolha um da lista para iniciar a análise detalhada.")
