import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config, csv_io, db, estoque


def aplicar(rows):
    rows = estoque.limpar_nan(rows)
    if not rows:
        print("Nenhuma linha para importar.", file=sys.stderr)
        return
    # ignore_duplicates: seed é bootstrap inicial; nunca sobrescreve estado
    # operacional (estoque_atual, preco_atual) de produtos já existentes.
    db.upsert_produtos(rows, None, service=True, ignore_duplicates=True)
    print(f"Upsert de {len(rows)} produtos via service role (existentes preservados).")


def garantir_bases():
    try:
        ids_existentes = {r["region_id"] for r in db.listar_regions(None, service=True)}
        if config.TENDA_REGION_DEFAULT not in ids_existentes:
            db.upsert_regions(
                [{
                    "region_id": config.TENDA_REGION_DEFAULT,
                    "nome": "Indaiatuba",
                    "ativo": True,
                }],
                service=True,
            )
        if db.get_config("tenda_region_id", None, service=True) is None:
            db.set_config("tenda_region_id", config.TENDA_REGION_DEFAULT, service=True)
    except Exception as err:
        print(f"[AVISO] Falha ao semear regions/config: {err}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="seed/produtos_initial.csv")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"Arquivo não encontrado: {args.csv}", file=sys.stderr)
        return 1

    garantir_bases()

    with open(args.csv, encoding="utf-8") as fh:
        df = csv_io.ler_csv(fh.read())

    cols = ["nome", "marca", "unidade", "qtd_por_cesta", "estoque_atual",
            "preco_atual", "token_tenda", "url_tenda", "ativo"]
    for col in cols:
        if col not in df.columns:
            df[col] = None
    df["qtd_por_cesta"] = df["qtd_por_cesta"].fillna(1)
    df["estoque_atual"] = df["estoque_atual"].fillna(0)
    df["ativo"] = df["ativo"].map(estoque.normalizar_ativo).where(df["ativo"].notna(), True)
    if "id" in df.columns:
        df["id"] = df["id"].where(df["id"].notna(), None)

    aplicar(df[["id"] + cols if "id" in df.columns else cols].to_dict("records"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
