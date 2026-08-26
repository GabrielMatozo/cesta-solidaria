import json
import time

import pandas as pd
import streamlit as st

from src import auth, calc, config, db, pdf
from src.ui import (
    carregar_dias_stale_cached,
    carregar_produtos_cached,
    flash,
    listar_desatualizados,
    load_css,
    render_flash,
    render_page_header,
    render_sidebar,
)

load_css()
render_flash()

user = auth.require_login()

with st.sidebar:
    render_sidebar()

render_page_header("Simulador de Cestas", "Calcule cestas, gere lista de compras e PDF")

token = auth.get_token()

# ===== CARREGAR PRODUTOS =====
carregar_produtos = carregar_produtos_cached
carregar_dias_stale = carregar_dias_stale_cached

with st.spinner("Carregando produtos..."):
    df = pd.DataFrame(carregar_produtos(token))

if df.empty:
    st.warning("Estoque vazio. Va em **Estoque** para cadastrar produtos.")
    if st.button("Ir para Estoque", type="primary", width='stretch'):
        st.switch_page("pages/1_Estoque.py")
    st.stop()

# ===== CALCULOS BASE =====
df["custo_cesta"] = df["qtd_por_cesta"] * df["preco_atual"]
custo_cesta = calc.custo_cesta(df)
cestas_estoque = calc.cestas_possiveis_estoque(df)

# ===== INPUTS =====
st.markdown("### Parâmetros da Simulação")
col1, col2 = st.columns(2)

with col1:
    cestas_desejadas = st.number_input(
        "Número de cestas desejado",
        min_value=1, value=1, step=1,
        key="sim_cestas",
        help="Quantas cestas você quer montar"
    )

with col2:
    orcamento = st.number_input(
        "Orçamento disponível (R$)",
        min_value=0.0, value=0.0, step=10.0,
        key="sim_orcamento",
        help="Deixe 0 para ignorar limite de orçamento"
    )

# ===== RESULTADOS =====
cestas_orcamento = calc.cestas_possiveis_orcamento(df, orcamento) if orcamento > 0 else float('inf')
faltando = calc.faltando_comprar(df, int(cestas_desejadas))

# Métricas
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Cestas com estoque atual", cestas_estoque)
with col2:
    st.metric("Custo de 1 cesta", f"R$ {custo_cesta:.2f}")
with col3:
    st.metric("Cestas com orçamento", int(cestas_orcamento) if orcamento > 0 else "Ilimitado")

# ===== ALERTAS DE PREÇO (calculados uma unica vez) =====
dias = carregar_dias_stale(token)
desatualizados_rows = listar_desatualizados(df, dias).to_dict("records")
desatualizados = [r["nome"] for r in desatualizados_rows]

if desatualizados:
    st.warning(f"**{len(desatualizados)} produto(s) com preco desatualizado:** " + ", ".join(desatualizados[:5]) + ("..." if len(desatualizados) > 5 else ""))

# ===== O QUE FALTA COMPRAR =====
st.markdown("### Lista de Compras")

if faltando.empty:
    st.success("Estoque completo. Nao precisa comprar nada!")
    st.stop()

# Renomear colunas para compatibilidade com o UI
faltando = faltando.rename(columns={"nome": "produto"})

# Formatar para exibição
faltando_display = faltando.copy()
faltando_display["preco_atual_fmt"] = faltando_display["preco_atual"].apply(lambda x: f"R$ {x:.2f}")
faltando_display["custo_reposicao_fmt"] = faltando_display["custo_reposicao"].apply(lambda x: f"R$ {x:.2f}")

total = sum(faltando["custo_reposicao"])
st.metric("Total da compra", f"R$ {total:.2f}")

st.data_editor(
    faltando_display[["produto", "unidade", "estoque_atual", "qtd_por_cesta", "faltando", "preco_atual_fmt", "custo_reposicao_fmt"]].rename(columns={
        "produto": "Produto", "unidade": "Unid.", "estoque_atual": "Estoque",
        "qtd_por_cesta": "Qtd/Cesta", "faltando": "Comprar", "preco_atual_fmt": "Preço Unit.", "custo_reposicao_fmt": "Custo"
    }),
    width='stretch', hide_index=True, disabled=True,
    column_config={
        "Comprar": st.column_config.NumberColumn("Comprar", format="%.1f"),
    }
)

# ===== ALERTAS DE ESTOQUE =====
if cestas_desejadas > cestas_estoque:
    st.warning(f"Estoque so cobre {cestas_estoque} cesta(s) de {cestas_desejadas} solicitadas. Compre os itens faltantes ou reduza a quantidade.")

if orcamento > 0 and cestas_desejadas > cestas_orcamento:
    st.warning(f"Orcamento so cobre {int(cestas_orcamento)} cesta(s) de {cestas_desejadas} solicitadas.")

# ===== ACOES =====
st.divider()
col1, col2, col3 = st.columns(3)

# PDF (gerado sob demanda; bytes ficam em session_state)
with col1:
    if st.session_state.get("pdf_parametros") != (int(cestas_desejadas), float(orcamento), time.strftime("%d/%m/%Y")):
        if st.button("Preparar PDF", width='stretch', type="secondary"):
            itens_pdf = faltando[["produto", "estoque_atual", "faltando", "custo_reposicao"]].rename(columns={
                "produto": "produto", "estoque_atual": "estoque", "faltando": "comprar", "custo_reposicao": "custo"
            }).to_dict("records")
            try:
                st.session_state["pdf_bytes"] = pdf.gerar_pdf_lista_compras(itens_pdf, total, time.strftime("%d/%m/%Y %H:%M"))
                st.session_state["pdf_parametros"] = (int(cestas_desejadas), float(orcamento), time.strftime("%d/%m/%Y"))
                st.rerun()
            except Exception as e:
                st.error("Erro ao gerar PDF. Tente novamente.")
    else:
        st.download_button(
            "Baixar PDF pronto", st.session_state["pdf_bytes"], "lista_compras.pdf",
            "application/pdf", width='stretch', type="primary"
        )
        if st.button("Regenerar", key="pdf_regenerar"):
            st.session_state.pop("pdf_bytes", None)
            st.session_state.pop("pdf_parametros", None)
            st.rerun()

# Salvar cálculo
with col2:
    if st.button("Salvar cálculo atual", width='stretch', type="secondary"):
        itens_json = json.dumps(faltando[["produto", "qtd_por_cesta", "preco_atual", "custo_reposicao"]].to_dict("records"))
        compra = {
            "orcamento": orcamento if orcamento > 0 else None,
            "num_cestas": int(cestas_desejadas),
            "itens": itens_json,
            "total": total,
            "criado_por": user["user_id"],
        }
        try:
            db.inserir_compra(compra, user["access_token"])
            st.cache_data.clear()
            flash("Cálculo salvo no histórico!")
            st.rerun()
        except Exception as e:
            st.error("Erro ao salvar calculo. Tente novamente.")

# Limpar
with col3:
    if st.button("Limpar simulação", width='stretch'):
        for chave in ("sim_cestas", "sim_orcamento", "pdf_bytes", "pdf_parametros"):
            st.session_state.pop(chave, None)
        st.rerun()

# ===== PRODUTOS COM PREÇO DESATUALIZADO =====
if desatualizados_rows:
    with st.expander(f"{len(desatualizados_rows)} preços desatualizados (clique para ver)"):
        for r in desatualizados_rows:
            data = config.formatar_data_hora(r.get("ultima_atualizacao_preco"))
            st.caption(f"- {r['nome']} - última atualização: {data}")
