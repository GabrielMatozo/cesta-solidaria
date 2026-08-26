"""Componentes de UI reutilizaveis para Cesta Solidaria."""

import html
import os
import textwrap
from functools import lru_cache

import streamlit as st


@lru_cache(maxsize=1)
def carregar_logo_b64() -> str:
    """Logo cesta.png em base64 (vazio se arquivo ausente)."""
    import base64
    caminho = os.path.join(os.path.dirname(__file__), "..", "assets", "cesta.png")
    try:
        with open(caminho, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except OSError:
        return ""


@st.cache_data(ttl=10)
def carregar_produtos_cached(token):
    """Produtos ativos para as paginas de estoque/simulador."""
    from src import db
    return db.listar_produtos(token)


@st.cache_data(ttl=60)
def carregar_dias_stale_cached(token):
    """Threshold de dias para preco desatualizado (config do banco)."""
    from src import config, db
    return int(db.get_config("preco_stale_dias", token) or config.PRECO_STALE_DIAS_DEFAULT)


def listar_desatualizados(df, dias: int):
    """Linhas com token_tenda cujo preco esta fora do limite de dias."""
    import pandas as pd

    from src import config

    linhas = []
    for _, r in df.iterrows():
        if r.get("token_tenda") and config.preco_desatualizado(
            r.get("ultima_atualizacao_preco"), dias
        ):
            linhas.append(r)
    return pd.DataFrame(linhas) if linhas else pd.DataFrame()


def html_block(raw: str) -> str:
    """Normaliza blocos de HTML multi-linha para uso seguro com st.markdown.

    O parser Markdown do Streamlit trata blocos indentados (4+ espacos) como
    codigo literal. Isso acontece tanto quando o bloco inteiro comeca
    indentado quanto quando uma linha em branco no MEIO do bloco (ex: um
    placeholder interpolado que virou string vazia) e seguida de uma linha
    indentada. Por isso, alem de remover a indentacao comum (dedent) e as
    bordas (strip), tambem removemos linhas inteiramente vazias.
    """
    dedented = textwrap.dedent(raw).strip()
    return "\n".join(line for line in dedented.split("\n") if line.strip())


def load_css():
    """Carrega CSS customizado uma vez por sessao (silencioso)."""
    if "_css_loaded" not in st.session_state:
        try:
            # Tenta varios caminhos possiveis
            base = os.path.dirname(__file__)
            candidates = [
                os.path.join(base, "..", "assets", "style.css"),
                os.path.join(base, "assets", "style.css"),
                os.path.abspath(os.path.join(os.getcwd(), "assets", "style.css")),
            ]
            css_path = None
            for p in candidates:
                p = os.path.abspath(p)
                if os.path.exists(p):
                    css_path = p
                    break
            if css_path:
                with open(css_path) as f:
                    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
                st.session_state["_css_loaded"] = True
        except Exception:
            pass  # Silencioso: CSS opcional, app funciona sem ele


def avatar(nome: str, size: str = "md") -> str:
    """Gera HTML para iniciais do nome (sem avatar)."""
    if not nome:
        iniciais = "U"
    elif "@" in nome and " " not in nome:
        iniciais = nome.split("@")[0][0].upper()
    else:
        iniciais = "".join(p[0].upper() for p in nome.split()[:2])
    iniciais = html.escape(iniciais)
    return f'<div class="avatar avatar-{html.escape(size)}">{iniciais}</div>'


def badge(text: str, variant: str = "neutral") -> str:
    """Gera HTML para badge."""
    return f'<span class="badge badge-{variant}">{html.escape(str(text))}</span>'


_STAT_ICONS = {
    "box": '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="M3.3 7 12 12l8.7-5"/><path d="M12 22V12"/></svg>',
    "alert": '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>',
    "clock": '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    "cart": '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/></svg>',
}


def stat_card(label: str, value: str, icon: str, icon_color: str = "green", badge_html: str = "") -> str:
    """Gera HTML para card de estatistica. icon pode ser chave SVG ou caractere."""
    label = html.escape(str(label))
    value = html.escape(str(value))
    icon_colors = {
        "green": "stat-icon-green",
        "blue": "stat-icon-blue",
        "orange": "stat-icon-orange",
        "red": "stat-icon-red",
    }
    icon_class = icon_colors.get(icon_color, "stat-icon-green")
    icon_html = _STAT_ICONS.get(icon, icon)

    return html_block(f"""
    <div class="stat-card">
        <div class="stat-icon {icon_class}">{icon_html}</div>
        <div class="stat-content">
            <div class="stat-value">{value}</div>
            <div class="stat-label">{label}</div>
            {badge_html}
        </div>
    </div>
    """)


def render_sidebar():
    """Renderiza sidebar profissional com navegacao nativa."""

    from src import auth
    user = auth.get_user()
    if not user:
        return

    logo_b64 = carregar_logo_b64()

    if logo_b64:
        logo_html = f'<div class="sidebar-logo" style="width: 36px; height: 36px; border-radius: 8px; background: url(\'data:image/png;base64,{logo_b64}\') center/cover no-repeat;"></div>'
    else:
        logo_html = '<div class="sidebar-logo" style="width: 36px; height: 36px; border-radius: 8px; background: var(--primary);"></div>'

    nome = html.escape(str(user.get('nome', '') or user.get('email', '') or 'Usuário'))

    st.markdown(html_block(f"""
    <div class="sidebar-header">
        {logo_html}
        <span class="sidebar-title">Cesta Solidária</span>
    </div>
    <div class="sidebar-user">
        <div class="sidebar-user-info">
            <div class="sidebar-user-name">{nome}</div>
            <div class="sidebar-user-role">{'Administrador' if user.get('is_admin') else 'Voluntário'}</div>
        </div>
    </div>
    <div class="sidebar-nav">
    """), unsafe_allow_html=True)

    # Navegação usando st.page_link (nativo do Streamlit)
    pages = [
        ("Dashboard", "pages/0_Dashboard.py"),
        ("Estoque", "pages/1_Estoque.py"),
        ("Simulador", "pages/2_Simulador.py"),
        ("Histórico", "pages/3_Historico.py"),
    ]

    if user.get("is_admin"):
        pages.extend([
            ("Usuários", "pages/4_Usuarios.py"),
            ("Configurações", "pages/5_Config.py"),
        ])

    for label, path in pages:
        st.page_link(path, label=label, width='stretch')

    st.markdown("</div>", unsafe_allow_html=True)

    # Logout
    if st.button("Sair", width='stretch', key="sidebar_logout", type="secondary"):
        from src import auth

        auth.logout()
        st.switch_page("pages/0_Login.py")

    st.markdown(html_block("""
    <div style="padding: 16px; border-top: 1px solid var(--border-light); font-size: 0.75rem; color: var(--text-muted); text-align: center;">
        Cesta Solidária v1.0.0
    </div>
    """), unsafe_allow_html=True)


def render_page_header(titulo: str, subtitulo: str = ""):
    """Renderiza cabecalho padrao das paginas."""
    titulo_seg = html.escape(str(titulo))
    subtitulo_seg = html.escape(str(subtitulo))
    st.markdown(html_block(f"""
    <div style="margin-bottom: 8px;">
        <h1 style="font-size:1.6rem;font-weight:700;margin:0;color:var(--text-primary,#212121);">{titulo_seg}</h1>
        <p style="margin:4px 0 0;color:var(--text-muted,#757575);font-size:0.9rem;">{subtitulo_seg}</p>
    </div>
    """), unsafe_allow_html=True)


def confirmation_dialog(
    titulo: str,
    mensagem: str,
    confirm_label: str = "Confirmar",
    cancel_label: str = "Cancelar",
    key: str = "confirm",
) -> bool:
    """Dialog de confirmacao inline.

    Uso: um botao externo seta ``st.session_state[key] = True``; enquanto o
    flag estiver ativo, este dialog renderiza e retorna True somente quando
    o usuario confirma. Retorna False caso contrario.
    """
    if not st.session_state.get(key):
        return False

    with st.container(border=True):
        st.warning(f"**{html.escape(str(titulo))}** {html.escape(str(mensagem))}")
        col_confirmar, col_cancelar = st.columns(2)
        confirmado = False
        with col_confirmar:
            if st.button(confirm_label, type="primary", key=f"{key}_confirm"):
                st.session_state[key] = False
                confirmado = True
        with col_cancelar:
            if st.button(cancel_label, key=f"{key}_cancel"):
                st.session_state[key] = False
        return confirmado


def flash(message: str, kind: str = "success"):
    """Guarda mensagem para exibir apos o proximo rerun."""
    st.session_state["_flash"] = {"kind": kind, "message": message}


def render_flash():
    """Exibe e consome mensagem pendente de flash (chamar no topo da pagina)."""
    dados = st.session_state.pop("_flash", None)
    if not dados:
        return
    kind = dados.get("kind", "info")
    message = dados.get("message", "")
    if kind == "success":
        st.success(message)
    elif kind == "error":
        st.error(message)
    elif kind == "warning":
        st.warning(message)
    else:
        st.info(message)


