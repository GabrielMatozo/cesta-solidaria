import pandas as pd


def custo_cesta(df: pd.DataFrame) -> float:
    if "qtd_por_cesta" not in df.columns or "preco_atual" not in df.columns:
        return 0.0
    return float((df["qtd_por_cesta"] * df["preco_atual"]).sum())


def cestas_possiveis_estoque(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    qtd = pd.to_numeric(df["qtd_por_cesta"], errors="coerce").fillna(0)
    if (qtd <= 0).any():
        return 0
    estoque = pd.to_numeric(df["estoque_atual"], errors="coerce").fillna(0)
    possiveis = (estoque / qtd).astype(int).clip(lower=0)
    return int(possiveis.min())


def cestas_possiveis_orcamento(df: pd.DataFrame, orcamento: float) -> int:
    """Quantas cestas completas o orcamento permite comprar do zero."""
    if orcamento <= 0 or df.empty:
        return 0
    custo = custo_cesta(df)
    if custo <= 0:
        return 0
    return int(orcamento // custo)


def faltando_comprar(df: pd.DataFrame, cestas_desejadas: int) -> pd.DataFrame:
    out = df.copy()
    out["qtd_necessaria"] = out["qtd_por_cesta"] * cestas_desejadas
    out["faltando"] = (out["qtd_necessaria"] - out["estoque_atual"]).clip(lower=0)
    out["custo_reposicao"] = out["faltando"] * out["preco_atual"]
    return out[out["faltando"] > 0].reset_index(drop=True)
