import base64
import json
import time

import streamlit as st

from src import db


def _jwt_exp(token: str) -> int | None:
    """Retorna timestamp de expiração do JWT ou None se inválido."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded).get("exp")
    except Exception:
        return None


def _token_expirado(token: str) -> bool:
    exp = _jwt_exp(token)
    if exp is None:
        return True
    return time.time() > exp - 30  # margem de 30s


def login(email: str, senha: str, lembrar: bool = False) -> bool:
    """Autentica usuário e cria sessão."""
    dados = db.autenticar(email, senha)
    if not dados:
        return False

    usuario = dados["user"]
    perfil = db.get_profile(usuario["id"], dados["access_token"])

    st.session_state["session"] = {
        "access_token": dados["access_token"],
        "refresh_token": dados.get("refresh_token"),
        "user_id": usuario["id"],
        "email": usuario["email"],
        "nome": perfil.get("nome") if perfil else "",
        "is_admin": bool(perfil and perfil.get("is_admin")),
        "login_time": time.time(),
        "remember_me": lembrar,
    }
    return True


def logout():
    """Encerra sessão local e revoga o refresh_token no Supabase."""
    sessao = st.session_state.get("session") or {}
    db.revogar_sessao(sessao.get("access_token"))
    st.session_state.pop("session", None)
    st.toast("Você saiu")


def _renovar_access_token(session: dict) -> bool:
    """Renova access_token usando refresh_token. Retorna True se renovou."""
    refresh_token = session.get("refresh_token")
    if not refresh_token:
        return False
    novos = db.renovar_sessao(refresh_token)
    if not novos or not novos.get("access_token"):
        return False
    session["access_token"] = novos["access_token"]
    if novos.get("refresh_token"):
        session["refresh_token"] = novos["refresh_token"]
    return True


def is_logged_in() -> bool:
    """Verifica se usuário está logado e sessão não expirou (app + JWT)."""
    session = st.session_state.get("session")
    if not session:
        return False

    # 1) Expiração app (24h / 30d)
    login_time = session.get("login_time", 0)
    remember = session.get("remember_me", False)
    max_age = 30 * 24 * 3600 if remember else 24 * 3600

    if time.time() - login_time > max_age:
        logout()
        return False

    # 2) Expiração JWT Supabase (~1h): renova via refresh_token antes de deslogar
    token = session.get("access_token")
    if token and _token_expirado(token) and not _renovar_access_token(session):
        logout()
        return False

    return True


def get_user():
    """Retorna dados do usuário logado ou None."""
    if is_logged_in():
        return st.session_state.get("session")
    return None


def is_admin(user=None) -> bool:
    """Verifica se usuário é admin."""
    usuario = user or get_user()
    return bool(usuario and usuario.get("is_admin"))


def require_login():
    """Redireciona para o login se não houver usuário autenticado.

    Retorna o usuário logado ou None (apos redirecionar e parar a execução).
    """
    user = get_user()
    if not user:
        st.switch_page("pages/0_Login.py")
        st.stop()
        return None
    return user


def get_token() -> str | None:
    """Retorna access token da sessão atual."""
    user = get_user()
    return user.get("access_token") if user else None
