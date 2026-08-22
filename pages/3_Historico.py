import json

import pandas as pd
import streamlit as st

from src import auth, config, db
from src.ui import load_css, render_flash, render_page_header, render_sidebar

load_css()
render_flash()

user = auth.require_login()

with st.sidebar:
    render_sidebar()

render_page_header("Histórico e Relatórios", "Visualize compras passadas e evolução de preços")

token = auth.get_token()

# ===== CARREGAR COMPRAS =====
@st.cache_data(ttl=10)
def carregar_compras(token):
    return db.listar_compras(token)

with st.spinner("Carregando histórico..."):
    compras = carregar_compras(token)

if not compras:
    st.info("Nenhuma compra registrada ainda. Faça sua primeira simulação no **Simulador**!")
    if st.button("Ir para Simulador", type="primary"):
        st.switch_page("pages/2_Simulador.py")
    st.stop()

# ===== PREPARAR DATAFRAME =====
def parse_itens(raw) -> list | None:
    """Converte o JSON de itens da compra; retorna None se malformado."""
    try:
        dados = json.loads(raw or "[]")
        return dados if isinstance(dados, list) else None
    except (TypeError, ValueError):
        return None


df = pd.DataFrame(compras)
df["itens_lista"] = df["itens"].apply(parse_itens)
df["data_exibicao"] = df["data"].apply(lambda x: config.formatar_data_hora(x) if x else "-")
df["valor_familia"] = df.apply(
    lambda r: r["total"] / r["num_cestas"] if r.get("num_cestas", 0) > 0 else 0, axis=1
)

# ===== FILTROS =====
col1, col2, col3 = st.columns(3)
with col1:
    filtro_data = st.date_input("Periodo", value=[], key="hist_data")
with col2:
    busca = st.text_input("Buscar", placeholder="Filtrar por nome...", key="hist_busca")
with col3:
    ordenar = st.selectbox("Ordenar", ["Mais recentes", "Mais antigas", "Maior valor", "Menor valor"], key="hist_ord")

# Aplicar filtros
df_filtrado = df.copy()
if filtro_data and len(filtro_data) == 2:
    ini, fim = filtro_data
    datas = pd.to_datetime(df_filtrado["data"], errors="coerce", utc=True).dt.date
    df_filtrado = df_filtrado[(datas >= ini) & (datas <= fim)]
if busca:
    busca_lower = busca.lower()
    df_filtrado = df_filtrado[
        df_filtrado.apply(
            lambda r: busca_lower in str(r.get("criado_por", "")).lower() or
                      any(busca_lower in str(item.get("produto", "")).lower()
                          for item in (r.get("itens_lista") or [])),
            axis=1
        )
    ]

# Ordenacao
ord_map = {"Mais recentes": ("data", False), "Mais antigas": ("data", True),
           "Maior valor": ("total", False), "Menor valor": ("total", True)}
col, asc = ord_map[ordenar]
df_filtrado = df_filtrado.sort_values(col, ascending=asc).reset_index(drop=True)

# ===== TABELA DE COMPRAS =====
st.markdown(f"### Compras ({len(df_filtrado)} registros)")

for _, compra in df_filtrado.iterrows():
    with st.expander(f"{compra['num_cestas']} cestas - {compra['data_exibicao']} - R$ {compra['total']:.2f} - R$ {compra['valor_familia']:.2f}/familia"):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Cestas", compra["num_cestas"])
        with col2:
            st.metric("Valor/Familia", f"R$ {compra['valor_familia']:.2f}")
        with col3:
            st.metric("Total", f"R$ {compra['total']:.2f}")

        # Itens
        itens = compra.get("itens_lista")
        if itens:
            itens_df = pd.DataFrame(itens)
            if not itens_df.empty:
                for origem, destino in (
                    ("custo_reposicao", "custo"),
                    ("custo", "custo"),
                    ("preco_atual", "preco_unit"),
                    ("preco_unit", "preco_unit"),
                ):
                    if origem in itens_df.columns and destino not in itens_df.columns:
                        itens_df[destino] = itens_df[origem]
                for col_moeda in ("custo", "preco_unit"):
                    if col_moeda in itens_df.columns:
                        itens_df[col_moeda] = itens_df[col_moeda].apply(
                            lambda x: f"R$ {x:.2f}" if isinstance(x, (int, float)) else x
                        )
                st.dataframe(itens_df, width='stretch', hide_index=True)
        else:
            st.caption(f"Itens: {compra.get('itens', '-')}")

# ===== GRAFICOS =====
st.divider()
st.markdown("### Evolução")

col1, col2 = st.columns(2)

with col1:
    if len(df_filtrado) > 1:
        chart_df = df_filtrado.sort_values("data").reset_index(drop=True)
        st.line_chart(chart_df.set_index("data")["total"], height=300)
        st.caption("Evolução do valor total das compras (filtro aplicado)")

with col2:
    if len(df_filtrado) > 1:
        chart_df = df_filtrado.sort_values("data").reset_index(drop=True)
        st.line_chart(chart_df.set_index("data")["valor_familia"], height=300)
        st.caption("Evolução do valor por família (R$) (filtro aplicado)")

# ===== EVOLUCAO DE PRECOS POR PRODUTO =====
st.markdown("### Evolução de Preços por Produto")

@st.cache_data(ttl=60)
def carregar_precos(token):
    return db.listar_tabela("precos_historico", token)

precos = carregar_precos(token)
if precos:
    precos_df = pd.DataFrame(precos)
    produtos_unicos = precos_df["produto_id"].unique()

    if len(produtos_unicos) > 0:
        produtos_map = {p["id"]: p["nome"] for p in db.listar_produtos(token)}
        prod_id = st.selectbox(
            "Produto",
            produtos_unicos,
            format_func=lambda pid: produtos_map.get(pid, f"ID {pid}"),
            key="hist_prod_preco"
        )

        prod_precos = precos_df[precos_df["produto_id"] == prod_id].sort_values("dia")
        if not prod_precos.empty:
            prod_precos["dia"] = pd.to_datetime(prod_precos["dia"])
            st.line_chart(prod_precos.set_index("dia")["preco"], height=250)
            st.caption(f"Evolução do preço - Região: {prod_precos['region_id'].iloc[0] if 'region_id' in prod_precos.columns else 'N/A'}")
else:
    st.info("Nenhum histórico de preços disponível ainda. Execute o scraper na Configuração.")
