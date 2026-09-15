import traceback

MENSAGEM_ERRO_BOOT = "Falha ao iniciar o app. Tente recarregar a pagina."


def mensagem_erro_boot(exc: BaseException) -> str:
    traceback.print_exception(type(exc), exc, exc.__traceback__)
    return MENSAGEM_ERRO_BOOT
