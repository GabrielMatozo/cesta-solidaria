import datetime as _dt
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
TENDA_REGION_DEFAULT = "000010"
PRECO_STALE_DIAS_DEFAULT = 2


def agora_sp() -> datetime:
    return datetime.now(FUSO)


def formatar_data_hora(dt) -> str:
    """Formata data/hora no fuso de Sao Paulo.

    Aceita str ISO, datetime ou date. Qualquer outro tipo (None, NaN do
    pandas, numero) volta como string vazia - DataFrames transformam
    valores ausentes em float NaN, que nao e None.
    """
    if dt is None or isinstance(dt, (int, float)):
        return ""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return dt
    if isinstance(dt, _dt.date) and not isinstance(dt, datetime):
        dt = datetime(dt.year, dt.month, dt.day)
    if not isinstance(dt, datetime):
        return ""
    # Convencao unica do projeto: datetime naive e interpretado como UTC.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(FUSO).strftime("%d/%m/%Y %H:%M")


def _parse(dt):
    if dt is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(dt).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
    return parsed


def preco_desatualizado(ultima_atualizacao, dias: int) -> bool:
    parsed = _parse(ultima_atualizacao)
    if parsed is None:
        return True
    idade = agora_sp() - parsed.astimezone(FUSO)
    return idade > timedelta(days=dias)


def idade_preco_dias(ultima_atualizacao) -> int | None:
    parsed = _parse(ultima_atualizacao)
    if parsed is None:
        return None
    return max(0, (agora_sp() - parsed.astimezone(FUSO)).days)
