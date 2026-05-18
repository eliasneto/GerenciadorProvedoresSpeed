import csv
import json
from io import BytesIO

import pandas as pd
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html


def _json_dump(value):
    if value in (None, "", {}, []):
        return ""
    return json.dumps(value, ensure_ascii=False)


def _format_datetime(value):
    if not value:
        return ""
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return value.strftime("%d/%m/%Y %H:%M:%S")


def _ordered_item_data_columns(audit, items):
    ordered = []
    detalhes = audit.detalhes_json if isinstance(audit.detalhes_json, dict) else {}
    colunas = detalhes.get("colunas")

    if isinstance(colunas, list):
        for coluna in colunas:
            coluna_texto = str(coluna or "").strip()
            if coluna_texto and coluna_texto not in ordered:
                ordered.append(coluna_texto)

    for item in items:
        if not isinstance(item.dados_json, dict):
            continue
        for coluna in item.dados_json.keys():
            coluna_texto = str(coluna or "").strip()
            if coluna_texto and coluna_texto not in ordered:
                ordered.append(coluna_texto)

    return ordered


def build_integration_audit_export(audit):
    items = list(audit.items.order_by("id"))
    item_columns = _ordered_item_data_columns(audit, items)

    itens = []
    for item in items:
        linha = {
            "Log_ID": audit.pk,
            "Integracao": audit.get_integration_display(),
            "Acao": audit.get_action_display(),
            "Arquivo": audit.arquivo_nome or "",
            "Usuario": getattr(audit.usuario, "username", "") or "",
            "Linha": item.linha_numero or "",
            "Status": item.get_status_display(),
            "Mensagem": item.mensagem or "",
            "Criado_Em_Item": _format_datetime(item.criado_em),
            "Dados_JSON_Bruto": _json_dump(item.dados_json),
        }

        dados_json = item.dados_json if isinstance(item.dados_json, dict) else {}
        for coluna in item_columns:
            valor = dados_json.get(coluna, "")
            if isinstance(valor, (dict, list)):
                valor = _json_dump(valor)
            linha[coluna] = valor

        itens.append(linha)

    resumo = [
        {
            "Log_ID": audit.pk,
            "Integracao": audit.get_integration_display(),
            "Acao": audit.get_action_display(),
            "Arquivo": audit.arquivo_nome or "",
            "Usuario": getattr(audit.usuario, "username", "") or "",
            "Total_Registros": audit.total_registros,
            "Total_Sucessos": audit.total_sucessos,
            "Total_Erros": audit.total_erros,
            "Criado_Em_Log": _format_datetime(audit.criado_em),
            "Detalhes_JSON_Bruto": _json_dump(audit.detalhes_json),
        }
    ]

    return resumo, itens


class IntegrationAuditExportAdminMixin:
    integration_audit_fields = (
        "integration",
        "action",
        "usuario",
        "arquivo_nome",
        "total_registros",
        "total_sucessos",
        "total_erros",
        "detalhes_json",
        "criado_em",
        "exportacoes_disponiveis",
    )

    def get_urls(self):
        opts = self.model._meta
        custom_urls = [
            path(
                "<path:object_id>/exportar/<str:formato>/",
                self.admin_site.admin_view(self.exportar_itens_integracao),
                name=f"{opts.app_label}_{opts.model_name}_exportar",
            )
        ]
        return custom_urls + super().get_urls()

    def exportar_itens_integracao(self, request, object_id, formato):
        audit = self.get_object(request, object_id)
        if audit is None:
            raise Http404("Log de integracao nao encontrado.")
        if not self.has_view_permission(request, audit):
            raise PermissionDenied

        resumo, itens = build_integration_audit_export(audit)
        nome_base = f"log_integracao_{audit.pk}"

        if formato == "csv":
            return self._exportar_csv(nome_base, itens)
        if formato in {"xlsx", "excel"}:
            return self._exportar_excel(nome_base, resumo, itens)
        raise Http404("Formato de exportacao invalido.")

    def _exportar_csv(self, nome_base, itens):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{nome_base}.csv"'
        response.write("\ufeff")

        headers = list(itens[0].keys()) if itens else [
            "Log_ID",
            "Integracao",
            "Acao",
            "Arquivo",
            "Usuario",
            "Linha",
            "Status",
            "Mensagem",
            "Criado_Em_Item",
            "Dados_JSON_Bruto",
        ]

        writer = csv.DictWriter(response, fieldnames=headers)
        writer.writeheader()
        for item in itens:
            writer.writerow(item)
        return response

    def _exportar_excel(self, nome_base, resumo, itens):
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            pd.DataFrame(resumo).to_excel(writer, sheet_name="Resumo", index=False)
            pd.DataFrame(itens).to_excel(writer, sheet_name="Itens", index=False)

        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{nome_base}.xlsx"'
        return response

    def exportacoes_disponiveis(self, obj):
        if not obj or not obj.pk:
            return "-"

        url_csv = reverse(
            f"admin:{obj._meta.app_label}_{obj._meta.model_name}_exportar",
            args=[obj.pk, "csv"],
        )
        url_xlsx = reverse(
            f"admin:{obj._meta.app_label}_{obj._meta.model_name}_exportar",
            args=[obj.pk, "xlsx"],
        )
        return format_html(
            '<a class="button" href="{}">Exportar CSV</a>&nbsp;'
            '<a class="button" href="{}">Exportar Excel</a>',
            url_csv,
            url_xlsx,
        )

    exportacoes_disponiveis.short_description = "Exportacoes"
