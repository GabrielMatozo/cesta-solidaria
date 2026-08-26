import os
import sys
from datetime import UTC, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config, db
from src import scraper_tenda as scraper


def main() -> int:
    region_id = db.get_config("tenda_region_id", None, service=True) or config.TENDA_REGION_DEFAULT
    produtos = db.listar_produtos(None, service=True)
    com_token = [p for p in produtos if p.get("token_tenda")]
    if not com_token:
        print("Nenhum produto com token_tenda para atualizar.", file=sys.stderr)
        return 0

    falhas = 0
    sem_match = 0
    agora = datetime.now(UTC).isoformat()
    hoje = datetime.now(UTC).date().isoformat()
    historico = []
    atualizados = []
    vencedores = []
    cliente = scraper.TendaScraper(region_id=region_id)
    try:
        for prod in com_token:
            preco = None
            slug_vencedor = prod["token_tenda"]
            marca_vencedora = ""
            try:
                if prod.get("termo_busca"):
                    # Marca mais barata do mesmo produto/peso; token_tenda passa
                    # a apontar para o vencedor do dia.
                    vencedor = cliente.buscar_mais_barato(
                        prod["termo_busca"], unidade_alvo=prod.get("unidade") or ""
                    )
                    if not vencedor:
                        print(
                            f"[AVISO] {prod['nome']}: nenhum candidato "
                            f"{prod['termo_busca']!r} com peso {prod.get('unidade')!r}; "
                            "mantendo preco anterior",
                            file=sys.stderr,
                        )
                        sem_match += 1
                        continue
                    preco = vencedor.preco
                    slug_vencedor = vencedor.slug
                    marca_vencedora = vencedor.marca or ""
                else:
                    resultado = cliente.buscar_preco_produto(prod["token_tanda"], region_id)
                    preco = resultado["preco"]
            except Exception as err:
                falhas += 1
                print(f"[ERRO] {prod['nome']} ({prod['token_tenda']}): {err}", file=sys.stderr)
                continue

            historico.append({
                "produto_id": prod["id"],
                "preco": preco,
                "dia": hoje,
                "region_id": region_id,
            })
            atualizados.append({
                "id": prod["id"],
                "preco_atual": preco,
                "ultima_atualizacao_preco": agora,
            })
            if prod.get("termo_busca"):
                vencedores.append({
                    "id": prod["id"],
                    "token_tenda": slug_vencedor,
                    "url_tenda": f"https://www.tendaatacado.com.br/produto/{slug_vencedor}",
                    "marca": marca_vencedora,
                })
            print(f"[OK] {prod['nome']}: R$ {preco}")
    finally:
        cliente.close()

    if historico:
        db.inserir_precos_historico(historico, service=True)
    if atualizados:
        db.upsert_produtos(atualizados, None, service=True)
    if vencedores:
        # Aponta cada produto para a marca vencedora de hoje.
        db.upsert_produtos(vencedores, None, service=True)

    # Resumo diario do custo da cesta (itens ativos, marcas vencedoras)
    catalogo = db.listar_produtos(None, service=True)
    itens_cesta = []
    for p in catalogo:
        if not p.get("ativo"):
            continue
        qtd = p.get("qtd_por_cesta") or 0
        preco_atual = float(p.get("preco_atual") or 0)
        subtotal = float(qtd) * preco_atual
        itens_cesta.append((p["nome"], qtd, preco_atual, subtotal))
    total_cesta = sum(s for *_, s in itens_cesta)

    print("\n===== CESTA DE HOJE (marcas mais baratas do dia) =====", file=sys.stderr)
    for nome, qtd, preco_item, sub in sorted(itens_cesta, key=lambda x: -x[3]):
        print(f"{nome}: {qtd} x R$ {preco_item:.2f} = R$ {sub:.2f}", file=sys.stderr)
    print(f"TOTAL DA CESTA: R$ {total_cesta:.2f}", file=sys.stderr)
    with open("custo_cesta.txt", "w", encoding="utf-8") as fh:
        fh.write(f"Cesta Solidaria - {hoje}\n\n")
        for nome, qtd, preco_item, sub in sorted(itens_cesta, key=lambda x: -x[3]):
            fh.write(f"{nome}: {qtd} x R$ {preco_item:.2f} = R$ {sub:.2f}\n")
        fh.write(f"\nTOTAL: R$ {total_cesta:.2f}\n")

    print(
        f"Atualizados {len(atualizados)} de {len(com_token)} produtos. "
        f"Falhas: {falhas}. Sem match de peso: {sem_match}"
    )
    # Falha unitaria transitoria nao deve abrir issue; so falha total.
    return 0 if atualizados else (1 if com_token else 0)


if __name__ == "__main__":
    raise SystemExit(main())
