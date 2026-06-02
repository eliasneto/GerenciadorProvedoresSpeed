from datetime import date, datetime
from decimal import Decimal

from core.models import IntegrationAudit, IntegrationAuditItem


def _json_safe(value):
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    try:
        if value != value:
            return None
    except Exception:
        pass
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except Exception:
            pass
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def dataframe_to_records(dataframe):
    records = []
    for idx, row in dataframe.iterrows():
        dados = {str(k).strip(): _json_safe(v) for k, v in row.to_dict().items()}
        records.append({"linha_numero": int(idx) + 2, "dados_json": dados})
    return records


def criar_auditoria_integracao(
    *,
    integration,
    action,
    usuario=None,
    arquivo_nome=None,
    total_registros=0,
    total_sucessos=0,
    total_erros=0,
    detalhes=None,
    itens=None,
):
    return IntegrationAudit.objects.create(
        integration=integration,
        action=action,
        usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
        arquivo_nome=arquivo_nome,
        total_registros=total_registros or 0,
        total_sucessos=total_sucessos or 0,
        total_erros=total_erros or 0,
        detalhes_json=_json_safe(detalhes or {}),
    )


def registrar_item_auditoria_integracao(
    audit,
    *,
    linha_numero=None,
    status="importado",
    mensagem=None,
    dados_json=None,
):
    return IntegrationAuditItem.objects.create(
        audit=audit,
        linha_numero=linha_numero,
        status=status,
        mensagem=mensagem,
        dados_json=_json_safe(dados_json or {}),
    )


def atualizar_auditoria_integracao(
    audit,
    *,
    total_registros=None,
    total_sucessos=None,
    total_erros=None,
    detalhes=None,
):
    campos_atualizados = []

    if total_registros is not None:
        audit.total_registros = total_registros
        campos_atualizados.append("total_registros")

    if total_sucessos is not None:
        audit.total_sucessos = total_sucessos
        campos_atualizados.append("total_sucessos")

    if total_erros is not None:
        audit.total_erros = total_erros
        campos_atualizados.append("total_erros")

    if detalhes is not None:
        detalhes_existentes = audit.detalhes_json or {}
        if isinstance(detalhes_existentes, dict) and isinstance(detalhes, dict):
            detalhes_mesclados = {**detalhes_existentes, **_json_safe(detalhes)}
        else:
            detalhes_mesclados = _json_safe(detalhes)
        audit.detalhes_json = detalhes_mesclados
        campos_atualizados.append("detalhes_json")

    if campos_atualizados:
        audit.save(update_fields=campos_atualizados)

    return audit


def registrar_auditoria_integracao(
    *,
    integration,
    action,
    usuario=None,
    arquivo_nome=None,
    total_registros=0,
    total_sucessos=0,
    total_erros=0,
    detalhes=None,
    itens=None,
):
    audit = criar_auditoria_integracao(
        integration=integration,
        action=action,
        usuario=usuario,
        arquivo_nome=arquivo_nome,
        total_registros=total_registros,
        total_sucessos=total_sucessos,
        total_erros=total_erros,
        detalhes=detalhes,
    )

    if itens:
        IntegrationAuditItem.objects.bulk_create(
            [
                IntegrationAuditItem(
                    audit=audit,
                    linha_numero=item.get("linha_numero"),
                    status=item.get("status", "importado"),
                    mensagem=item.get("mensagem"),
                    dados_json=_json_safe(item.get("dados_json") or {}),
                )
                for item in itens
            ]
        )

    return audit
