from src import pdf


def test_gerar_pdf_retorna_bytes():
    itens = [
        {"produto": "Arroz (5kg)", "estoque": 1, "comprar": 3, "custo": 61.5},
        {"produto": "Feijão (1kg)", "estoque": 21, "comprar": 0, "custo": 0.0},
    ]
    out = pdf.gerar_pdf_lista_compras(itens, 61.5, "19/08/2026 07:00")
    assert out[:4] == b"%PDF"
    assert b"TOTAL" in out
    assert b"Arroz" in out
    assert b"19/08/2026" in out
