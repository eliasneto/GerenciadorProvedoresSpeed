from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import HistoricoSincronizacao


TIPOS_BLOQUEADOS = {
    "incremental": ["incremental"],
    "total": ["total"],
    "faxina": ["faxina"],
    "os_comercial_lastmile": ["os_comercial_lastmile"],
    "email_respostas_cotacao": ["email_respostas_cotacao"],
    "backup": ["backup"],
}


TIMEOUT_ROTINAS = {
    "incremental": timedelta(minutes=30),
    "total": timedelta(hours=8),
    "faxina": timedelta(hours=3),
    "os_comercial_lastmile": timedelta(hours=3),
    "email_respostas_cotacao": timedelta(minutes=20),
    "backup": timedelta(hours=6),
}


def _timeout_rotina(tipo):
    return TIMEOUT_ROTINAS.get(tipo, timedelta(hours=2))


def _encerrar_rotinas_presass(tipo):
    tipos = TIPOS_BLOQUEADOS.get(tipo, [tipo])
    limite = timezone.now() - _timeout_rotina(tipo)
    rotinas_presass = HistoricoSincronizacao.objects.filter(
        tipo__in=tipos,
        status="rodando",
        data_fim__isnull=True,
        data_inicio__lt=limite,
    )
    if not rotinas_presass.exists():
        return

    detalhes_timeout = (
        "Encerrado automaticamente por timeout de seguranca da trava de sincronizacao."
    )
    for historico in rotinas_presass:
        historico.status = "erro"
        historico.data_fim = timezone.now()
        historico.detalhes = (
            f"{historico.detalhes}\n{detalhes_timeout}".strip()
            if historico.detalhes
            else detalhes_timeout
        )
        historico.save(update_fields=["status", "data_fim", "detalhes"])


def buscar_rotina_em_execucao(tipo):
    _encerrar_rotinas_presass(tipo)
    tipos = TIPOS_BLOQUEADOS.get(tipo, [tipo])
    return (
        HistoricoSincronizacao.objects.filter(
            tipo__in=tipos,
            status="rodando",
            data_fim__isnull=True,
        )
        .order_by("data_inicio")
        .first()
    )


@transaction.atomic
def iniciar_historico_com_trava(tipo, origem="automatica", executado_por=None, detalhes=""):
    rotina_ativa = buscar_rotina_em_execucao(tipo)
    if rotina_ativa:
        return None, rotina_ativa

    historico = HistoricoSincronizacao.objects.create(
        tipo=tipo,
        status="rodando",
        origem=origem,
        executado_por=executado_por,
        detalhes=detalhes,
    )
    return historico, None


def descrever_rotina_em_execucao(tipo, historico):
    return (
        f"Ja existe uma rotina '{tipo}' em execucao "
        f"(historico #{historico.id}, iniciada em {historico.data_inicio:%d/%m/%Y %H:%M})."
    )
