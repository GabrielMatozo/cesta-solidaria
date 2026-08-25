import pandas as pd

from src import estoque


def _df():
    return pd.DataFrame([
        {"id": 1, "nome": "Feijão", "marca": "Camil", "qtd_por_cesta": 3,
         "estoque_atual": 21, "preco_atual": 5.25, "token_tenda": None,
         "ultima_atualizacao_preco": None},
        {"id": 2, "nome": "Arroz", "marca": "Camil", "qtd_por_cesta": 2,
         "estoque_atual": 7, "preco_atual": 20.5, "token_tenda": "arroz-token",
         "ultima_atualizacao_preco": "2026-08-01T10:00:00+00:00"},
    ])


def test_ordenar_por_nome():
    out = estoque.ordenar(_df(), "nome", True)
    assert out.iloc[0]["nome"] == "Arroz"


def test_ordenar_por_preco_decrescente():
    out = estoque.ordenar(_df(), "preco_atual", False)
    assert out.iloc[0]["nome"] == "Arroz"


def test_ordenar_por_custo_cesta():
    out = estoque.ordenar(_df(), "custo_cesta", True)
    assert out.iloc[0]["nome"] == "Feijão"


def test_ordenar_campo_invalido_nao_quebra():
    assert len(estoque.ordenar(_df(), "inexistente", True)) == 2


def test_filtrar_texto():
    assert len(estoque.filtrar(_df(), "arroz", "todos", dias=2)) == 1


def test_filtrar_status_manual():
    assert len(estoque.filtrar(_df(), "", "manual", dias=2)) == 1


def test_filtrar_status_automatico():
    assert len(estoque.filtrar(_df(), "", "automático", dias=2)) == 1


def test_filtrar_status_desatualizado():
    out = estoque.filtrar(_df(), "", "desatualizado", dias=2)
    assert list(out["nome"]) == ["Arroz"]


def test_filtrar_texto_metacaracteres():
    assert len(estoque.filtrar(_df(), "a.r", "todos", dias=2)) == 0


def test_limpar_nan_converte_para_none():
    registros = [{"nome": "Arroz", "token_tenda": float("nan"), "preco_atual": 1.5}]
    out = estoque.limpar_nan(registros)
    assert out[0]["nome"] == "Arroz"
    assert out[0]["token_tenda"] is None
    assert out[0]["preco_atual"] == 1.5


def test_limpar_nan_preserva_original():
    registros = [{"nome": "Arroz", "token_tenda": float("nan")}]
    estoque.limpar_nan(registros)
    assert pd.isna(registros[0]["token_tenda"])


def test_normalizar_ativo_variacoes():
    from src import estoque as mod
    assert mod.normalizar_ativo(True) is True
    assert mod.normalizar_ativo("true") is True
    assert mod.normalizar_ativo("SIM") is True
    assert mod.normalizar_ativo("1") is True
    assert mod.normalizar_ativo("false") is False
    assert mod.normalizar_ativo("0") is False
    assert mod.normalizar_ativo("") is False
    assert mod.normalizar_ativo(None) is False
