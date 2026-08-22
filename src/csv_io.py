import io

import pandas as pd

COLUNAS_CSV = [
    "id", "nome", "marca", "unidade", "qtd_por_cesta", "estoque_atual",
    "preco_atual", "token_tenda", "url_tenda", "ativo", "ultima_atualizacao_preco",
]


def produtos_to_csv(df: pd.DataFrame) -> str:
    cols = [c for c in COLUNAS_CSV if c in df.columns]
    return df[cols].to_csv(index=False)


def ler_csv(texto: str) -> pd.DataFrame:
    return pd.read_csv(io.StringIO(texto))


def validar_csv(df: pd.DataFrame) -> list[str]:
    erros = []
    for col in ["nome", "qtd_por_cesta", "estoque_atual"]:
        if col not in df.columns:
            erros.append(f"Coluna obrigatoria ausente: {col}")
    if "nome" in df.columns and df["nome"].isna().any():
        erros.append("Existem produtos sem nome")
    for col in ["qtd_por_cesta", "estoque_atual", "preco_atual"]:
        if col in df.columns:
            try:
                pd.to_numeric(df[col])
            except (ValueError, TypeError):
                erros.append(f"Coluna {col} deve ser numerica")
    if "id" in df.columns:
        ids_presentes = df["id"].dropna()
        nao_numericos = ids_presentes[~ids_presentes.astype(str).str.fullmatch(r"\d+")]
        if not nao_numericos.empty:
            erros.append("Coluna id deve ser numerica (valores invalidos: "
                         + ", ".join(str(v) for v in nao_numericos.head(3)) + ")")
        duplicados = ids_presentes[ids_presentes.duplicated()]
        if not duplicados.empty:
            erros.append("Existem ids duplicados no CSV: "
                         + ", ".join(str(v) for v in sorted(set(duplicados.tolist()))[:5]))
    return erros


def _iguais(a, b) -> bool:
    if pd.isna(a) and pd.isna(b):
        return True
    if a == b:
        return True
    # Evita falso-positivo de "alterado" quando o mesmo valor numerico
    # vem em tipos diferentes (ex: "5" vindo do CSV vs 5 vindo do banco).
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return False


def diff_importacao(atual: pd.DataFrame, novo: pd.DataFrame) -> dict:
    atuais = atual.dropna(subset=["id"])
    mapa = {int(r["id"]): r for _, r in atuais.iterrows()}
    novos = []
    alterados = []
    campos = ["nome", "marca", "unidade", "qtd_por_cesta", "estoque_atual",
              "preco_atual", "token_tenda", "url_tenda", "ativo"]
    for _, r in novo.iterrows():
        rid = r.get("id")
        try:
            rid_int = int(rid)
        except (TypeError, ValueError):
            rid_int = None
        if rid_int is None or rid_int not in mapa:
            novos.append(r.to_dict())
            continue
        antigo = mapa[rid_int]
        for campo in campos:
            if campo not in r:
                continue
            if not _iguais(r[campo], antigo[campo]):
                alterados.append({
                    "id": int(rid), "produto": r.get("nome", antigo.get("nome", "")),
                    "campo": campo, "de": antigo[campo], "para": r[campo],
                })
    return {"novos": novos, "alterados": alterados}
