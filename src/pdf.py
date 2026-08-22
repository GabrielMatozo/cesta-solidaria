from fpdf import FPDF
from fpdf.enums import XPos, YPos

LARGESTA_NOME = 38


def gerar_pdf_lista_compras(itens: list[dict], total: float, data_preco: str) -> bytes:
    pdf = FPDF()
    pdf.set_compression(False)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(190, 10, "Lista de Compras - Cesta Solidaria", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(190, 8, f"Precos atualizados em: {data_preco}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def cabecalho_tabela():
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(70, 8, "Produto", 1)
        pdf.cell(30, 8, "Estoque", 1)
        pdf.cell(30, 8, "Comprar", 1)
        pdf.cell(40, 8, "Custo", 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)

    cabecalho_tabela()
    for item in itens:
        if pdf.will_page_break(8):
            cabecalho_tabela()
        nome = str(item["produto"]).encode("latin-1", "replace").decode("latin-1")
        if len(nome) > LARGESTA_NOME:
            nome = nome[:LARGESTA_NOME - 3] + "..."
        pdf.cell(70, 8, nome, 1)
        pdf.cell(30, 8, str(item["estoque"]), 1)
        pdf.cell(30, 8, str(item["comprar"]), 1)
        pdf.cell(40, 8, f'R$ {item["custo"]:.2f}', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(190, 10, f"TOTAL: R$ {total:.2f}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())
