import pytest

from src import db


class FakeResp:
    def __init__(self, dados, status=200):
        self._dados = dados
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._dados


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    yield


def test_listar_produtos(monkeypatch):
    chamadas = {}
    def fake_get(url, headers=None, **kw):
        chamadas["url"] = url
        chamadas["headers"] = headers
        return FakeResp([{"id": 1, "nome": "Arroz"}])

    monkeypatch.setattr(db.requests, "get", fake_get)
    rows = db.listar_produtos("token-usuario")
    assert rows[0]["nome"] == "Arroz"
    assert "rest/v1/produtos" in chamadas["url"]
    assert chamadas["headers"]["Authorization"] == "Bearer token-usuario"


def test_upsert_produtos(monkeypatch):
    chamadas = {}
    def fake_post(url, json=None, headers=None, **kw):
        chamadas["url"] = url
        chamadas["headers"] = headers
        return FakeResp([{"id": 1}])

    monkeypatch.setattr(db.requests, "post", fake_post)
    db.upsert_produtos([{"id": 1, "nome": "Arroz"}], "token-usuario")
    assert "on_conflict=id" in chamadas["url"]
    assert chamadas["headers"]["Prefer"] == "resolution=merge-duplicates,return=representation"


def test_get_config_sem_valor(monkeypatch):
    monkeypatch.setattr(db.requests, "get", lambda url, headers=None, **kw: FakeResp([]))
    assert db.get_config("tenda_region_id", "tok") is None


def test_set_config(monkeypatch):
    chamadas = {}
    def fake_post(url, json=None, headers=None, **kw):
        chamadas["url"] = url
        chamadas["json"] = json
        return FakeResp([{"chave": "x", "valor": "y"}])

    monkeypatch.setattr(db.requests, "post", fake_post)
    db.set_config("preco_stale_dias", "3", "tok")
    assert chamadas["json"] == [{"chave": "preco_stale_dias", "valor": "3"}]


def test_autenticar_ok(monkeypatch):
    def fake_post(url, json=None, headers=None, **kw):
        assert "auth/v1/token" in url
        return FakeResp({"access_token": "abc", "user": {"id": "u1", "email": "a@b.c"}})

    monkeypatch.setattr(db.requests, "post", fake_post)
    res = db.autenticar("a@b.c", "senha")
    assert res["access_token"] == "abc"


def test_autenticar_errado_retorna_none(monkeypatch):
    def fake_post(url, json=None, headers=None, **kw):
        return FakeResp({"error": "invalid_credentials"}, status=400)

    monkeypatch.setattr(db.requests, "post", fake_post)
    assert db.autenticar("a@b.c", "errada") is None


def test_requisicoes_usam_timeout(monkeypatch):
    capturado = {}
    def fake_get(url, headers=None, **kw):
        capturado["timeout"] = kw.get("timeout")
        return FakeResp([])

    monkeypatch.setattr(db.requests, "get", fake_get)
    db.listar_produtos("tok")
    assert capturado["timeout"] == db.DEFAULT_TIMEOUT


def test_autenticar_retorna_refresh_token(monkeypatch):
    def fake_post(url, json=None, headers=None, **kw):
        return FakeResp({
            "access_token": "abc",
            "refresh_token": "rt-123",
            "user": {"id": "u1", "email": "a@b.c"},
        })

    monkeypatch.setattr(db.requests, "post", fake_post)
    res = db.autenticar("a@b.c", "senha")
    assert res["refresh_token"] == "rt-123"


def test_renovar_sessao(monkeypatch):
    chamadas = {}
    def fake_post(url, json=None, headers=None, **kw):
        chamadas["url"] = url
        chamadas["json"] = json
        return FakeResp({
            "access_token": "novo-access",
            "refresh_token": "novo-refresh",
            "user": {"id": "u1"},
        })

    monkeypatch.setattr(db.requests, "post", fake_post)
    res = db.renovar_sessao("rt-antigo")
    assert "grant_type=refresh_token" in chamadas["url"]
    assert chamadas["json"] == {"refresh_token": "rt-antigo"}
    assert res["access_token"] == "novo-access"
    assert res["refresh_token"] == "novo-refresh"


def test_listar_tabela_pagina_resultados(monkeypatch):
    pagina = {"n": 0}

    def fake_get(url, headers=None, **kw):
        pagina["n"] += 1
        range_header = headers.get("Range", "")
        if pagina["n"] == 1:
            assert range_header == "0-999"
            return FakeResp([{"id": i} for i in range(1000)])
        assert range_header == "1000-1999"
        return FakeResp([{"id": 1000}, {"id": 1001}])

    monkeypatch.setattr(db.requests, "get", fake_get)
    rows = db.listar_tabela("precos_historico", None, service=True)
    assert len(rows) == 1002
    assert pagina["n"] == 2


def test_upsert_produtos_ignore_duplicates(monkeypatch):
    capturado = {}
    def fake_post(url, json=None, headers=None, **kw):
        capturado["prefer"] = headers.get("Prefer") if headers else None
        return FakeResp([{"id": 1}])

    monkeypatch.setattr(db.requests, "post", fake_post)
    db.upsert_produtos([{"id": 1}], "tok", ignore_duplicates=True)
    assert capturado["prefer"] == "resolution=ignore-duplicates,return=representation"


def test_revogar_sessao(monkeypatch):
    chamadas = {}
    def fake_post(url, json=None, headers=None, **kw):
        chamadas["url"] = url
        chamadas["headers"] = headers
        return FakeResp({})

    monkeypatch.setattr(db.requests, "post", fake_post)
    db.revogar_sessao("tok-123")
    assert "auth/v1/logout" in chamadas["url"]
    assert "scope=global" in chamadas["url"]
    assert chamadas["headers"]["Authorization"] == "Bearer tok-123"


def test_contar_compras_desde_count_exact(monkeypatch):
    class RespComRange:
        status_code = 200
        headers = {"Content-Range": "0-0/57"}

        def raise_for_status(self):
            pass

        def json(self):
            return [{"id": 1}]

    capturado = {}
    def fake_get(url, headers=None, **kw):
        capturado["prefer"] = headers.get("Prefer")
        capturado["range"] = headers.get("Range")
        capturado["url"] = url
        return RespComRange()

    monkeypatch.setattr(db.requests, "get", fake_get)
    total = db.contar_compras_desde("tok", "2026-08-01T00:00:00+00:00")
    assert total == 57
    assert capturado["prefer"] == "count=exact"
    assert capturado["range"] == "0-0"
    assert "data=gte.2026-08-01" in capturado["url"]


def test_criar_usuario_via_rpc(monkeypatch):
    capturado = {}
    def fake_post(url, json=None, headers=None, **kw):
        capturado["url"] = url
        capturado["json"] = json
        capturado["auth"] = headers.get("Authorization") if headers else None
        return FakeResp("uuid-novo")

    monkeypatch.setattr(db.requests, "post", fake_post)
    usr = db.criar_usuario("vol@igreja.org", "senha123", "Voluntário", False, "tok-admin")
    assert usr == {"id": "uuid-novo"}
    assert "/rpc/admin_criar_usuario" in capturado["url"]
    assert capturado["json"] == {
        "p_email": "vol@igreja.org", "p_senha": "senha123",
        "p_nome": "Voluntário", "p_is_admin": False,
    }
    assert capturado["auth"] == "Bearer tok-admin"


def test_excluir_usuario_via_rpc(monkeypatch):
    chamadas = {}
    def fake_post(url, json=None, headers=None, **kw):
        chamadas["url"] = url
        chamadas["json"] = json
        return FakeResp(None)

    monkeypatch.setattr(db.requests, "post", fake_post)
    db.excluir_usuario("u-1", "tok-admin")
    assert "/rpc/admin_excluir_usuario" in chamadas["url"]
    assert chamadas["json"] == {"p_id": "u-1"}
