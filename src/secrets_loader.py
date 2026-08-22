import os


def get_secret(chave: str, default=None):
    """Busca segredo em st.secrets primeiro, depois em variaveis de ambiente."""
    try:
        import streamlit as st

        val = st.secrets.get(chave)
        if val is not None:
            return val
    except Exception:
        pass
    return os.environ.get(chave, default)
