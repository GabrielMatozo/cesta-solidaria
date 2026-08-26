import json
from datetime import UTC, datetime

import streamlit as st

from src import auth, config, csv_io, db, estoque, scraper_tenda
from src.ui import flash, load_css, render_flash, render_page_header, render_sidebar

load_css()
render_flash()

user = auth.require_login()
if not auth.is_admin(user):
    st.error("Acesso restrito a administradores.")
    st.stop()

with st.sidebar:
    render_sidebar()

render_page_header("Configurações", "Regiões, preços, backup e ações administrativas")

token = auth.get_token()

try:
    regioes = db.listar_regions(token)
    config_atual = {
        "tenda_region_id": db.get_config("tenda_region_id", token),
        "preco_stale_dias": db.get_config("preco_stale_dias", token),
    }
except Exception as e:
    st.error(f"Erro ao carregar configurações: {e}")
    st.stop()

# ===== REGIOES PRE-CONFIGURADAS =====
REGIOES_CIDADES = {
    "000010": "Indaiatuba",
    "000020": "Salto",
    "000030": "Itu",
    "000040": "Campinas",
}

# Garantir que regioes pre-configuradas existem no banco (apenas na 1a visita
# da sessao; nao sobrescreve nomes ja existentes).
if "_regions_seeded" not in st.session_state:
    st.session_state["_regions_seeded"] = True
    try:
        regioes_existentes = db.listar_regions(token)
        ids_existentes = {r["region_id"] for r in regioes_existentes}
        novas_regioes = []
        for rid, nome in REGIOES_CIDADES.items():
            if rid not in ids_existentes:
                novas_regioes.append({"region_id": rid, "nome": nome, "ativo": True})
        if novas_regioes:
            db.upsert_regions(novas_regioes, token)
    except Exception as e:
        st.caption(f"Aviso: não foi possível verificar regiões pré-configuradas ({e}).")

    # Regiao padrao, apenas se nenhuma configuracao existir ainda.
    try:
        if db.get_config("tenda_region_id", token) is None:
            db.set_config("tenda_region_id", config.TENDA_REGION_DEFAULT, token)
    except Exception:
        pass

# ===== SELEÇÃO DE REGIÃO =====
st.markdown("### Região Tenda para preços")

if not regioes:
    st.caption("Nenhuma região cadastrada.")
    st.stop()

# Montar opções: cidades conhecidas primeiro, depois outras
opcoes_regiao = {}
for r in regioes:
    nome = r["nome"]
    rid = r["region_id"]
    opcoes_regiao[f"{nome} ({rid})"] = rid

atual = config_atual["tenda_region_id"] or "000010"

# Encontrar índice atual
chave_atual = None
for chave, rid in opcoes_regiao.items():
    if rid == atual:
        chave_atual = chave
        break

escolha_chave = st.selectbox(
    "Região ativa",
    list(opcoes_regiao.keys()),
    index=list(opcoes_regiao.keys()).index(chave_atual) if chave_atual in opcoes_regiao else 0,
)
escolha_rid = opcoes_regiao[escolha_chave]

if st.button("Salvar região ativa"):
    db.set_config("tenda_region_id", escolha_rid, token)
    st.cache_data.clear()
    flash(f"Região salva: {escolha_chave}")
    st.rerun()

# ===== ADICIONAR REGIÃO MANUAL =====
with st.expander("Adicionar região manualmente"):
    col1, col2, col3 = st.columns(3)
    with col1:
        novo_rid = st.text_input("Código da região (region_id)", placeholder="ex: 000010")
    with col2:
        novo_nome = st.text_input("Nome da região", placeholder="ex: Tenda Salto")
    with col3:
        novo_cep = st.text_input("CEP de referência (opcional)")
    if st.button("Adicionar região"):
        if novo_rid and novo_nome:
            try:
                db.upsert_regions(
                    [{"region_id": novo_rid, "nome": novo_nome, "cep_referencia": novo_cep or None}],
                    token,
                )
                st.cache_data.clear()
                flash(f"Região {novo_nome} adicionada!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao adicionar região: {e}")
        else:
            st.warning("Preencha código e nome da região.")

# ===== ALERTA DE PREÇO DESATUALIZADO =====
st.markdown("### Alerta de preço desatualizado")
dias_input = st.number_input(
    "Dias sem atualização para alertar",
    min_value=1, max_value=30,
    value=int(config_atual['preco_stale_dias'] or config.PRECO_STALE_DIAS_DEFAULT),
)
if st.button("Salvar limite de dias"):
    db.set_config("preco_stale_dias", str(dias_input), token)
    st.cache_data.clear()
    st.success("Limite salvo!")

st.divider()
st.markdown("### Ações administrativas")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Executar Scraper de Preços", type="primary", width='stretch'):
        with st.spinner("Buscando preços no Tenda..."):
            region_id = db.get_config("tenda_region_id", token) or config.TENDA_REGION_DEFAULT
            produtos = db.listar_produtos(token)
            com_token = [p for p in produtos if p.get("token_tenda")]
            if not com_token:
                st.warning("Nenhum produto com token_tenda cadastrado.")
            else:
                cliente_scraper = scraper_tenda.TendaScraper(region_id=region_id)
                barra = st.progress(0)
                atualizados = 0
                erros = 0
                for i, prod in enumerate(com_token):
                    try:
                        if prod.get("termo_busca"):
                            vencedor = cliente_scraper.buscar_mais_barato(
                                prod["termo_busca"], unidade_alvo=prod.get("unidade") or ""
                            )
                            if not vencedor:
                                st.caption(f"{prod['nome']}: nenhum candidato com o mesmo peso; preço mantido")
                                continue
                            preco = vencedor.preco
                            slug_dia = vencedor.slug
                            marca_dia = vencedor.marca or ""
                        else:
                            resultado = scraper_tenda.buscar_preco_produto(prod["token_tenda"], region_id)
                            preco = resultado["preco"]
                            slug_dia = prod["token_tenda"]
                            marca_dia = ""
                        agora = datetime.now(UTC).isoformat()
                        db.inserir_precos_historico([
                            {"produto_id": prod["id"], "preco": preco, "dia": agora[:10], "region_id": region_id}
                        ], token)
                        upsert_data = {
                            "id": prod["id"],
                            "nome": prod["nome"],
                            "marca": marca_dia or prod.get("marca"),
                            "unidade": prod.get("unidade"),
                            "qtd_por_cesta": prod.get("qtd_por_cesta"),
                            "estoque_atual": prod.get("estoque_atual"),
                            "preco_atual": preco,
                            "token_tenda": slug_dia,
                            "url_tenda": f"https://www.tendaatacado.com.br/produto/{slug_dia}",
                            "ativo": prod.get("ativo", True),
                            "ultima_atualizacao_preco": agora
                        }
                        db.upsert_produtos([upsert_data], token)
                        if prod.get("termo_busca"):
                            db.atualizar_produtos([{
                                "id": prod["id"],
                                "token_tenda": slug_dia,
                                "url_tenda": f"https://www.tendaatacado.com.br/produto/{slug_dia}",
                                "marca": marca_dia,
                            }], token)
                        atualizados += 1
                    except Exception as e:
                        erros += 1
                        st.warning(f"Erro em {prod['nome']}: {e}")
                    barra.progress((i + 1) / len(com_token))
                st.success(f"Scraper concluído: {atualizados} atualizados, {erros} erros.")
            st.cache_data.clear()

with col2:
    if st.button("Gerar Backup", type="secondary", width='stretch'):
        with st.spinner("Gerando backup das tabelas..."):
            # profiles fica de fora: contém dados de contas e o arquivo
            # fica no disco sem controle de acesso.
            tabelas = {
                "produtos": db.listar_tabela("produtos", token),
                "precos_historico": db.listar_tabela("precos_historico", token),
                "compras": db.listar_tabela("compras", token),
                "regions": db.listar_tabela("regions", token),
                "config": db.listar_tabela("config", token),
            }
            backup_json = json.dumps(tabelas, ensure_ascii=False, default=str, indent=2)
            st.download_button(
                "Baixar backup.json",
                backup_json,
                f"backup_cesta_solidaria_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json",
                "application/json",
                width='stretch',
            )
            st.success("Backup pronto para download (tabela profiles excluída).")

with col3:
    if st.button("Popular Dados Iniciais (Seed)", type="secondary", width='stretch'):
        with st.spinner("Importando seed/produtos_initial.csv..."):
            # Garantir região padrão sem sobrescrever nomes existentes.
            try:
                ids_existentes = {r["region_id"] for r in db.listar_regions(token)}
                if config.TENDA_REGION_DEFAULT not in ids_existentes:
                    db.upsert_regions([{
                        "region_id": config.TENDA_REGION_DEFAULT,
                        "nome": "Indaiatuba",
                        "ativo": True,
                    }], token)
                if db.get_config("tenda_region_id", token) is None:
                    db.set_config("tenda_region_id", config.TENDA_REGION_DEFAULT, token)
            except Exception as e:
                st.warning(f"Aviso ao configurar região padrão: {e}")

            import os
            csv_path = "seed/produtos_initial.csv"
            if not os.path.exists(csv_path):
                st.error(f"Arquivo não encontrado: {csv_path}")
            else:
                with open(csv_path, encoding="utf-8") as f:
                    df = csv_io.ler_csv(f.read())
                cols = ["nome", "marca", "unidade", "qtd_por_cesta", "estoque_atual",
                        "preco_atual", "token_tenda", "url_tenda", "termo_busca", "ativo"]
                for col in cols:
                    if col not in df.columns:
                        df[col] = None
                df["qtd_por_cesta"] = df["qtd_por_cesta"].fillna(1)
                df["estoque_atual"] = df["estoque_atual"].fillna(0)
                df["ativo"] = df["ativo"].map(estoque.normalizar_ativo).where(df["ativo"].notna(), True)
                if "id" in df.columns:
                    df["id"] = df["id"].where(df["id"].notna(), None)

                rows = df[["id"] + cols if "id" in df.columns else cols].to_dict("records")
                rows = estoque.limpar_nan(rows)
                try:
                    # ignore_duplicates: seed nao destrói estado operacional
                    # (estoque/preço) de produtos que já existem no banco.
                    db.upsert_produtos(rows, token, ignore_duplicates=True)
                    st.cache_data.clear()
                    flash(f"Seed concluído: {len(rows)} produtos importados (existentes preservados).")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro no seed: {e}")

# Nova linha: Descoberta automática de tokens
st.markdown("### Descoberta Automática de Tokens Tenda")
st.caption("Busca automaticamente o token_tenda no site do Tenda para produtos sem token.")

if st.button("Descobrir Tokens Tenda", type="secondary", width='stretch'):
    with st.spinner("Buscando tokens no Tenda Atacado..."):
        produtos = db.listar_produtos(token)
        sem_token = [p for p in produtos if p.get("ativo") and not p.get("token_tenda")]
        if not sem_token:
            st.info("Todos os produtos ativos já possuem token_tenda.")
        else:
            region_id = db.get_config("tenda_region_id", token) or config.TENDA_REGION_DEFAULT
            barra = st.progress(0)
            atualizados = 0
            erros = 0
            erros_detalhes = []
            tokens_encontrados = []
            for i, prod in enumerate(sem_token):
                try:
                    token_tenda = scraper_tenda.buscar_token_por_nome(prod["nome"], region_id)
                    if token_tenda:
                        upsert_data = {
                            "id": prod["id"],
                            "nome": prod["nome"],
                            "marca": prod.get("marca"),
                            "unidade": prod.get("unidade"),
                            "qtd_por_cesta": prod.get("qtd_por_cesta"),
                            "estoque_atual": prod.get("estoque_atual"),
                            "preco_atual": prod.get("preco_atual"),
                            "token_tenda": token_tenda,
                            "url_tenda": prod.get("url_tenda"),
                            "ativo": prod.get("ativo", True),
                            "ultima_atualizacao_preco": None
                        }
                        db.upsert_produtos([upsert_data], token)
                        atualizados += 1
                        tokens_encontrados.append({"nome": prod["nome"], "token": token_tenda})
                    else:
                        erros += 1
                        erros_detalhes.append(f"{prod['nome']}: nenhum resultado na busca")
                except Exception as e:
                    erros += 1
                    erros_detalhes.append(f"{prod['nome']}: {type(e).__name__}: {e}")
                barra.progress((i + 1) / len(sem_token))
            st.cache_data.clear()
            # Store results in session_state to persist after rerun
            st.session_state["token_discovery_result"] = {
                "atualizados": atualizados,
                "erros": erros,
                "erros_detalhes": erros_detalhes,
                "tokens_encontrados": tokens_encontrados,
            }
            st.rerun()

# Display results from session_state (persists after rerun)
if "token_discovery_result" in st.session_state:
    result = st.session_state.pop("token_discovery_result")
    if result["erros_detalhes"]:
        with st.expander(f"Ver {len(result['erros_detalhes'])} erro(s)"):
            for err in result["erros_detalhes"]:
                st.write(f"- {err}")
    if result["tokens_encontrados"]:
        st.markdown("### Tokens Encontrados")
        for item in result["tokens_encontrados"]:
            st.write(f"- **{item['nome']}**: `{item['token']}`")
    st.success(f"Descoberta concluída: {result['atualizados']} tokens encontrados, {result['erros']} sem resultado.")
