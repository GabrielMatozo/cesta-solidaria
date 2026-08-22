import contextlib

import requests

from src import secrets_loader

DEFAULT_TIMEOUT = 15
PAGE_SIZE = 1000
MAX_PAGES = 500


def supabase_url() -> str:
    return secrets_loader.get_secret("SUPABASE_URL", "").rstrip("/")


def anon_key() -> str:
    return secrets_loader.get_secret("SUPABASE_ANON_KEY", "")


def service_key() -> str:
    return secrets_loader.get_secret("SUPABASE_SERVICE_ROLE_KEY", "")


def _headers(token, service=False):
    """
    Gera headers para requisições Supabase.

    Args:
        token: Access token do usuário (anon key como apikey + Bearer token)
        service: Se True, usa SERVICE_ROLE_KEY (apenas para scripts/backend).
                 NÃO usar no frontend - use token do usuário logado.
    """
    chave = service_key() if service else anon_key()
    headers = {"apikey": chave, "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif service:
        headers["Authorization"] = f"Bearer {chave}"
    return headers


def _url(tabela: str) -> str:
    return f"{supabase_url()}/rest/v1/{tabela}"


def listar_produtos(token, *, service=False):
    resp = requests.get(
        f"{_url('produtos')}?select=*&order=nome.asc",
        headers=_headers(token, service),
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def listar_tabela(tabela: str, token, *, service=False) -> list[dict]:
    """Lista todas as linhas de uma tabela, paginando com header Range.

    O PostgREST/Supabase corta respostas em db-max-rows (default 1000), então
    uma chamada única pode retornar dados truncados com HTTP 200. O limite de
    paginas e um guard contra loop infinito caso o servidor ignore o Range.
    """
    rows: list[dict] = []
    offset = 0
    for _ in range(MAX_PAGES):
        headers = _headers(token, service)
        headers["Range"] = f"{offset}-{offset + PAGE_SIZE - 1}"
        resp = requests.get(
            f"{_url(tabela)}?select=*", headers=headers, timeout=DEFAULT_TIMEOUT
        )
        resp.raise_for_status()
        lote = resp.json()
        rows.extend(lote)
        if len(lote) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE
    return rows


def upsert_produtos(rows, token, *, service=False, ignore_duplicates=False):
    headers = _headers(token, service)
    resolution = "ignore-duplicates" if ignore_duplicates else "merge-duplicates"
    headers["Prefer"] = f"resolution={resolution},return=representation"
    resp = requests.post(
        f"{_url('produtos')}?on_conflict=id",
        json=rows,
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def listar_regions(token, *, service=False):
    resp = requests.get(
        f"{_url('regions')}?select=*&order=nome.asc",
        headers=_headers(token, service),
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def upsert_regions(rows, token=None, *, service=False):
    headers = _headers(token, service)
    headers["Prefer"] = "resolution=merge-duplicates,return=representation"
    resp = requests.post(
        f"{_url('regions')}?on_conflict=region_id",
        json=rows,
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def get_config(chave, token, *, service=False):
    resp = requests.get(
        f"{_url('config')}?chave=eq.{chave}&select=valor",
        headers=_headers(token, service),
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0]["valor"] if rows else None


def set_config(chave, valor, token=None, *, service=False):
    headers = _headers(token, service)
    headers["Prefer"] = "resolution=merge-duplicates,return=representation"
    resp = requests.post(
        f"{_url('config')}?on_conflict=chave",
        json=[{"chave": chave, "valor": str(valor)}],
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()


def inserir_precos_historico(rows, token=None, *, service=False):
    headers = _headers(token, service)
    headers["Prefer"] = "resolution=merge-duplicates,return=representation"
    resp = requests.post(
        f"{_url('precos_historico')}?on_conflict=produto_id,dia",
        json=rows,
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()


def inserir_compra(compra, token):
    headers = _headers(token)
    headers["Prefer"] = "return=representation"
    resp = requests.post(
        f"{_url('compras')}",
        json=[compra],
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def listar_compras(token, limite=100):
    resp = requests.get(
        f"{_url('compras')}?select=*&order=data.desc&limit={limite}",
        headers=_headers(token),
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def contar_compras_desde(token, data_iso: str) -> int:
    """Conta compras com data >= data_iso sem baixar as linhas.

    Usa Range 0-0 + Prefer count=exact; o total vem do Content-Range.
    """
    headers = _headers(token)
    headers["Prefer"] = "count=exact"
    headers["Range"] = "0-0"
    resp = requests.get(
        f"{_url('compras')}?select=id&data=gte.{data_iso}",
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    content_range = resp.headers.get("Content-Range", "")
    if "/" in content_range:
        try:
            return int(content_range.rsplit("/", 1)[-1])
        except ValueError:
            pass
    return len(resp.json())


def autenticar(email, senha):
    resp = requests.post(
        f"{supabase_url()}/auth/v1/token?grant_type=password",
        json={"email": email, "password": senha},
        headers=_headers(None),
        timeout=DEFAULT_TIMEOUT,
    )
    if resp.status_code == 400:
        return None
    resp.raise_for_status()
    dados = resp.json()
    return {
        "access_token": dados["access_token"],
        "refresh_token": dados.get("refresh_token"),
        "user": dados["user"],
    }


def renovar_sessao(refresh_token):
    """Renova o access token via refresh_token. Retorna None se falhar."""
    try:
        resp = requests.post(
            f"{supabase_url()}/auth/v1/token?grant_type=refresh_token",
            json={"refresh_token": refresh_token},
            headers=_headers(None),
            timeout=DEFAULT_TIMEOUT,
        )
        if resp.status_code != 200:
            return None
        dados = resp.json()
        return {
            "access_token": dados["access_token"],
            "refresh_token": dados.get("refresh_token"),
            "user": dados.get("user"),
        }
    except requests.RequestException:
        return None


def revogar_sessao(access_token):
    """Revoga a sessao (refresh_token incluido) no Supabase. Best-effort."""
    if not access_token:
        return
    with contextlib.suppress(Exception):
        requests.post(
            f"{supabase_url()}/auth/v1/logout?scope=global",
            headers=_headers(access_token),
            timeout=DEFAULT_TIMEOUT,
        )


def criar_usuario(email, senha, nome, is_admin, token):
    """Cria usuario via RPC admin (exige JWT de administrador logado)."""
    resp = requests.post(
        f"{supabase_url()}/rest/v1/rpc/admin_criar_usuario",
        json={
            "p_email": email,
            "p_senha": senha,
            "p_nome": nome,
            "p_is_admin": bool(is_admin),
        },
        headers=_headers(token),
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    return {"id": resp.json()}


def excluir_usuario(user_id, token):
    """Exclui usuario via RPC admin (exige JWT de administrador logado)."""
    resp = requests.post(
        f"{supabase_url()}/rest/v1/rpc/admin_excluir_usuario",
        json={"p_id": str(user_id)},
        headers=_headers(token),
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()


def listar_profiles(token, *, service=False):
    resp = requests.get(
        f"{_url('profiles')}?select=id,nome,email,is_admin&order=nome.asc",
        headers=_headers(token, service),
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def get_profile(user_id, token, *, service=False):
    resp = requests.get(
        f"{_url('profiles')}?id=eq.{user_id}&select=nome,email,is_admin",
        headers=_headers(token, service),
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None
