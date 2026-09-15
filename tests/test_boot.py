from src import boot


def test_mensagem_padrao_pt_br_sem_acento():
    assert boot.MENSAGEM_ERRO_BOOT == "Falha ao iniciar o app. Tente recarregar a pagina."


def test_helper_retorna_generico_e_nao_vaza_detalhe():
    try:
        raise RuntimeError("segredo-sensivel-123")
    except RuntimeError as exc:
        msg = boot.mensagem_erro_boot(exc)
    assert msg == boot.MENSAGEM_ERRO_BOOT
    assert "segredo-sensivel-123" not in msg
    assert "Traceback" not in msg
