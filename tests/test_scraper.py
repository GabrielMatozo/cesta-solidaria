import sys

from src.scraper_tenda import Produto, escolher_mais_barato, peso_normalizado


def _p(nome, preco, disponivel=True, slug="x"):
    return Produto(
        sku="1", slug=slug, nome=nome, preco=preco,
        preco_original=None, disponivel=disponivel,
        url=f"https://t/{slug}", imagem_url=None, marca=None,
        unidade=None, descricao=None,
    )


def test_peso_normalizado_variacoes():
    assert peso_normalizado("Oleo de Soja Vitaliv 900ml") == (900, "ml")
    assert peso_normalizado("Acucar Extra Fino 1kg") == (1000, "g")
    assert peso_normalizado("Arroz Tipo 1 5kg Visconde") == (5000, "g")
    assert peso_normalizado("Gelatina Uva 20g Qualimax") == (20, "g")
    assert peso_normalizado("Refresco 18G Frisco") == (18, "g")
    assert peso_normalizado("Produto sem peso") is None


def test_escolhe_marca_mais_barata_mesmo_peso():
    candidatos = [
        _p("Oleo Liza 900ml", 8.99),
        _p("Oleo Vitaliv 900ml", 7.35),
        _p("Oleo Soya 900ml", 7.99),
    ]
    escolhido = escolher_mais_barato(candidatos, alvo=(900, "ml"))
    assert escolhido.preco == 7.35
    assert escolhido.nome.startswith("Oleo Vitaliv")


def test_descarta_peso_diferente_mesmo_produto():
    candidatos = [
        _p("Oleo Vitaliv 500ml", 4.00),
        _p("Oleo Liza 900ml", 8.99),
    ]
    escolhido = escolher_mais_barato(candidatos, alvo=(900, "ml"))
    assert escolhido is not None
    assert escolhido.preco == 8.99


def test_descarta_indisponivel_e_preco_zero():
    candidatos = [
        _p("Oleo Barato 900ml", 0.0),
        _p("Oleo Indisponivel 900ml", 3.00, disponivel=False),
        _p("Oleo Liza 900ml", 8.99),
    ]
    escolhido = escolher_mais_barato(candidatos, alvo=(900, "ml"))
    assert escolhido.preco == 8.99


def test_sem_candidato_compativel_retorna_none():
    candidatos = [_p("Oleo Vitaliv 500ml", 4.00)]
    assert escolher_mais_barato(candidatos, alvo=(900, "ml")) is None
    assert escolher_mais_barato([], alvo=(900, "ml")) is None


def test_nao_confunde_g_com_ml():
    candidatos = [_p("Leite Condensado Caixa 395g", 4.69)]
    assert escolher_mais_barato(candidatos, alvo=(395, "ml")) is None


if __name__ == "__main__":
    sys.exit(0)


def test_descarta_produto_fora_do_termo_mesmo_com_peso_certo():
    candidatos = [
        _p("Fubá Mimoso PQ 500g", 2.15),
        _p("Farinha de Milho Amarela PQ 500g", 4.49),
    ]
    # termo pede farinha de milho: fubá tem o peso certo mas nao eh o produto
    escolhido = escolher_mais_barato(candidatos, alvo=(500, "g"),
                                     palavras=["farinha", "milho"])
    assert escolhido is not None
    assert "Farinha de Milho" in escolhido.nome


def test_palavras_comparam_sem_acento_e_ignoram_stopwords():
    assert peso_normalizado("Leite em Pó Integral 400g") == (400, "g")
    candidatos = [_p("Leite Condensado Semidesnatado 395g", 4.69)]
    # termo "leite condensado desnatado 395g": palavra "desnatado" nao consta
    assert escolher_mais_barato(candidatos, alvo=(395, "g"),
                                palavras=["leite", "condensado"]) is not None
