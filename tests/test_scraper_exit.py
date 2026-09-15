import importlib.util
import os

import pytest


def _carregar_job():
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    caminho = os.path.join(raiz, "scripts", "scraper_tenda.py")
    spec = importlib.util.spec_from_file_location("scraper_job", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def job():
    return _carregar_job()


def test_tudo_ok_nao_falha(job):
    assert job.deve_falhar(0, 10, 10) is False


def test_falha_total_falha(job):
    assert job.deve_falhar(10, 0, 10) is True


def test_mais_da_metade_falhou_falha(job):
    assert job.deve_falhar(6, 4, 10) is True


def test_falha_unitaria_transitoria_nao_falha(job):
    assert job.deve_falhar(1, 9, 10) is False


def test_empate_nao_falha(job):
    assert job.deve_falhar(5, 5, 10) is False


def test_sem_com_token_nunca_falha(job):
    assert job.deve_falhar(0, 0, 0) is False
