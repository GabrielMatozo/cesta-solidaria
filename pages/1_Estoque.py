import pandas as pd
import streamlit as st

from src import auth, config, csv_io, db, estoque
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

render_page_header("Estoque e Produtos", "Gerencie produtos, estoque, tokens Tenda e preços")

token = auth.get_token()

# ===== CARREGAR DADOS =====
carregar_produtos = carregar_produtos_cached
carregar_dias_stale = carregar_dias_stale_cached


def formulario_novo_produto():
    """Formulario inline de criacao de produto (usado no estoque vazio e no fim da pagina)."""
    with st.expander("Novo Produto", expanded=True), st.form("novo_produto_form"):
        c1, c2 = st.columns(2)
        with c1:
            nome = st.text_input("Nome do produto *", placeholder="Ex: Arroz (5kg)")
            marca = st.text_input("Marca", placeholder="Opcional")
            unidade = st.text_input("Unidade *", placeholder="Ex: 5kg")
        with c2:
            qtd = st.number_input("Qtd por cesta *", min_value=0.1, value=1.0, step=0.5)
            est = st.number_input("Estoque atual *", min_value=0.0, value=0.0, step=0.1)
            preco = st.number_input("Preço unitário (R$) *", min_value=0.0, value=0.0, step=0.01)
        token_t = st.text_input("Token Tenda (opcional)", placeholder="Código do produto no Tenda Atacado")
        url_t = st.text_input("URL Tenda (opcional)", placeholder="https://...")
        termo_b = st.text_input(
            "Termo de busca de marca mais barata (opcional)",
            placeholder="Ex: oleo de soja 900ml",
            help="Se preenchido, a automação diária busca este termo e grava sempre a marca mais barata com o mesmo peso/volume.",
        )
        ativo = st.checkbox("Ativo", value=True)

        if st.form_submit_button("Criar Produto", type="primary"):
            if not nome or not unidade:
                st.error("Nome e unidade são obrigatórios")
            else:
                # Sem chave id: o default (bigserial) so se aplica
                # quando a coluna nao vem no payload.
                novo = [{
                    "nome": nome, "marca": marca or "", "unidade": unidade,
                    "qtd_por_cesta": qtd, "estoque_atual": est, "preco_atual": preco,
                    "token_tenda": token_t or None, "url_tenda": url_t or None,
                    **({"termo_busca": termo_b} if termo_b else {}),
                    "ativo": ativo, "ultima_atualizacao_preco": None
                }]
                try:
                    db.upsert_produtos(novo, user["access_token"])
                    flash(f"Produto {nome} criado!")
                    st.session_state["show_new_form"] = False
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao criar produto: {e}")


with st.spinner("Carregando produtos..."):
    df = pd.DataFrame(carregar_produtos(token))

if df.empty:
    st.info("Nenhum produto cadastrado. Use o formulario abaixo para adicionar o primeiro.")
    formulario_novo_produto()
    st.stop()

# ===== COLUNAS DE EXIBICAO E CALCULOS =====
df["custo_cesta"] = df["qtd_por_cesta"] * df["preco_atual"]

# Filtros
col_a, col_b, col_c, col_d = st.columns([1, 1, 2, 1])
with col_a:
    campo = st.selectbox("Ordenar por", ["nome", "preco_atual", "estoque_atual", "custo_cesta"], key="estoque_ordenar")
with col_b:
    crescente = st.radio("Direção", ["Crescente", "Decrescente"], horizontal=True, key="estoque_dir") == "Crescente"
with col_c:
    texto = st.text_input("Buscar por nome/marca", placeholder="Digite para filtrar...", key="estoque_busca")
with col_d:
    status = st.selectbox("Status do preço", ["todos", "automático", "manual", "desatualizado"], key="estoque_status")

# Aplicar filtros
dias_stale = carregar_dias_stale(token)
df_filtrado = estoque.filtrar(df, texto, status, dias_stale)
df_filtrado = estoque.ordenar(df_filtrado, campo, crescente)

# ===== EXIBIR TABELA =====
if df_filtrado.empty:
    st.info("Nenhum produto encontrado com os filtros atuais.")
else:
    # Preparar dados para exibicao
    display_df = df_filtrado.copy()
    display_df["preco_atual_fmt"] = display_df["preco_atual"].apply(lambda x: f"R$ {x:.2f}")
    display_df["custo_cesta_fmt"] = display_df["custo_cesta"].apply(lambda x: f"R$ {x:.2f}")

    # Status do preço
    def status_preco(row):
        if pd.isna(row.get("token_tenda")):
            return "Manual"
        if config.preco_desatualizado(row.get("ultima_atualizacao_preco"), dias_stale):
            return "Desatualizado"
        return "Automático"

    display_df["status_preco"] = display_df.apply(status_preco, axis=1)
    display_df["ultima_atualizacao"] = display_df["ultima_atualizacao_preco"].apply(
        lambda x: config.formatar_data_hora(x) if pd.notna(x) else "-"
    )

    # Configurar colunas
    colunas_show = ["nome", "marca", "unidade", "qtd_por_cesta", "estoque_atual",
                    "preco_atual_fmt", "custo_cesta_fmt", "status_preco", "ultima_atualizacao"]
    colunas_rename = {
        "nome": "Produto", "marca": "Marca", "unidade": "Unid.",
        "qtd_por_cesta": "Qtd/Cesta", "estoque_atual": "Estoque",
        "preco_atual_fmt": "Preço", "custo_cesta_fmt": "Custo/Cesta",
        "status_preco": "Status", "ultima_atualizacao": "Ult. Atualização"
    }

    st.dataframe(
        display_df[colunas_show].rename(columns=colunas_rename),
        width='stretch',
        hide_index=True,
        column_config={
            "Produto": st.column_config.TextColumn("Produto", width="medium"),
            "Marca": st.column_config.TextColumn("Marca", width="small"),
            "Unid.": st.column_config.TextColumn("Unid.", width="small"),
            "Qtd/Cesta": st.column_config.NumberColumn("Qtd/Cesta", format="%.0f", width="small"),
            "Estoque": st.column_config.NumberColumn("Estoque", format="%.1f", width="small"),
            "Preço": st.column_config.NumberColumn("Preço", format="R$ %.2f", width="small"),
            "Custo/Cesta": st.column_config.NumberColumn("Custo/Cesta", format="R$ %.2f", width="small"),
            "Status": st.column_config.TextColumn("Status", width="medium"),
            "Ult. Atualização": st.column_config.TextColumn("Ult. Atualização", width="medium"),
        }
    )

# ===== ACOES =====
st.divider()
st.markdown("### Importar / Exportar")

# Export row
col_export, col_import = st.columns([1, 1])
with col_export:
    csv_export = csv_io.produtos_to_csv(df)
    st.download_button(
        "Exportar CSV", csv_export, "estoque.csv", "text/csv",
        width='stretch', type="secondary"
    )

with col_import:
    if st.button("Importar CSV", width='stretch', type="secondary"):
        st.session_state["show_import"] = True

# Import uploader (conditional)
if st.session_state.get("show_import"):
    arquivo = st.file_uploader("Selecionar arquivo CSV", type=["csv"], key="estoque_import", label_visibility="collapsed")
    if arquivo:
        conteudo = arquivo.getvalue()
        try:
            texto_import = conteudo.decode("utf-8-sig")
        except UnicodeDecodeError:
            # latin-1 mapeia qualquer byte, nunca falha
            texto_import = conteudo.decode("latin-1")
        if texto_import is not None:
            novo = csv_io.ler_csv(texto_import)
            erros = csv_io.validar_csv(novo)
            if erros:
                st.error("Erros no CSV:")
                for e in erros:
                    st.write(f"- {e}")
            else:
                diff = csv_io.diff_importacao(df, novo)
                if not diff["novos"] and not diff["alterados"]:
                    st.info("Nenhuma alteração detectada.")
                else:
                    st.warning(f"**{len(diff['novos'])} novos produtos**, **{len(diff['alterados'])} alterações**")
                    if diff["alterados"]:
                        with st.expander("Ver alterações"):
                            for alt in diff["alterados"]:
                                st.write(f"- {alt['produto']}: {alt['campo']} {alt['de']} -> {alt['para']}")
                    if st.button("Aplicar importação", type="primary", width='stretch'):
                        # CSV sem coluna id = tudo novo (bigserial resolve)
                        colunas_import = (["id"] if "id" in novo.columns else []) + [
                            "nome", "marca", "unidade", "qtd_por_cesta",
                            "estoque_atual", "preco_atual", "token_tenda",
                            "url_tenda", "termo_busca", "ativo",
                        ]
                        rows = novo[colunas_import].to_dict("records")
                        rows = estoque.limpar_nan(rows)
                        rows = [{k: v for k, v in r.items() if not (k == "id" and v is None)} for r in rows]
                        try:
                            db.upsert_produtos(rows, user["access_token"])
                            flash("Importação aplicada!")
                            st.session_state["show_import"] = False
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao aplicar importação: {e}")

# ===== ALERTAS DE PREÇO DESATUALIZADO =====
desat_df = listar_desatualizados(df, dias_stale)
if not desat_df.empty:
    resumo = ", ".join(
        f"{r['nome']} ({config.formatar_data_hora(r.get('ultima_atualizacao_preco'))})"
        for _, r in desat_df.head(5).iterrows()
    )
    st.warning(f"**Atenção:** {len(desat_df)} produto(s) com preço desatualizado: {resumo}{'...' if len(desat_df) > 5 else ''}")

# ===== FORMULÁRIO NOVO PRODUTO =====
formulario_aberto = bool(st.session_state.get("show_new_form"))
if st.button(
    "Fechar formulário" if formulario_aberto else "Adicionar Novo Produto",
    width='stretch',
):
    st.session_state["show_new_form"] = not formulario_aberto

if st.session_state.get("show_new_form"):
    formulario_novo_produto()
