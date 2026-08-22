import traceback

import streamlit as st

try:
    from src.ui import carregar_logo_b64, load_css
except Exception as e:
    st.error(f"Erro ao importar modulos: {e}")
    st.code(traceback.format_exc())
    st.stop()

favicon_b64 = carregar_logo_b64()

page_icon = f"data:image/png;base64,{favicon_b64}" if favicon_b64 else None

st.set_page_config(
    page_title="Cesta Solidária",
    page_icon=page_icon,
    layout="wide",
    initial_sidebar_state="expanded",
)

# load_css ja trata excecoes internamente (silencioso).
load_css()

# Navegacao unica e estatica: switch_page so resolve paginas registradas,
# e mutar a lista entre reruns quebrava a transicao pos-login. O controle
# de acesso fica nas paginas (require_login / is_admin), e a sidebar nativa
# fica oculta porque o app renderiza a propria.
pg = st.navigation(
    [
        st.Page("pages/0_Login.py", title="Login"),
        st.Page("pages/0_Dashboard.py", title="Dashboard"),
        st.Page("pages/1_Estoque.py", title="Estoque"),
        st.Page("pages/2_Simulador.py", title="Simulador"),
        st.Page("pages/3_Historico.py", title="Histórico"),
        st.Page("pages/4_Usuarios.py", title="Usuários"),
        st.Page("pages/5_Config.py", title="Configurações"),
    ],
    position="hidden",
)
pg.run()
