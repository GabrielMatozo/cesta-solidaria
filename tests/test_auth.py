import base64
import json
import time
from unittest import mock

from src import auth


def _jwt_com_exp(exp: float) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"exp": int(exp)}).encode()).decode()
    return f"header.{payload}.assinatura"


def test_login_ok_popula_sessao():
    fake_db = mock.Mock()
    fake_db.autenticar.return_value = {
        "access_token": "tok", "refresh_token": "rt", "user": {"id": "u1", "email": "a@b.c"}
    }
    fake_db.get_profile.return_value = {"nome": "Ana", "is_admin": True}
    with mock.patch("src.auth.db", fake_db), mock.patch("src.auth.st") as fake_st:
        fake_st.session_state = {}
        assert auth.login("a@b.c", "senha") is True
    assert fake_st.session_state["session"]["is_admin"] is True
    assert fake_st.session_state["session"]["access_token"] == "tok"
    assert fake_st.session_state["session"]["refresh_token"] == "rt"


def test_login_errado_nao_popula():
    fake_db = mock.Mock()
    fake_db.autenticar.return_value = None
    with mock.patch("src.auth.db", fake_db), mock.patch("src.auth.st") as fake_st:
        fake_st.session_state = {}
        assert auth.login("a@b.c", "errada") is False
    assert "session" not in fake_st.session_state


def test_logout_remove_sessao():
    with mock.patch("src.auth.st") as fake_st:
        fake_st.session_state = {"session": {}}
        auth.logout()
    assert "session" not in fake_st.session_state


def test_is_admin():
    assert auth.is_admin({"is_admin": True}) is True
    assert auth.is_admin({"is_admin": False}) is False
    with mock.patch("src.auth.st") as fake_st:
        fake_st.session_state = {}
        assert auth.is_admin(None) is False


def test_is_logged_in_renova_token_expirado():
    agora = time.time()
    expirado = _jwt_com_exp(agora - 100)
    valido = _jwt_com_exp(agora + 3600)
    sessao = {
        "user_id": "u1", "email": "a@b.c", "nome": "Ana", "is_admin": True,
        "login_time": agora, "remember_me": False,
        "access_token": expirado, "refresh_token": "rt-antigo",
    }
    fake_db = mock.Mock()
    fake_db.renovar_sessao.return_value = {
        "access_token": valido, "refresh_token": "rt-novo",
    }
    with mock.patch("src.auth.db", fake_db), mock.patch("src.auth.st") as fake_st:
        fake_st.session_state = {"session": dict(sessao)}
        assert auth.is_logged_in() is True
    assert fake_st.session_state["session"]["access_token"] == valido
    assert fake_st.session_state["session"]["refresh_token"] == "rt-novo"
    fake_db.renovar_sessao.assert_called_once_with("rt-antigo")


def test_is_logged_in_desloga_quando_refresh_falha():
    agora = time.time()
    expirado = _jwt_com_exp(agora - 100)
    sessao = {
        "user_id": "u1", "email": "a@b.c", "nome": "Ana", "is_admin": True,
        "login_time": agora, "remember_me": False,
        "access_token": expirado, "refresh_token": "rt-antigo",
    }
    fake_db = mock.Mock()
    fake_db.renovar_sessao.return_value = None
    with mock.patch("src.auth.db", fake_db), mock.patch("src.auth.st") as fake_st:
        fake_st.session_state = {"session": dict(sessao)}
        assert auth.is_logged_in() is False
    assert "session" not in fake_st.session_state


def test_require_login_redireciona_quando_nao_logado():
    with mock.patch("src.auth.st") as fake_st:
        fake_st.session_state = {}
        fake_st.switch_page = mock.Mock()
        fake_st.stop = mock.Mock()
        resultado = auth.require_login()
    assert resultado is None
    fake_st.switch_page.assert_called_once_with("pages/0_Login.py")
    fake_st.stop.assert_called_once()


def test_require_login_returns_user_when_logged_in():
    now = time.time()
    valido = _jwt_com_exp(now + 3600)
    with mock.patch("src.auth.st") as fake_st:
        fake_st.session_state = {
            "session": {
                "user_id": "u1", "email": "a@b.c", "nome": "Ana", "is_admin": True,
                "login_time": now, "remember_me": False,
                "access_token": valido, "refresh_token": "rt",
            }
        }
        fake_st.rerun = mock.Mock()
        user = auth.require_login()
    assert user["user_id"] == "u1"
    assert user["email"] == "a@b.c"


def _sessao_com_login_time(login_time, remember_me=False):
    return {
        "user_id": "u1", "email": "a@b.c", "nome": "Ana", "is_admin": True,
        "login_time": login_time, "remember_me": remember_me,
        "access_token": _jwt_com_exp(time.time() + 3600), "refresh_token": "rt",
    }


def test_is_logged_in_expira_apos_24h_sem_lembrar():
    antigo = time.time() - 25 * 3600
    with mock.patch("src.auth.st") as fake_st:
        fake_st.session_state = {"session": _sessao_com_login_time(antigo)}
        assert auth.is_logged_in() is False
    assert "session" not in fake_st.session_state


def test_is_logged_in_valido_dentro_de_30d_com_lembrar():
    recente = time.time() - 29 * 24 * 3600
    with mock.patch("src.auth.st") as fake_st:
        fake_st.session_state = {"session": _sessao_com_login_time(recente, remember_me=True)}
        assert auth.is_logged_in() is True


def test_logout_revoga_refresh_token():
    fake_db = mock.Mock()
    with mock.patch("src.auth.db", fake_db), mock.patch("src.auth.st") as fake_st:
        fake_st.session_state = {"session": {"access_token": "tok-x"}}
        auth.logout()
    fake_db.revogar_sessao.assert_called_once_with("tok-x")
    assert "session" not in fake_st.session_state
