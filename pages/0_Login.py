import streamlit as st

from src import auth
from src.ui import carregar_logo_b64, load_css

load_css()

cesta_b64 = carregar_logo_b64()

st.markdown(
    """<style>
[data-testid="stHeader"] { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
.block-container { padding-top: 1.5rem !important; padding-bottom: 1rem !important; }

/* Login page - style the form as the card */
[data-testid="stForm"] {
    background: var(--bg-card);
    border-radius: var(--radius-xl);
    box-shadow: var(--shadow-xl);
    padding: var(--space-8);
    border: 1px solid var(--border-light);
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    max-width: 420px;
    margin: 0 auto;
}

.login-shell {
    max-width: 420px;
    margin: 0 auto;
}

.login-brand {
    text-align: center;
    margin-bottom: var(--space-8);
}

.login-logo {
    width: 72px;
    height: 72px;
    margin: 0 auto var(--space-5);
    border-radius: var(--radius-lg);
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-inverse);
    font-weight: 700;
    font-size: 1.75rem;
    box-shadow: var(--shadow-lg);
}

.login-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0 0 var(--space-2);
}

.login-subtitle {
    font-size: 0.875rem;
    color: var(--text-secondary);
    margin: 0;
}

.login-divider {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    margin: var(--space-6) 0;
    color: var(--text-muted);
    font-size: 0.8125rem;
}
.login-divider::before,
.login-divider::after {
    content: "";
    flex: 1;
    height: 1px;
    background: var(--border-light);
}
.login-divider span {
    white-space: nowrap;
}

.login-footer a {
    color: var(--primary);
    text-decoration: none;
}
.login-footer a:hover {
    text-decoration: underline;
}
</style>""",
    unsafe_allow_html=True,
)

if auth.is_logged_in():
    # Ja autenticado: sai da tela de login sem depender de rerun.
    st.switch_page("pages/0_Dashboard.py")

# Brand/logo
st.markdown(
    '<div class="login-shell"><div class="login-brand">'
    '<div class="login-logo" style="width: 72px; height: 72px; margin: 0 auto 20px; border-radius: 12px; background: url(\'data:image/png;base64,' + cesta_b64 + '\') center/cover no-repeat;"></div>'
    '<h1 class="login-title">Cesta Solidária</h1>'
    '<p class="login-subtitle">Gestão de cestas básicas para projetos sociais</p>'
    '</div>'
    '<div class="login-divider"><span>Entre com sua conta</span></div></div>',
    unsafe_allow_html=True,
)

# Form - Streamlit form styled as the login card
with st.form("login_form", clear_on_submit=False, border=False):
    email = st.text_input("Email", placeholder="seu@email.com", autocomplete="email", key="login_email")
    senha = st.text_input("Senha", type="password", autocomplete="current-password", key="login_senha")

    col1, col2 = st.columns([1, 1])
    with col1:
        lembrar = st.checkbox("Lembrar-me (30 dias)", key="login_lembrar")

    submitted = st.form_submit_button("Entrar", type="primary", width='stretch')

if submitted:
    if not email or not senha:
        st.error("Preencha email e senha")
    elif "@" not in email:
        st.error("Email inválido")
    else:
        with st.spinner("Autenticando..."):
            if auth.login(email, senha, lembrar=lembrar):
                # switch_page faz a troca atomica de pagina no cliente;
                # st.rerun aqui reexecutava com a navegacao mutada e deixava
                # o frame antigo do login visivel atras do novo.
                st.switch_page("pages/0_Dashboard.py")
            else:
                st.error("Email ou senha inválidos")

# Footer alinhado a largura do card
st.markdown(
    '<div class="login-shell"><p style="margin-top:12px;font-size:0.7rem;'
    'opacity:0.75;text-align:center;">Cesta Solidária v1.0</p></div>',
    unsafe_allow_html=True,
)
