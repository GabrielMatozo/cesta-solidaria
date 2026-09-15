from src import ui


def test_badge_escapa_texto():
    out = ui.badge("<script>alert(1)</script>", "primary")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_badge_mantem_variant_valido():
    out = ui.badge("Adm", "primary")
    assert "badge-primary" in out


def test_badge_invalido_cai_para_neutro():
    out = ui.badge("X", 'neutral"><script>alert(1)</script>')
    assert "<script>" not in out
    assert "badge-neutral" in out
