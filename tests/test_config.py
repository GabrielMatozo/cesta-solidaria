from datetime import UTC, datetime, timedelta

from src import config


def test_agora_sp_eh_aware():
    agora = config.agora_sp()
    assert agora.tzinfo is not None


def test_formatar_data_hora_iso_utc():
    assert config.formatar_data_hora("2026-08-19T10:00:00+00:00") == "19/08/2026 07:00"


def test_formatar_data_hora_none():
    assert config.formatar_data_hora(None) == ""


def test_formatar_data_hora_naive_e_tratado_como_utc():
    assert config.formatar_data_hora("2026-01-01T10:00:00") == "01/01/2026 07:00"


def test_preco_recente_nao_desatualizado():
    recente = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
    assert config.preco_desatualizado(recente, dias=2) is False


def test_preco_velho_desatualizado():
    velho = (datetime.now(UTC) - timedelta(days=5)).isoformat()
    assert config.preco_desatualizado(velho, dias=2) is True


def test_preco_sem_data_desatualizado():
    assert config.preco_desatualizado(None, dias=2) is True


def test_idade_preco_dias():
    velho = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    assert config.idade_preco_dias(velho) == 3


def test_formatar_data_hora_nan_ou_float_retorna_vazio():
    import math
    assert config.formatar_data_hora(float("nan")) == ""
    assert config.formatar_data_hora(123.45) == ""
    assert config.formatar_data_hora(math.inf) == ""
