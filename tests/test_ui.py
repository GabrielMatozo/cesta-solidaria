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


def test_stat_card_icon_malicioso_vira_texto_escapado():
    out = ui.stat_card("L", "V", '</div><script>alert(1)</script>')
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_stat_card_badge_malicioso_vira_escapado():
    out = ui.stat_card("L", "V", "box", "green", '<script>alert(1)</script>')
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_stat_card_chave_box_renderiza_svg():
    out = ui.stat_card("L", "V", "box")
    assert "<svg" in out


def test_stat_card_badge_valido_passa():
    out = ui.stat_card("L", "V", "box", "green", ui.badge("3 itens", "warning"))
    assert '<span class="badge badge-warning">' in out


def test_listar_desatualizados_ignora_token_nan():
    import pandas as pd

    df = pd.DataFrame([
        {"token_tenda": float("nan"), "ultima_atualizacao_preco": "2026-08-01T10:00:00+00:00"},
    ])
    assert len(ui.listar_desatualizados(df, 2)) == 0


def test_listar_desatualizados_lista_token_valido():
    import pandas as pd

    df = pd.DataFrame([
        {"token_tenda": "arroz-token", "ultima_atualizacao_preco": "2026-08-01T10:00:00+00:00"},
    ])
    assert len(ui.listar_desatualizados(df, 2)) == 1
