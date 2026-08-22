import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import db


def backup() -> dict:
    # profiles fica de fora: contem emails e papeis de conta; o arquivo
    # circula (download/artifact) fora do controle do banco.
    tabelas = {
        "produtos": db.listar_produtos(None, service=True),
        "precos_historico": db.listar_tabela("precos_historico", None, service=True),
        "compras": db.listar_tabela("compras", None, service=True),
        "regions": db.listar_tabela("regions", None, service=True),
        "config": db.listar_tabela("config", None, service=True),
    }
    return tabelas


if __name__ == "__main__":
    dados = backup()
    conteudo = json.dumps(dados, ensure_ascii=False, default=str)
    checksum = hashlib.sha256(conteudo.encode()).hexdigest()

    print(conteudo, file=sys.stdout)

    contagens = {tabela: len(rows) for tabela, rows in dados.items()}
    for tabela, n in contagens.items():
        print(f"[backup] {tabela}: {n} linhas", file=sys.stderr)
    print(f"[backup] sha256: {checksum}", file=sys.stderr)
    if contagens.get("precos_historico", 0) == 0:
        print("[backup] AVISO: precos_historico vazio - verifique se o scraper rodou antes", file=sys.stderr)
