import html
import time

import streamlit as st

from src import auth, config, db
from src.ui import (
    badge,
    html_block,
    load_css,
    render_page_header,
    render_sidebar,
    stat_card,
)

load_css()

user = auth.require_login()

# ===== SIDEBAR =====
with st.sidebar:
    render_sidebar()

# ===== HEADER =====
render_page_header(
    f"Bem-vindo, {user.get('nome', '').split()[0] if user.get('nome') else 'Usuário'}!",
    "Visão geral do seu projeto Cesta Solidária",
)

# ===== CARREGAR DADOS =====
token = auth.get_token()

@st.cache_data(ttl=10)
def carregar_dashboard(token):
    produtos = db.listar_produtos(token)
    compras = db.listar_compras(token, limite=50)
    regioes = db.listar_regions(token)
    regiao_ativa = db.get_config("tenda_region_id", token) or config.TENDA_REGION_DEFAULT
    dias_stale = int(db.get_config("preco_stale_dias", token) or config.PRECO_STALE_DIAS_DEFAULT)
    compras_mes = db.contar_compras_desde(token, time.strftime("%Y-%m-01"))
    return produtos, compras, regioes, regiao_ativa, dias_stale, compras_mes

with st.spinner("Carregando dashboard..."):
    try:
        produtos, compras, regioes, regiao_ativa, dias_stale, compras_mes = carregar_dashboard(token)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        st.stop()

# ===== CALCULAR ESTATISTICAS =====
total_produtos = len(produtos)
estoque_baixo = sum(1 for p in produtos if p.get("estoque_atual", 0) <= p.get("qtd_por_cesta", 1) * 2 and p.get("ativo"))
sem_token = sum(1 for p in produtos if not p.get("token_tenda") and p.get("ativo"))
precos_velhos = 0
for p in produtos:
    if p.get("token_tenda") and p.get("ultima_atualizacao_preco") and config.preco_desatualizado(
        p["ultima_atualizacao_preco"], dias_stale
    ):
        precos_velhos += 1

# ===== STATS CARDS =====
cols = st.columns(4)
with cols[0]:
    st.markdown(stat_card("Produtos Cadastrados", str(total_produtos), "box", "green"), unsafe_allow_html=True)
with cols[1]:
    st.markdown(stat_card("Estoque Baixo", str(estoque_baixo), "alert", "orange", badge(f"{estoque_baixo} itens", "warning") if estoque_baixo else ""), unsafe_allow_html=True)
with cols[2]:
    st.markdown(stat_card("Preços Desatualizados", str(precos_velhos), "clock", "red" if precos_velhos else "green", badge(f"{precos_velhos} itens", "error") if precos_velhos else ""), unsafe_allow_html=True)
with cols[3]:
    st.markdown(stat_card("Compras Este Mês", str(compras_mes), "cart", "blue"), unsafe_allow_html=True)

# ===== ACOES RAPIDAS =====
st.markdown("### Ações Rápidas")
botoes_rapidos = [
    ("Novo Produto", "pages/1_Estoque.py", "quick_novo"),
    ("Simular Cesta", "pages/2_Simulador.py", "quick_simular"),
    ("Ver Histórico", "pages/3_Historico.py", "quick_historico"),
]
if auth.is_admin(user):
    botoes_rapidos.append(("Configurações", "pages/5_Config.py", "quick_config"))

cols_rapidas = st.columns(len(botoes_rapidos))
for col, (label, destino, chave) in zip(cols_rapidas, botoes_rapidos, strict=False):
    with col:
        if st.button(label, width='stretch', key=chave):
            st.switch_page(destino)

# ===== SUGESTOES / ALERTAS =====
st.markdown("### Próximas Ações Sugeridas")

sugestoes = []

if estoque_baixo:
    sugestoes.append({
        "title": f"{estoque_baixo} produtos com estoque baixo",
        "desc": "Verifique o estoque e gere lista de compras no Simulador",
        "action": "pages/1_Estoque.py",
    })

if precos_velhos:
    sugestoes.append({
        "title": f"{precos_velhos} preços desatualizados (>{dias_stale} dias)",
        "desc": "Execute o scraper ou atualize manualmente nas Configurações",
        "action": "pages/5_Config.py",
    })

if sem_token:
    sugestoes.append({
        "title": f"{sem_token} produtos sem token Tenda",
        "desc": "Adicione token_tenda para automatizar preços",
        "action": "pages/1_Estoque.py",
    })

if not compras:
    sugestoes.append({
        "title": "Nenhuma compra registrada ainda",
        "desc": "Faça sua primeira simulação e salve no Simulador",
        "action": "pages/2_Simulador.py",
    })

if not sugestoes:
    sugestoes.append({
        "title": "Tudo em ordem!",
        "desc": "Seu estoque está atualizado e os preços sincronizados",
        "action": None,
    })

for s in sugestoes:
    if s["action"]:
        st.page_link(s["action"], label=s["title"], icon=":material/arrow_forward:", width='stretch')
        st.caption(s["desc"])
    else:
        st.success(f"{s['title']} - {s['desc']}")

# ===== ULTIMAS COMPRAS =====
if compras:
    st.markdown("### Últimas Compras")
    for c in compras[:5]:
        data = c.get("data", "")[:16].replace("T", " ")
        total = c.get("total", 0)
        n_cestas = c.get("num_cestas", 0)
        st.markdown(html_block(f"""
        <div class="card" style="display:flex;justify-content:space-between;align-items:center;padding:12px 16px;margin:8px 0;">
            <div><strong>{n_cestas} cestas</strong> - {data}</div>
            <div style="font-weight:600;color:var(--primary);font-size:1.125rem;">R$ {total:.2f}</div>
        </div>
        """), unsafe_allow_html=True)
else:
    st.info("Nenhuma compra registrada ainda. Faça sua primeira simulação!")

# ===== FOOTER INFO =====
nome_regiao = next((r.get("nome") for r in regioes if r.get("region_id") == regiao_ativa), regiao_ativa)
st.markdown("---")
st.markdown(html_block(f"""
<div class="text-center" style="color:var(--text-muted);font-size:0.8125rem;padding:16px;">
    Última atualização: {time.strftime("%d/%m/%Y %H:%M")} - Região ativa: {html.escape(str(nome_regiao))}
</div>
"""), unsafe_allow_html=True)
