import pandas as pd

from src import csv_io


def _df():
    return pd.DataFrame([
        {"id": 1, "nome": "Arroz", "marca": "Camil", "unidade": "5kg",
         "qtd_por_cesta": 2, "estoque_atual": 7, "preco_atual": 20.5,
         "token_tenda": "arroz-branco-t1-camil-selecoes-5kg", "url_tenda": "",
         "ativo": True, "ultima_atualizacao_preco": None}
    ])


def test_produtos_to_csv_contem_cabecalho():
    csv = csv_io.produtos_to_csv(_df())
    assert csv.startswith("id,nome,marca")
    assert "Arroz" in csv


def test_ler_csv_roundtrip():
    csv = csv_io.produtos_to_csv(_df())
    df = csv_io.ler_csv(csv)
    assert df.iloc[0]["nome"] == "Arroz"
    assert df.iloc[0]["qtd_por_cesta"] == 2


def test_validar_csv_ok():
    assert csv_io.validar_csv(_df()) == []


def test_validar_csv_coluna_ausente():
    df = _df().drop(columns=["qtd_por_cesta"])
    assert "Coluna obrigatoria ausente: qtd_por_cesta" in csv_io.validar_csv(df)


def test_validar_csv_nome_vazio():
    df = _df()
    df.loc[0, "nome"] = None
    assert any("nome" in e for e in csv_io.validar_csv(df))


def test_validar_csv_nao_numerica():
    df = _df()
    df["preco_atual"] = df["preco_atual"].astype(object)
    df.loc[0, "preco_atual"] = "abc"
    assert any("preco_atual deve ser numerica" in e for e in csv_io.validar_csv(df))


def test_validar_csv_id_nao_numerico():
    df = _df()
    df["id"] = df["id"].astype(object)
    df.loc[0, "id"] = "abc"
    assert any("id" in e for e in csv_io.validar_csv(df))


def test_validar_csv_id_duplicado():
    df = pd.concat([_df(), _df()], ignore_index=True)
    erros = csv_io.validar_csv(df)
    assert any("duplicado" in e for e in erros)


def test_diff_importacao():
    atual = _df()
    novo = pd.DataFrame([
        {"id": 1, "nome": "Arroz", "marca": "Camil", "unidade": "5kg",
         "qtd_por_cesta": 2, "estoque_atual": 10, "preco_atual": 20.5,
         "token_tenda": "arroz-branco-t1-camil-selecoes-5kg", "url_tenda": "",
         "ativo": True, "ultima_atualizacao_preco": None},
        {"id": None, "nome": "Feijão", "marca": "", "unidade": "1kg",
         "qtd_por_cesta": 3, "estoque_atual": 21, "preco_atual": 5.25,
         "token_tenda": None, "url_tenda": "", "ativo": True,
         "ultima_atualizacao_preco": None},
    ])
    diff = csv_io.diff_importacao(atual, novo)
    assert len(diff["novos"]) == 1
    assert diff["novos"][0]["nome"] == "Feijão"
    assert len(diff["alterados"]) == 1
    assert diff["alterados"][0]["campo"] == "estoque_atual"
    assert diff["alterados"][0]["de"] == 7
    assert diff["alterados"][0]["para"] == 10


def test_diff_importacao_nan_nan_nao_conta_como_alterado():
    atual = pd.DataFrame([
        {"id": 1, "nome": "Arroz", "marca": "Camil", "unidade": "5kg",
         "qtd_por_cesta": 2, "estoque_atual": 7, "preco_atual": 20.5,
         "token_tenda": float("nan"), "url_tenda": "", "ativo": True,
         "ultima_atualizacao_preco": None},
    ])
    novo = pd.DataFrame([
        {"id": 1, "nome": "Arroz", "marca": "Camil", "unidade": "5kg",
         "qtd_por_cesta": 2, "estoque_atual": 7, "preco_atual": 20.5,
         "token_tenda": float("nan"), "url_tenda": "", "ativo": True,
         "ultima_atualizacao_preco": None},
    ])
    diff = csv_io.diff_importacao(atual, novo)
    assert diff["alterados"] == []
