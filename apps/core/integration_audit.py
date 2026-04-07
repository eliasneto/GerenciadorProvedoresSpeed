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
    audit = IntegrationAudit.objects.create(
        integration=integration,
        action=action,
        usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
        arquivo_nome=arquivo_nome,
        total_registros=total_registros or 0,
        total_sucessos=total_sucessos or 0,
        total_erros=total_erros or 0,
        detalhes_json=_json_safe(detalhes or {}),
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
