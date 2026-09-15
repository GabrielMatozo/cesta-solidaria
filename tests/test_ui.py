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


def test_avatar_mantem_size_valido():
    out = ui.avatar("Maria Silva", "sm")
    assert "avatar-sm" in out


def test_avatar_size_invalido_cai_para_md():
    out = ui.avatar("Maria Silva", 'md"><script>alert(1)</script>')
    assert "<script>" not in out
    assert 'class="avatar avatar-md"' in out


def test_avatar_size_desconhecido_cai_para_md():
    out = ui.avatar("Maria Silva", "lg")
    assert "avatar-md" in out
