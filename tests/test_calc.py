import pandas as pd
import pytest

from src import calc


def _df():
    return pd.DataFrame([
        {"id": 1, "nome": "Arroz", "marca": "", "unidade": "5kg", "qtd_por_cesta": 2, "estoque_atual": 7, "preco_atual": 20.50},
        {"id": 2, "nome": "Feijão", "marca": "", "unidade": "1kg", "qtd_por_cesta": 3, "estoque_atual": 21, "preco_atual": 5.25},
    ])


def test_custo_cesta():
    assert calc.custo_cesta(_df()) == pytest.approx(56.75)


def test_cestas_possiveis_estoque():
    assert calc.cestas_possiveis_estoque(_df()) == 3


def test_cestas_possiveis_estoque_negativo_nao_fica_negativo():
    df = _df()
    df.loc[0, "estoque_atual"] = -5
    assert calc.cestas_possiveis_estoque(df) == 0


def test_cestas_possiveis_orcamento():
    df = _df()  # custo total 56.75
    assert calc.cestas_possiveis_orcamento(df, 113.50) == 2
    assert calc.cestas_possiveis_orcamento(df, 56) == 0
    assert calc.cestas_possiveis_orcamento(df, 0) == 0


def test_faltando_comprar():
    out = calc.faltando_comprar(_df(), 5)
    assert len(out) == 1
    assert out.iloc[0]["nome"] == "Arroz"
    assert out.iloc[0]["faltando"] == 3
    assert out.iloc[0]["custo_reposicao"] == pytest.approx(61.5)
