"""PO-066/RN-042: numero de rastreio usado no assunto do e-mail enviado a
partir da Escola (nivel "Global", RN-023) ou de um RE/RI/Mapa Calor
(RN-029/RN-043), no mesmo espirito do codigo `#123456` ja usado para
cotacao (`apps/core_admin/quotes_views.py::_build_quote_email_subject`).
Usado tanto para montar o assunto no envio quanto para correlacionar a
resposta recebida ao registro de origem certo (`apps/integracoes/email/
sincronizar_respostas_email_cotacao.py`).

Decisao do usuario (2026-08-11): codigo = data do dia do envio + INEP da
Escola + sufixo do nivel (`RE`, `RI`, `MC` ou `Global`; `MC` acrescentado
na RN-043/PO-067). Formato de separadores/ordem no assunto e decisao
tecnica do Dev (RN-042): prefixo `ESC-` (para nunca colidir com o codigo
puramente numerico da cotacao, `Proposal.codigo_proposta`) seguido de
`AAAAMMDD-INEP-SUFIXO`, ex.: `ESC-20260811-12345678-RE`.

Modulo sem dependencia de nenhum model — importavel tanto pela camada de
aplicacao (`apps.core_admin`, ao montar o assunto no envio) quanto pela
camada de integracao (`apps.integracoes.email`, ao interpretar a resposta),
sem violar a ordem de camada da ADR-007."""
import re
from datetime import date

from django.conf import settings
from django.utils import timezone

NIVEL_RE = "re"
NIVEL_RI = "ri"
NIVEL_MC = "mc"
NIVEL_GLOBAL = "global"

SUFIXO_POR_NIVEL = {
    NIVEL_RE: "RE",
    NIVEL_RI: "RI",
    NIVEL_MC: "MC",
    NIVEL_GLOBAL: "Global",
}
NIVEL_POR_SUFIXO = {sufixo.lower(): nivel for nivel, sufixo in SUFIXO_POR_NIVEL.items()}

PREFIXO_CODIGO = "ESC"

_CODIGO_PATTERN = re.compile(
    r"\b" + PREFIXO_CODIGO + r"-(\d{8})-([A-Za-z0-9]+)-(RE|RI|MC|Global)\b",
    re.IGNORECASE,
)


def _sanitizar_inep(inep):
    limpo = re.sub(r"[^A-Za-z0-9]", "", str(inep or ""))
    return limpo or "SEMINEP"


def montar_codigo_rastreio(inep, nivel, data_envio=None):
    """Monta o codigo de rastreio (RN-042) para o nivel informado
    (NIVEL_RE/NIVEL_RI/NIVEL_GLOBAL). `data_envio` e a data do dia do envio
    (padrao: hoje, fuso local)."""
    if nivel not in SUFIXO_POR_NIVEL:
        raise ValueError(f"Nivel de rastreio invalido: {nivel!r}")

    if data_envio is None:
        # Mesmo padrao de `Proposal.montar_codigo_proposta`
        # (apps/partners/models.py): `timezone.localdate()` exige
        # `USE_TZ=True` (nao e o caso deste projeto, ver config/settings.py).
        data_envio = timezone.localdate() if settings.USE_TZ else date.today()
    sufixo = SUFIXO_POR_NIVEL[nivel]
    return f"{PREFIXO_CODIGO}-{data_envio:%Y%m%d}-{_sanitizar_inep(inep)}-{sufixo}"


def montar_assunto_com_codigo(codigo, assunto):
    """Mesmo padrao de `_build_quote_email_subject` (quotes_views.py):
    prefixa o assunto com `#{codigo}`, sem duplicar se o usuario ja tiver
    incluido o prefixo."""
    codigo = (codigo or "").strip()
    assunto = (assunto or "").strip()

    if not codigo:
        return assunto

    prefixo = f"#{codigo}"
    if assunto.startswith(prefixo):
        return assunto

    return f"{prefixo} - {assunto}" if assunto else prefixo


def extrair_codigos_rastreio(assunto):
    """Extrai, em ordem de aparicao, os codigos de rastreio (RN-042)
    presentes no assunto de um e-mail recebido. Devolve o codigo no
    formato canonico (sufixo com a capitalizacao padrao)."""
    if not assunto:
        return []

    encontrados = []
    for match in _CODIGO_PATTERN.finditer(assunto):
        data_str, inep, sufixo_bruto = match.groups()
        nivel = NIVEL_POR_SUFIXO.get(sufixo_bruto.lower())
        if not nivel:
            continue
        codigo = f"{PREFIXO_CODIGO}-{data_str}-{inep}-{SUFIXO_POR_NIVEL[nivel]}"
        if codigo not in encontrados:
            encontrados.append(codigo)
    return encontrados


def decompor_codigo_rastreio(codigo):
    """Devolve `(inep, nivel)` a partir de um codigo valido, ou `None`
    quando o codigo nao segue o formato esperado."""
    match = _CODIGO_PATTERN.fullmatch((codigo or "").strip())
    if not match:
        return None

    _data_str, inep, sufixo_bruto = match.groups()
    nivel = NIVEL_POR_SUFIXO.get(sufixo_bruto.lower())
    if not nivel:
        return None
    return inep, nivel
