from django.db import transaction

from .models import HistoricoSincronizacao


TIPOS_BLOQUEADOS = {
    "incremental": ["incremental"],
    "total": ["total"],
    "faxina": ["faxina"],
    "os_comercial_lastmile": ["os_comercial_lastmile"],
    "backup": ["backup"],
}


def buscar_rotina_em_execucao(tipo):
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
