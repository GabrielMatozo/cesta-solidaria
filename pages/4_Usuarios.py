import contextlib

import streamlit as st

from src import auth, db
from src.ui import (
    avatar,
    badge,
    confirmation_dialog,
    flash,
    load_css,
    render_flash,
    render_page_header,
    render_sidebar,
)

load_css()
render_flash()

user = auth.require_login()
if not auth.is_admin(user):
    st.error("Acesso restrito a administradores.")
    st.stop()

with st.sidebar:
    render_sidebar()

render_page_header("Usuários", "Gerencie voluntários e administradores")

token = auth.get_token()

# ===== LISTAR USUARIOS =====
@st.cache_data(ttl=10)
def carregar_usuarios(token):
    return db.listar_profiles(token)

profiles = carregar_usuarios(token)

# ===== LISTA DE USUARIOS =====
st.markdown("### Usuários Cadastrados")

if not profiles:
    st.info("Nenhum usuário além de você.")
else:
    for p in profiles:
        nome = p.get("nome") or "Sem nome"
        email = p.get("email") or "-"
        is_self = p["id"] == user["user_id"]

        col1, col2, col3, col4 = st.columns([1, 3, 2, 1])
        with col1:
            st.markdown(avatar(nome, "sm"), unsafe_allow_html=True)
        with col2:
            st.write(f"**{nome}**")
            st.caption(email)
        with col3:
            role = "Administrador" if p.get("is_admin") else "Voluntário"
            st.markdown(badge(role, "primary" if p.get("is_admin") else "neutral"), unsafe_allow_html=True)
        with col4:
            if not is_self:
                confirm_key = f"confirm_excluir_{p['id']}"
                if st.button("Excluir", key=f"del_{p['id']}", width='stretch'):
                    st.session_state[confirm_key] = True
            else:
                st.markdown('<span class="badge badge-neutral">Você</span>', unsafe_allow_html=True)

# Dialog de confirmacao full-width (fora da coluna estreita)
alvo_exclusao = next((p for p in profiles if st.session_state.get(f"confirm_excluir_{p['id']}")), None)
if alvo_exclusao:
    nome_alvo = alvo_exclusao.get("nome") or alvo_exclusao.get("email") or "este usuário"
    if confirmation_dialog(
        f"Excluir {nome_alvo}?",
        "Esta ação é irreversível. O usuário perderá acesso ao sistema.",
        confirm_label="Excluir", cancel_label="Cancelar", key=f"confirm_excluir_{alvo_exclusao['id']}"
    ):
        try:
            db.excluir_usuario(alvo_exclusao["id"], user["access_token"])
            flash(f"Usuário {nome_alvo} excluído")
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            if "propria conta" in str(e):
                st.error("Você não pode excluir a própria conta.")
            else:
                st.error(f"Erro ao excluir usuário: {e}")

# ===== CRIAR NOVO USUÁRIO =====
st.divider()
st.markdown("### Novo Voluntário")

with st.form("novo_usuario_form"):
    col1, col2 = st.columns(2)
    with col1:
        email = st.text_input("Email *", placeholder="voluntario@email.com")
        nome = st.text_input("Nome *", placeholder="Nome completo")
    with col2:
        senha = st.text_input("Senha temporária *", type="password", placeholder="Mínimo 6 caracteres")
        is_admin = st.checkbox("Administrador", value=False)

    if st.form_submit_button("Criar Voluntário", type="primary"):
        if not email or not nome or not senha:
            st.error("Preencha todos os campos obrigatórios")
        elif "@" not in email:
            st.error("Email inválido")
        elif len(senha) < 6:
            st.error("Senha deve ter pelo menos 6 caracteres")
        else:
            with st.spinner("Criando usuário..."):
                try:
                    # criação via RPC admin (JWT do administrador logado)
                    db.criar_usuario(email, senha, nome, is_admin, user["access_token"])
                    flash(f"Usuário {nome} criado!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    corpo = ""
                    resp_obj = getattr(e, "response", None)
                    if resp_obj is not None:
                        with contextlib.suppress(Exception):
                            corpo = str(resp_obj.json().get("message", "")).lower()
                    msg = (str(e) + " " + corpo).lower()
                    if "duplicate key" in msg or "already registered" in msg or "already exists" in msg:
                        st.error("Este email já está cadastrado.")
                    elif "apenas administradores" in msg:
                        st.error("Somente administradores podem criar usuários.")
                    else:
                        st.error(f"Erro ao criar usuário: {e}")
