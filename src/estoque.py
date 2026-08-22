import pandas as pd

from src import config

CAMPOS_ORDENACAO = {"nome", "marca", "preco_atual", "estoque_atual", "custo_cesta"}


def ordenar(df: pd.DataFrame, campo: str, crescente: bool = True) -> pd.DataFrame:
    if df.empty or campo not in CAMPOS_ORDENACAO:
        return df
    if campo == "custo_cesta" and "custo_cesta" not in df.columns:
        df = df.copy()
        df["custo_cesta"] = df["qtd_por_cesta"] * df["preco_atual"]
    return df.sort_values(campo, ascending=crescente).reset_index(drop=True)


def limpar_nan(registros: list[dict]) -> list[dict]:
    return [
        {k: (None if pd.isna(v) else v) for k, v in reg.items()}
        for reg in registros
    ]


def filtrar(df: pd.DataFrame, texto: str, status: str, dias: int) -> pd.DataFrame:
    out = df.copy()
    if texto:
        mask = (
            out["nome"].str.contains(texto, case=False, na=False, regex=False)
            | out["marca"].str.contains(texto, case=False, na=False, regex=False)
        )
        out = out[mask]
    if status == "automático":
        out = out[out["token_tenda"].notna()]
    elif status == "manual":
        out = out[out["token_tenda"].isna()]
    elif status == "desatualizado":
        automaticos = out["token_tenda"].notna()
        stale = out["ultima_atualizacao_preco"].apply(
            lambda u: config.preco_desatualizado(u, dias)
        )
        out = out[automaticos & stale]
    return out.reset_index(drop=True)


def normalizar_ativo(valor) -> bool:
    """Converte representacoes comuns de booleano ('false', '0', 'sim'...)."""
    if isinstance(valor, bool):
        return valor
    return str(valor).strip().lower() in ("true", "1", "sim", "s", "yes", "t")
