"""
Scraper para API do Tenda Atacado com anti-bloqueio GRATUITO.

Estratégias gratuitas implementadas:
- Rotação de User-Agents reais (sem bibliotecas externas)
- Jitter aleatório entre requisições (2.5-8s)
- Rotação de sessão (limita requisições por sessão)
- Headers realísticos rotativos
- Backoff exponencial em erros 429/403/5xx
"""

from __future__ import annotations

import logging
import os
import random
import re
import time
from dataclasses import dataclass
from typing import Any, Self

import requests

from src import config as _config

log = logging.getLogger(__name__)

# =============================================================================
# USER-AGENTS REAIS (Firefox, Chrome, Safari, Edge em Windows/Mac/Linux/Android)
# =============================================================================
USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
    "Mozilla/5.0 (Linux; Android 14; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
]

# Headers base realísticos (sem campos que denunciam automação)
BASE_HEADERS_TEMPLATE = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Referer": "https://www.tendaatacado.com.br/",
    "Origin": "https://www.tendaatacado.com.br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Linux"',
}


@dataclass
class Produto:
    """Representa um produto do Tenda Atacado."""
    sku: str
    slug: str
    nome: str
    preco: float
    preco_original: float | None
    disponivel: bool
    url: str
    imagem_url: str | None
    marca: str | None
    unidade: str | None
    descricao: str | None


# SELECAO DE MARCA MAIS BARATA
# =============================================================================

_PESO_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l)\b", re.IGNORECASE)


def peso_normalizado(texto: str):
    """Extrai peso/volume normalizado de um texto.

    Retorna (valor, unidade) com unidade em {"g", "ml"} e valor em inteiro
    na menor unidade pratica (kg -> g, l -> ml). None se nao houver peso.
    """
    if not texto:
        return None
    m = _PESO_RE.search(texto)
    if not m:
        return None
    valor = float(m.group(1).replace(",", "."))
    unidade = m.group(2).lower()
    if unidade == "kg":
        return (int(round(valor * 1000)), "g")
    if unidade == "l":
        return (int(round(valor * 1000)), "ml")
    return (int(round(valor)), unidade)


_STOPWORDS = {"de", "do", "da", "em", "e", "com"}


def _normaliza(texto: str) -> str:
    """Minusculas sem acento, para comparar palavras do termo com o nome."""
    import unicodedata

    sem_acento = unicodedata.normalize("NFD", texto)
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).lower()


def palavras_do_termo(termo: str):
    """Palavras significativas do termo (sem stopwords e sem o token de peso)."""
    sem_peso = _PESO_RE.sub(" ", (termo or "").lower())
    return [
        p for p in _normaliza(sem_peso).split()
        if p not in _STOPWORDS and len(p) > 1
    ]


def escolher_mais_barato(produtos, alvo, palavras=None):
    """Escolhe o produto disponivel mais barato com o mesmo peso/volume.

    alvo: tupla (valor, unidade) vinda de peso_normalizado. Candidatos com
    peso diferente, indisponiveis ou sem preco valido sao descartados -
    nunca substitui por produto de quantidade/peso diferente.

    palavras: quando informado, o nome do candidato precisa conter todas
    (comparacao sem acento) - descarta produtos fora da categoria que a
    busca do mercado traz junto (ex: fuba em busca de farinha de milho).
    """
    def peso_do(p):
        return peso_normalizado(p.nome) or peso_normalizado(p.slug)

    if alvo is None:
        melhores = [p for p in produtos if p.disponivel and p.preco > 0]
    else:
        melhores = [
            p for p in produtos
            if p.disponivel and p.preco > 0 and peso_do(p) == alvo
        ]
    if palavras:
        nome_norm = None
        filtrados = []
        for p in melhores:
            nome_norm = _normaliza(p.nome or "")
            if all(palavra in nome_norm for palavra in palavras):
                filtrados.append(p)
        melhores = filtrados
    if not melhores:
        return None
    return min(melhores, key=lambda p: p.preco)


@dataclass
class ResultadoBusca:
    """Resultado de uma busca de produtos."""
    produtos: list[Produto]
    total: int
    pagina: int
    total_paginas: int


class TendaScraperError(Exception):
    """Exceção base do scraper."""


class TendaAPIError(TendaScraperError):
    """Erro retornado pela API do Tenda."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"API Error {status_code}: {message}")


class TendaScraper:
    """
    Cliente para a API pública do Tenda Atacado com anti-bloqueio gratuito.

    IMPORTANTE: A API usa `cartId` (numérico, ex: 38343853), NÃO o código da região (ex: 000021).
    O cartId padrão 38343853 foi obtido do HAR e funciona para buscas e detalhes.
    """

    BASE_URL = "https://api.tendaatacado.com.br/api/public/store"
    # Token publico embutido no frontend do site do Tenda; usado como
    # fallback quando TENDA_BEARER_TOKEN nao esta definido no ambiente.
    DEFAULT_BEARER = "fb60ee8cc1435ebf5774acd662c87d85"
    DEFAULT_CART_ID = "38343853"

    def __init__(
        self,
        region_id: str | None = None,
        cart_id: str | None = None,
        bearer_token: str | None = None,
        timeout: float = 20.0,
        max_retries: int = 3,
        min_delay: float = 2.5,
        max_delay: float = 8.0,
        max_req_per_session: int = 30,
        use_tor: bool = False,
    ) -> None:
        self.region_id = region_id or _config.TENDA_REGION_DEFAULT
        self.cart_id = cart_id or os.getenv("TENDA_CART_ID", self.DEFAULT_CART_ID)
        self.bearer_token = bearer_token or os.getenv("TENDA_BEARER_TOKEN", self.DEFAULT_BEARER)
        self.timeout = timeout
        self.max_retries = max_retries
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_req_per_session = max_req_per_session
        self.use_tor = use_tor

        self._req_count = 0
        self._session_ua: str | None = None
        self._session: requests.Session | None = None
        self._tor_available = self._check_tor() if use_tor else False

        self._new_session()

    def _check_tor(self) -> bool:
        try:
            proxies = {"http": "socks5://127.0.0.1:9050", "https": "socks5://127.0.0.1:9050"}
            with requests.Session() as s:
                s.proxies = proxies
                r = s.get("http://httpbin.org/ip", timeout=10)
            log.info("Tor disponível: %s", r.json().get("origin"))
            return True
        except Exception:
            log.warning("Tor não disponível na porta 9050. Continuando sem Tor.")
            return False

    def _random_ua(self) -> str:
        return random.choice(USER_AGENTS)

    def _headers_for_ua(self, ua: str) -> dict[str, str]:
        is_mobile = "Mobile" in ua or "iPhone" in ua or "Android" in ua
        is_firefox = "Firefox" in ua
        is_safari = "Safari" in ua and "Chrome" not in ua

        headers = BASE_HEADERS_TEMPLATE.copy()
        headers["User-Agent"] = ua
        headers["Sec-CH-UA-Mobile"] = "?1" if is_mobile else "?0"
        headers["Sec-CH-UA-Platform"] = '"Android"' if "Android" in ua else ('"macOS"' if "Macintosh" in ua else '"Windows"')

        if random.random() < 0.3:
            headers["Accept-Language"] = "pt-BR,pt;q=0.8,en-US;q=0.7,en;q=0.6"
        elif random.random() < 0.6:
            headers["Accept-Language"] = "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"

        if is_firefox:
            headers["Sec-CH-UA"] = '"Firefox";v="131", "Not_A Brand";v="24"'
        elif is_safari:
            headers["Sec-CH-UA"] = '"Safari";v="17", "Not_A Brand";v="24"'
        else:
            headers["Sec-CH-UA"] = '"Chromium";v="129", "Not_A Brand";v="24"'

        return headers


    def _new_session(self) -> None:
        if self._session:
            self._session.close()

        proxies = None
        if self.use_tor and self._tor_available:
            proxies = {"http": "socks5://127.0.0.1:9050", "https": "socks5://127.0.0.1:9050"}
            log.info("Nova sessão via Tor")

        self._session_ua = self._random_ua()
        headers = self._headers_for_ua(self._session_ua)
        headers["Authorization"] = f"Bearer {self.bearer_token}"

        self._session = requests.Session()
        if proxies:
            self._session.proxies = proxies
        self._session.headers.update(headers)
        self._req_count = 0
        log.info("Nova sessão criada (UA: %s...)", self._session_ua[:50])

    def _rotate_session_if_needed(self) -> None:
        if self._req_count >= self.max_req_per_session:
            log.info("Rotacionando sessão (%d requisições)", self._req_count)
            self._new_session()

    def _jitter_delay(self) -> None:
        delay = random.uniform(self.min_delay, self.max_delay)
        log.debug("Aguardando %.1fs (jitter)", delay)
        time.sleep(delay)

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        self._rotate_session_if_needed()
        self._jitter_delay()

        url = f"{self.BASE_URL}{path}"
        params = kwargs.pop("params", {})
        params["cartId"] = self.cart_id

        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._session.request(
                    method, url, params=params, timeout=self.timeout, **kwargs
                )
                self._req_count += 1

                if resp.status_code == 200:
                    return resp

                log.warning("HTTP %d na tentativa %d/%d - URL: %s", resp.status_code, attempt, self.max_retries, resp.url)

                if resp.status_code in (429, 403, 500, 502, 503, 504):
                    if attempt < self.max_retries:
                        wait = min(2 ** attempt * 5, 60)
                        log.info("Backoff %ds antes de retry...", wait)
                        time.sleep(wait)
                        self._new_session()
                        continue
                    raise TendaAPIError(resp.status_code, resp.text[:500])

                raise TendaAPIError(resp.status_code, resp.text[:500])

            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    wait = min(2 ** attempt * 3, 30)
                    log.warning("Erro de rede (%s). Tentativa %d/%d. Aguardando %ds...", exc, attempt, self.max_retries, wait)
                    time.sleep(wait)
                    self._new_session()
                    continue
                raise TendaScraperError(f"Falha após {self.max_retries} tentativas: {last_exc}") from last_exc

        raise TendaScraperError(f"Falha após {self.max_retries} tentativas")

    def buscar_preco_produto(self, token: str, region_id: str | None = None) -> dict:
        original_region = self.region_id
        self.region_id = region_id or self.region_id
        try:
            produto = self.detalhes_produto(token)
            if not produto:
                raise TendaAPIError(404, f"Produto não encontrado: {token}")
            return {
                "token": token,
                "nome": produto.nome,
                "preco": produto.preco,
                "region_id": self.region_id,
            }
        finally:
            self.region_id = original_region

    def buscar_mais_barato(self, termo: str, unidade_alvo: str | None = None,
                           max_paginas: int = 2) -> Produto | None:
        """Busca o termo e retorna a marca mais barata do mesmo peso/volume.

        unidade_alvo: texto do produto cadastrado (ex: "900ml", "1kg") que
        define o peso alvo. Sem unidade_alvo ou sem peso reconhecivel,
        nao filtra por peso: devolve o candidato disponivel mais barato
        que combine com as palavras do termo.
        """
        resultado = self.buscar(termo, pagina=1)
        candidatos = list(resultado.produtos)
        if max_paginas > 1 and len(resultado.produtos) >= 20:
            try:
                pag2 = self.buscar(termo, pagina=2)
                candidatos.extend(pag2.produtos)
            except TendaAPIError:
                pass

        alvo = peso_normalizado(unidade_alvo or "")
        return escolher_mais_barato(
            candidatos, alvo=alvo, palavras=palavras_do_termo(termo)
        )

    def buscar_token_por_nome(self, nome: str, region_id: str | None = None) -> str | None:
        original_region = self.region_id
        self.region_id = region_id or self.region_id
        try:
            resultado = self.buscar(nome, pagina=1, filters=False)
            if resultado.produtos:
                slug = resultado.produtos[0].slug
                log.info("Token encontrado para '%s': %s", nome, slug)
                return slug
            log.warning("Nenhum produto encontrado para: %s", nome)
            return None
        except Exception as e:
            log.error("Erro ao buscar token para '%s': %s", nome, e)
            raise
        finally:
            self.region_id = original_region

    def buscar(
        self,
        query: str,
        pagina: int = 1,
        order: str = "relevance",
        save: bool = False,
        filters: bool = False,
    ) -> ResultadoBusca:
        params = {
            "query": query,
            "page": pagina,
            "order": order,
            "save": str(save).lower(),
            "filters": str(filters).lower(),
        }

        resp = self._request("GET", "/search", params=params)
        data = resp.json()

        produtos = []
        for item in data.get("products", []):
            try:
                produto = self._parse_produto(item)
                if produto:
                    produtos.append(produto)
            except Exception as e:
                log.warning("Erro ao parsear produto %s: %s", item.get("id"), e)

        total = data.get("total", 0)
        per_page = data.get("perPage", len(produtos))
        total_paginas = (total + per_page - 1) // per_page if per_page else 1

        return ResultadoBusca(
            produtos=produtos,
            total=total,
            pagina=pagina,
            total_paginas=total_paginas,
        )

    def buscar_todos(self, query: str, max_paginas: int = 10) -> list[Produto]:
        todos = []
        for pagina in range(1, max_paginas + 1):
            resultado = self.buscar(query, pagina=pagina)
            if not resultado.produtos:
                break
            todos.extend(resultado.produtos)
            if pagina >= resultado.total_paginas:
                break
            time.sleep(random.uniform(1.5, 4.0))
        return todos

    def detalhes_produto(self, slug: str) -> Produto | None:
        resp = self._request("GET", f"/product/{slug}")
        data = resp.json()
        return self._parse_produto(data)

    def _parse_produto(self, item: dict[str, Any]) -> Produto | None:
        sku = item.get("sku") or item.get("id")
        slug = item.get("token") or item.get("slug") or ""
        if not sku:
            return None

        # Cadeias com `or` descartam valores legitimos como 0 e False;
        # usar verificacao explicita de None.
        preco: Any = item.get("price")
        if preco is None:
            preco = item.get("priceWithDiscount")
        if preco is None:
            preco = item.get("priceWithoutDiscount")

        preco_original = item.get("priceWithoutDiscount")
        if preco_original is None:
            preco_original = item.get("originalPrice")

        disponivel = item["available"] if "available" in item else item.get("availableToSell", True)

        return Produto(
            sku=str(sku),
            slug=slug,
            nome=item.get("name") or item.get("title") or "",
            preco=float(preco) if preco is not None else 0.0,
            preco_original=float(preco_original) if preco_original is not None else None,
            disponivel=bool(disponivel),
            url=f"https://www.tendaatacado.com.br/produto/{slug}?region_id={self.region_id}",
            imagem_url=item.get("image") or item.get("imageUrl") or item.get("thumbnail"),
            marca=item.get("brand") or item.get("brandName"),
            unidade=item.get("unit") or item.get("unitOfMeasure"),
            descricao=item.get("description") or item.get("shortDescription"),
        )

    def close(self) -> None:
        if self._session:
            self._session.close()
            self._session = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# =========================================================================
# Funções de conveniência (compatibilidade)
# =========================================================================

def buscar_preco_produto(
    token: str,
    region_id: str | None = None,
    bearer_token: str | None = None,
    timeout: float = 20.0,
    max_retries: int = 3,
) -> dict:
    with TendaScraper(region_id=region_id, bearer_token=bearer_token, timeout=timeout, max_retries=3) as scraper:
        return scraper.buscar_preco_produto(token, region_id)


def buscar_token_por_nome(
    nome: str,
    region_id: str | None = None,
    bearer_token: str | None = None,
    timeout: float = 20.0,
    max_retries: int = 3,
) -> str | None:
    with TendaScraper(region_id=region_id, bearer_token=bearer_token, timeout=timeout, max_retries=3) as scraper:
        return scraper.buscar_token_por_nome(nome, region_id)


def buscar_produtos(
    query: str,
    region_id: str | None = None,
    max_paginas: int = 5,
    use_tor: bool = False,
) -> list[Produto]:
    with TendaScraper(region_id=region_id, use_tor=use_tor) as scraper:
        return scraper.buscar_todos(query, max_paginas=max_paginas)


def main() -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Tenda Scraper - Anti-bloqueio gratuito")
    parser.add_argument("query", help="Termo de busca (ex: arroz)")
    parser.add_argument("--regiao", default=None, help="ID da região (padrão: config.TENDA_REGION_DEFAULT)")
    parser.add_argument("--paginas", type=int, default=3, help="Máx páginas (padrão: 3)")
    parser.add_argument("--tor", action="store_true", help="Usar Tor se disponível (porta 9050)")
    parser.add_argument("--json", action="store_true", help="Saída em JSON")
    args = parser.parse_args()

    produtos = buscar_produtos(args.query, region_id=args.regiao, max_paginas=args.paginas, use_tor=args.tor)

    if args.json:
        print(json.dumps([p.__dict__ for p in produtos], ensure_ascii=False, indent=2))
    else:
        for i, p in enumerate(produtos, 1):
            print(f"{i}. {p.nome} - R$ {p.preco:.2f} - {p.url}")


if __name__ == "__main__":
    main()
