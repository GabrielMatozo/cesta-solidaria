import html
import json
import traceback

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
def carregar_compras(user_id, _token):
    return db.listar_compras(_token)

with st.spinner("Carregando histórico..."):
    try:
        compras = carregar_compras(user["user_id"], token)
    except Exception:
        traceback.print_exc()
        st.error("Erro ao carregar dados.")
        st.stop()

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
    lambda r: float(r.get("total") or 0) / float(r.get("num_cestas") or 0) if (r.get("num_cestas") or 0) > 0 else 0, axis=1
)

# ===== FILTROS =====
col1, col2, col3 = st.columns(3)
with col1:
    filtro_data = st.date_input("Período", value=[], key="hist_data")
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
    n_cestas = compra.get("num_cestas") or 0
    data_exibicao = html.escape(str(compra.get("data_exibicao") or "-"))
    total = float(compra.get("total") or 0)
    valor_familia = float(compra.get("valor_familia") or 0)
    with st.expander(f"{n_cestas} cestas - {data_exibicao} - R$ {total:.2f} - R$ {valor_familia:.2f}/família"):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Cestas", n_cestas)
        with col2:
            st.metric("Valor/Família", f"R$ {valor_familia:.2f}")
        with col3:
            st.metric("Total", f"R$ {total:.2f}")

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

if len(df_filtrado) < 2:
    st.caption("Cadastre pelo menos 2 compras para ver os gráficos de evolução.")

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
def carregar_precos(user_id, _token):
    return db.listar_tabela("precos_historico", _token)

try:
    precos = carregar_precos(user["user_id"], token)
except Exception:
    traceback.print_exc()
    st.error("Erro ao carregar historico de precos.")
    st.stop()
if precos:
    precos_df = pd.DataFrame(precos)
    produtos_unicos = precos_df["produto_id"].unique()

    if len(produtos_unicos) > 0:
        try:
            produtos_map = {p["id"]: p["nome"] for p in db.listar_produtos(token)}
        except Exception:
            traceback.print_exc()
            st.error("Erro ao carregar historico de precos.")
            st.stop()
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
    st.info("Nenhum historico de precos ainda. Execute o scraper na pagina Configuracoes.")
