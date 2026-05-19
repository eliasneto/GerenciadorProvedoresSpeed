from io import BytesIO
import subprocess

import pandas as pd
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.http import urlencode

from clientes.sync_utils import buscar_rotina_em_execucao, descrever_rotina_em_execucao
from core.admin_integration_exports import IntegrationAuditExportAdminMixin
from core.integration_audit import dataframe_to_records, registrar_auditoria_integracao
from core.models import IntegrationAuditItem
from scripts.integracoes.backoffice.desativar_atendimento_ixc import executar_desativacao_atendimento

from .models import (
    CadastroClienteIXCAuditoria,
    CotacaoStatusAuditoria,
    EdicaoAtendimentoIXCAuditoria,
    EdicaoLoginIXCAuditoria,
    EmailCotacaoRespostaImportacaoAuditoria,
    EmailCotacaoRespostaSyncAuditoria,
    DesativacaoAtendimentoIXCAuditoria,
    HistoricoSincronizacaoAuditoria,
    IntegrationAuditAuditoria,
    IntegrationAuditItemAuditoria,
    LoginAuditoria,
    RestoreBackupAuditoria,
    LogAlteracaoIXCAuditoria,
    RegistroHistoricoAuditoria,
)


@admin.register(RegistroHistoricoAuditoria)
class RegistroHistoricoAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "tipo", "data")
    list_filter = ("tipo", "data")
    search_fields = ("usuario__username", "acao")


@admin.register(LoginAuditoria)
class LoginAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("criado_em", "acao", "sucesso", "username_informado", "usuario", "endereco_ip")
    list_filter = ("acao", "sucesso", "criado_em")
    search_fields = ("username_informado", "usuario__username", "endereco_ip", "detalhes")
    readonly_fields = ("usuario", "username_informado", "acao", "sucesso", "endereco_ip", "user_agent", "detalhes", "criado_em")


@admin.register(RestoreBackupAuditoria)
class RestoreBackupAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("criado_em", "arquivo_nome", "origem", "sucesso", "media_restaurada", "usuario", "endereco_ip")
    list_filter = ("origem", "sucesso", "media_restaurada", "criado_em")
    search_fields = ("arquivo_nome", "usuario__username", "endereco_ip", "detalhes")
    readonly_fields = ("usuario", "origem", "arquivo_nome", "sucesso", "media_restaurada", "endereco_ip", "user_agent", "detalhes", "criado_em")


@admin.register(CotacaoStatusAuditoria)
class CotacaoStatusAuditoriaAdmin(admin.ModelAdmin):
    list_display = (
        "criado_em",
        "codigo_cotacao",
        "parceiro_nome",
        "cliente_nome",
        "status_anterior",
        "status_novo",
        "origem",
        "integrou_ixc",
        "usuario",
    )
    list_filter = ("origem", "integrou_ixc", "status_anterior", "status_novo", "criado_em")
    search_fields = (
        "codigo_cotacao",
        "codigo_lote",
        "parceiro_nome",
        "cliente_nome",
        "endereco_referencia",
        "usuario__username",
        "detalhes",
    )
    readonly_fields = (
        "usuario",
        "proposal",
        "codigo_cotacao",
        "codigo_lote",
        "parceiro_nome",
        "cliente_nome",
        "endereco_referencia",
        "status_anterior",
        "status_novo",
        "origem",
        "integrou_ixc",
        "endereco_ip",
        "user_agent",
        "detalhes",
        "criado_em",
    )


@admin.register(EmailCotacaoRespostaSyncAuditoria)
class EmailCotacaoRespostaSyncAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("mailbox_email", "ativo", "ultima_sincronizacao_em", "atualizado_em")
    readonly_fields = ("atualizado_em", "ultima_sincronizacao_em", "ultimo_erro", "inbox_delta_link")


@admin.register(EmailCotacaoRespostaImportacaoAuditoria)
class EmailCotacaoRespostaImportacaoAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("proposal", "remetente", "assunto", "recebido_em", "importado_em")
    list_filter = ("recebido_em", "importado_em")
    search_fields = ("proposal__codigo_proposta", "assunto", "remetente", "graph_message_id", "internet_message_id")
    readonly_fields = (
        "proposal",
        "historico",
        "graph_message_id",
        "internet_message_id",
        "assunto",
        "remetente",
        "recebido_em",
        "importado_em",
    )


class IntegrationAuditItemInline(admin.TabularInline):
    model = IntegrationAuditItem
    extra = 0
    can_delete = False
    readonly_fields = ("linha_numero", "status", "mensagem", "dados_json", "criado_em")


@admin.register(IntegrationAuditAuditoria)
class IntegrationAuditAuditoriaAdmin(IntegrationAuditExportAdminMixin, admin.ModelAdmin):
    integration_audit_title = "Logs de Integracoes"
    integration_audit_eyebrow = "Auditoria central"
    integration_audit_subtitle = (
        "Acompanhe os logs tecnicos das automacoes, filtre por integracao ou acao "
        "e exporte os itens processados em formato estruturado."
    )
    list_display = (
        "integration",
        "action",
        "usuario",
        "arquivo_nome",
        "total_registros",
        "total_sucessos",
        "total_erros",
        "criado_em",
        "exportacoes_disponiveis",
    )
    list_filter = ("integration", "action", "criado_em")
    search_fields = ("usuario__username", "arquivo_nome")
    fields = IntegrationAuditExportAdminMixin.integration_audit_fields
    readonly_fields = IntegrationAuditExportAdminMixin.integration_audit_fields
    inlines = [IntegrationAuditItemInline]


@admin.register(IntegrationAuditItemAuditoria)
class IntegrationAuditItemAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("audit", "linha_numero", "status", "criado_em")
    list_filter = ("status", "criado_em", "audit__integration")
    search_fields = ("audit__arquivo_nome", "mensagem")
    readonly_fields = ("audit", "linha_numero", "status", "mensagem", "dados_json", "criado_em")


@admin.register(CadastroClienteIXCAuditoria)
class CadastroClienteIXCAuditoriaAdmin(IntegrationAuditExportAdminMixin, admin.ModelAdmin):
    integration_code = "cadastro_cliente_ixc"
    integration_audit_title = "Cadastro de Clientes IXC"
    integration_audit_eyebrow = "Automacao administrativa"
    integration_audit_subtitle = (
        "Consulte as importacoes e execucoes do cadastro em massa de clientes no IXC, "
        "com exportacao estruturada para analise por linha."
    )
    integration_audit_note = (
        "Use os botoes de exportacao para baixar os resultados ja abertos em colunas no CSV ou no Excel."
    )
    list_display = (
        "arquivo_nome",
        "action",
        "total_registros",
        "total_sucessos",
        "total_erros",
        "usuario",
        "criado_em",
        "exportacoes_disponiveis",
    )
    list_filter = ("action", "criado_em")
    search_fields = ("usuario__username", "arquivo_nome")
    fields = IntegrationAuditExportAdminMixin.integration_audit_fields
    readonly_fields = IntegrationAuditExportAdminMixin.integration_audit_fields
    inlines = [IntegrationAuditItemInline]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(integration=self.integration_code)


@admin.register(EdicaoLoginIXCAuditoria)
class EdicaoLoginIXCAuditoriaAdmin(IntegrationAuditExportAdminMixin, admin.ModelAdmin):
    integration_code = "edicao_login_ixc"
    integration_audit_title = "Edicao de Logins IXC"
    integration_audit_eyebrow = "Automacao administrativa"
    integration_audit_subtitle = (
        "Consulte as alteracoes em massa de logins no IXC, com rastreabilidade por arquivo, "
        "linha processada e campos alterados."
    )
    integration_audit_note = (
        "As exportacoes abrem os campos tratados em colunas separadas no CSV e no Excel."
    )
    list_display = (
        "arquivo_nome",
        "action",
        "total_registros",
        "total_sucessos",
        "total_erros",
        "usuario",
        "criado_em",
        "exportacoes_disponiveis",
    )
    list_filter = ("action", "criado_em")
    search_fields = ("usuario__username", "arquivo_nome")
    fields = IntegrationAuditExportAdminMixin.integration_audit_fields
    readonly_fields = IntegrationAuditExportAdminMixin.integration_audit_fields
    inlines = [IntegrationAuditItemInline]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(integration=self.integration_code)


@admin.register(EdicaoAtendimentoIXCAuditoria)
class EdicaoAtendimentoIXCAuditoriaAdmin(IntegrationAuditExportAdminMixin, admin.ModelAdmin):
    integration_code = "edicao_atendimento_ixc"
    integration_audit_title = "Edicao de Atendimentos IXC"
    integration_audit_eyebrow = "Automacao administrativa"
    integration_audit_subtitle = (
        "Consulte as alteracoes em massa de atendimentos no IXC, com rastreabilidade por arquivo, "
        "linha processada e campos alterados."
    )
    integration_audit_note = (
        "As exportacoes abrem os campos tratados em colunas separadas no CSV e no Excel."
    )
    list_display = (
        "arquivo_nome",
        "action",
        "total_registros",
        "total_sucessos",
        "total_erros",
        "usuario",
        "criado_em",
        "exportacoes_disponiveis",
    )
    list_filter = ("action", "criado_em")
    search_fields = ("usuario__username", "arquivo_nome")
    fields = IntegrationAuditExportAdminMixin.integration_audit_fields
    readonly_fields = IntegrationAuditExportAdminMixin.integration_audit_fields
    inlines = [IntegrationAuditItemInline]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(integration=self.integration_code)


@admin.register(DesativacaoAtendimentoIXCAuditoria)
class DesativacaoAtendimentoIXCAuditoriaAdmin(IntegrationAuditExportAdminMixin, admin.ModelAdmin):
    integration_code = "desativacao_atendimento_ixc"
    change_list_template = "admin/desativacao_atendimento_ixc_change_list.html"
    list_display = (
        "arquivo_nome",
        "total_registros",
        "total_sucessos",
        "total_erros",
        "usuario",
        "criado_em",
        "exportacoes_disponiveis",
    )
    search_fields = ("usuario__username", "arquivo_nome")
    fields = IntegrationAuditExportAdminMixin.integration_audit_fields
    readonly_fields = IntegrationAuditExportAdminMixin.integration_audit_fields
    inlines = [IntegrationAuditItemInline]

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).filter(integration=self.integration_code)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "baixar-modelo/",
                self.admin_site.admin_view(self.baixar_modelo_desativacao),
                name="auditoria_desativacaoatendimentoixcauditoria_baixar_modelo",
            ),
            path(
                "processar-planilha/",
                self.admin_site.admin_view(self.processar_planilha_desativacao),
                name="auditoria_desativacaoatendimentoixcauditoria_processar_planilha",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update(
            {
                "download_modelo_url": reverse(
                    "admin:auditoria_desativacaoatendimentoixcauditoria_baixar_modelo"
                ),
                "processar_planilha_url": reverse(
                    "admin:auditoria_desativacaoatendimentoixcauditoria_processar_planilha"
                ),
                "pode_processar_desativacao": self.has_change_permission(request),
            }
        )
        return super().changelist_view(request, extra_context=extra_context)

    def _serializar_linha_para_auditoria(self, dataframe, index):
        return {str(k).strip(): dataframe.at[index, k] for k in dataframe.columns}

    def _ler_dataframe_upload(self, arquivo):
        if arquivo.name.lower().endswith(".csv"):
            try:
                return pd.read_csv(arquivo, sep=None, engine="python", encoding="utf-8")
            except UnicodeDecodeError:
                arquivo.seek(0)
                return pd.read_csv(arquivo, sep=None, engine="python", encoding="latin1")

        try:
            return pd.read_excel(arquivo)
        except ValueError:
            arquivo.seek(0)
            try:
                return pd.read_csv(arquivo, sep=None, engine="python", encoding="utf-8")
            except UnicodeDecodeError:
                arquivo.seek(0)
                return pd.read_csv(arquivo, sep=None, engine="python", encoding="latin1")

    def baixar_modelo_desativacao(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied

        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df = pd.DataFrame(columns=["Atendimento_ID", "OS_ID", "Mensagem", "Confirmar_Desativacao"])
            df.to_excel(writer, index=False, sheet_name="Modelo_Desativacao_IXC")

            workbook = writer.book
            worksheet = writer.sheets["Modelo_Desativacao_IXC"]
            header_format = workbook.add_format({"bold": True, "bg_color": "#BFDBFE", "border": 1})
            integer_format = workbook.add_format({"num_format": "0"})

            worksheet.write(0, 0, "Atendimento_ID", header_format)
            worksheet.write(0, 1, "OS_ID", header_format)
            worksheet.write(0, 2, "Mensagem", header_format)
            worksheet.write(0, 3, "Confirmar_Desativacao", header_format)
            worksheet.set_column(0, 0, 20, integer_format)
            worksheet.set_column(1, 1, 16, integer_format)
            worksheet.set_column(2, 2, 90)
            worksheet.set_column(3, 3, 26)
            worksheet.data_validation(
                1,
                0,
                5000,
                0,
                {
                    "validate": "integer",
                    "criteria": ">=",
                    "value": 1,
                    "ignore_blank": False,
                    "input_title": "ID do atendimento",
                    "input_message": "Informe apenas o ID numerico do atendimento no IXC.",
                    "error_title": "Valor invalido",
                    "error_message": "Atendimento_ID aceita somente numeros inteiros.",
                },
            )
            worksheet.data_validation(
                1,
                1,
                5000,
                1,
                {
                    "validate": "integer",
                    "criteria": ">=",
                    "value": 1,
                    "ignore_blank": True,
                    "input_title": "ID da O.S.",
                    "input_message": "Opcional. Se ficar vazio, o sistema busca a O.S. vinculada ao atendimento.",
                    "error_title": "Valor invalido",
                    "error_message": "OS_ID aceita somente numeros inteiros.",
                },
            )
            worksheet.data_validation(
                1,
                3,
                5000,
                3,
                {
                    "validate": "list",
                    "source": ["SIM"],
                    "ignore_blank": False,
                    "input_title": "Confirmacao obrigatoria",
                    "input_message": "Digite SIM para autorizar a finalizacao do atendimento.",
                    "error_title": "Confirmacao obrigatoria",
                    "error_message": "Para finalizar, o campo Confirmar_Desativacao deve conter SIM.",
                },
            )

            instrucoes = pd.DataFrame(
                [
                    {
                        "Orientacao": "Esta automacao finaliza administrativamente o atendimento no IXC sem excluir o historico.",
                    },
                    {
                        "Orientacao": "Preencha Atendimento_ID com o ID numerico do atendimento no IXC.",
                    },
                    {
                        "Orientacao": "OS_ID e opcional. Use apenas quando quiser forcar uma O.S. especifica.",
                    },
                    {
                        "Orientacao": "Mensagem e opcional. Se ficar vazia, sera usada uma mensagem administrativa padrao.",
                    },
                    {
                        "Orientacao": "Preencha Confirmar_Desativacao com SIM em todas as linhas que deseja finalizar.",
                    },
                ]
            )
            instrucoes.to_excel(writer, index=False, sheet_name="Instrucoes")
            writer.sheets["Instrucoes"].set_column(0, 0, 110)

        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = "attachment; filename=Modelo_Desativacao_Atendimentos_IXC.xlsx"
        return response

    def processar_planilha_desativacao(self, request):
        if request.method != "POST":
            return HttpResponseRedirect("../")

        if not self.has_change_permission(request):
            raise PermissionDenied

        arquivo = request.FILES.get("arquivo_desativacao_atendimento")
        if not arquivo:
            messages.error(request, "Selecione uma planilha para processar a desativacao dos atendimentos.")
            return HttpResponseRedirect("../")

        try:
            df = self._ler_dataframe_upload(arquivo)
            itens_importados = dataframe_to_records(df)
            registrar_auditoria_integracao(
                integration=self.integration_code,
                action="importacao_planilha",
                usuario=request.user,
                arquivo_nome=arquivo.name,
                total_registros=len(itens_importados),
                detalhes={"colunas": list(df.columns)},
                itens=itens_importados,
            )

            df["Status_Importacao"] = ""
            df["Mensagem_Importacao"] = ""
            df["ID_IXC"] = ""

            sucessos = 0
            falhas = 0
            itens_execucao = []

            for index, linha in df.iterrows():
                if pd.notna(linha.get("Atendimento_ID")):
                    status, mensagem, atendimento_id = executar_desativacao_atendimento(
                        linha,
                        usuario_sistema=request.user,
                    )

                    if status:
                        sucessos += 1
                        df.at[index, "Status_Importacao"] = "SUCESSO"
                    else:
                        falhas += 1
                        df.at[index, "Status_Importacao"] = "ERRO"

                    df.at[index, "Mensagem_Importacao"] = mensagem
                    df.at[index, "ID_IXC"] = atendimento_id or ""
                    itens_execucao.append(
                        {
                            "linha_numero": index + 2,
                            "status": "sucesso" if status else "erro",
                            "mensagem": mensagem,
                            "dados_json": self._serializar_linha_para_auditoria(df, index),
                        }
                    )

            registrar_auditoria_integracao(
                integration=self.integration_code,
                action="execucao_integracao",
                usuario=request.user,
                arquivo_nome=arquivo.name,
                total_registros=sucessos + falhas,
                total_sucessos=sucessos,
                total_erros=falhas,
                detalhes={"colunas": list(df.columns)},
                itens=itens_execucao,
            )

            output = BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="Resultado_Desativacao_IXC")
                worksheet = writer.sheets["Resultado_Desativacao_IXC"]
                for col_num, _ in enumerate(df.columns.values):
                    worksheet.set_column(col_num, col_num, 24)

            output.seek(0)
            response = HttpResponse(
                output.read(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = "attachment; filename=Relatorio_Desativacao_Atendimentos_IXC.xlsx"
            return response
        except Exception as exc:
            messages.error(request, f"Falha ao processar a desativacao dos atendimentos: {exc}")
            return HttpResponseRedirect("../")


@admin.register(LogAlteracaoIXCAuditoria)
class LogAlteracaoIXCAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("id", "cliente", "login_ixc", "campo_alterado", "data_registro")
    list_filter = ("campo_alterado", "data_registro")
    search_fields = ("cliente__razao_social", "cliente__nome_fantasia", "login_ixc", "campo_alterado", "valor_antigo", "valor_novo")
    autocomplete_fields = ("cliente",)
    ordering = ("-data_registro",)


@admin.register(HistoricoSincronizacaoAuditoria)
class HistoricoSincronizacaoAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("id", "data_inicio", "tipo", "origem", "executado_por", "status", "registros_processados", "tempo_execucao")
    list_filter = ("status", "tipo", "origem")
    readonly_fields = ("data_inicio", "data_fim", "status", "origem", "executado_por", "registros_processados", "detalhes")
    change_list_template = "admin/historico_botoes.html"
    change_form_template = "admin/historico_sincronizacao_change_form.html"
    actions = ["parar_sincronizacao"]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("rodar-carga-total/", self.admin_site.admin_view(self.btn_rodar_carga_total), name="rodar-carga-total"),
            path("rodar-incremental/", self.admin_site.admin_view(self.btn_rodar_incremental), name="rodar-incremental"),
            path("rodar-faxina/", self.admin_site.admin_view(self.btn_rodar_faxina), name="rodar-faxina"),
            path("rodar-os-comercial-lastmile/", self.admin_site.admin_view(self.btn_rodar_os_comercial_lastmile), name="rodar-os-comercial-lastmile"),
            path("parar-os-comercial-lastmile/", self.admin_site.admin_view(self.btn_parar_os_comercial_lastmile), name="parar-os-comercial-lastmile"),
            path("rodar-respostas-email-cotacao/", self.admin_site.admin_view(self.btn_rodar_respostas_email_cotacao), name="rodar-respostas-email-cotacao"),
            path("rodar-backup/", self.admin_site.admin_view(self.btn_rodar_backup), name="rodar-backup"),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        rotina_os_lastmile_ativa = buscar_rotina_em_execucao("os_comercial_lastmile")
        extra_context.update({
            "rotina_os_lastmile_ativa": rotina_os_lastmile_ativa,
            "rotina_os_lastmile_descricao": (
                descrever_rotina_em_execucao("os_comercial_lastmile", rotina_os_lastmile_ativa)
                if rotina_os_lastmile_ativa else ""
            ),
        })
        return super().changelist_view(request, extra_context=extra_context)

    def btn_rodar_carga_total(self, request):
        rotina_ativa = buscar_rotina_em_execucao("total")
        if rotina_ativa:
            self.message_user(request, descrever_rotina_em_execucao("total", rotina_ativa), messages.WARNING)
            return HttpResponseRedirect("../")
        subprocess.Popen(["python", "scripts/integracoes/ixc_api.py", "manual", request.user.username])
        self.message_user(request, "Carga total iniciada em segundo plano.", messages.SUCCESS)
        return HttpResponseRedirect("../")

    def btn_rodar_incremental(self, request):
        rotina_ativa = buscar_rotina_em_execucao("incremental")
        if rotina_ativa:
            self.message_user(request, descrever_rotina_em_execucao("incremental", rotina_ativa), messages.WARNING)
            return HttpResponseRedirect("../")
        subprocess.Popen(["python", "scripts/integracoes/ixc_api_incremental.py", "manual", request.user.username])
        self.message_user(request, "Sincronizacao incremental iniciada.", messages.SUCCESS)
        return HttpResponseRedirect("../")

    def btn_rodar_faxina(self, request):
        rotina_ativa = buscar_rotina_em_execucao("faxina")
        if rotina_ativa:
            self.message_user(request, descrever_rotina_em_execucao("faxina", rotina_ativa), messages.WARNING)
            return HttpResponseRedirect("../")
        subprocess.Popen(["python", "scripts/integracoes/ixc_faxina.py", "manual", request.user.username])
        self.message_user(request, "Rotina de faxina iniciada.", messages.SUCCESS)
        return HttpResponseRedirect("../")

    def btn_rodar_os_comercial_lastmile(self, request):
        rotina_ativa = buscar_rotina_em_execucao("os_comercial_lastmile")
        if rotina_ativa:
            self.message_user(
                request,
                descrever_rotina_em_execucao("os_comercial_lastmile", rotina_ativa),
                messages.WARNING,
            )
            return HttpResponseRedirect("../?" + urlencode({"tipo__exact": "os_comercial_lastmile"}))

        comando = ["python", "scripts/integracoes/ixc_os_comercial_lastmile.py", "manual", request.user.username]

        cliente_local_id = (request.GET.get("cliente_local_id") or "").strip()
        cliente_ixc_id = (request.GET.get("cliente_ixc_id") or "").strip()
        os_alterada_desde = (request.GET.get("os_alterada_desde") or "").strip()
        os_alterada_nos_ultimos_dias = (request.GET.get("os_alterada_nos_ultimos_dias") or "").strip()

        if cliente_local_id:
            comando.append(f"--cliente-local-id={cliente_local_id}")
        if cliente_ixc_id:
            comando.append(f"--cliente-ixc-id={cliente_ixc_id}")
        if os_alterada_desde:
            comando.append(f"--os-alterada-desde={os_alterada_desde}")
        if os_alterada_nos_ultimos_dias:
            comando.append(f"--os-alterada-nos-ultimos-dias={os_alterada_nos_ultimos_dias}")

        subprocess.Popen(comando)

        detalhes = []
        if cliente_local_id:
            detalhes.append(f"cliente local {cliente_local_id}")
        if cliente_ixc_id:
            detalhes.append(f"cliente IXC {cliente_ixc_id}")
        if os_alterada_desde:
            detalhes.append(f"O.S. alterada desde {os_alterada_desde}")
        if os_alterada_nos_ultimos_dias:
            detalhes.append(f"O.S. alterada nos ultimos {os_alterada_nos_ultimos_dias} dias")

        mensagem = "Rotina de OS Comercial | Lastmile iniciada."
        if detalhes:
            mensagem += " Filtros: " + ", ".join(detalhes) + "."

        self.message_user(request, mensagem, messages.SUCCESS)
        return HttpResponseRedirect("../?" + urlencode({"tipo__exact": "os_comercial_lastmile"}))

    def btn_parar_os_comercial_lastmile(self, request):
        rotina_ativa = buscar_rotina_em_execucao("os_comercial_lastmile")
        if not rotina_ativa:
            self.message_user(
                request,
                "Nenhuma rotina de OS Comercial | Lastmile em execucao foi encontrada.",
                messages.WARNING,
            )
            return HttpResponseRedirect("../?" + urlencode({"tipo__exact": "os_comercial_lastmile"}))

        rotina_ativa.detalhes = "STOP"
        rotina_ativa.save(update_fields=["detalhes"])
        self.message_user(
            request,
            f"Sinal de parada enviado para a rotina de OS Comercial | Lastmile #{rotina_ativa.id}.",
            messages.WARNING,
        )
        return HttpResponseRedirect("../?" + urlencode({"tipo__exact": "os_comercial_lastmile"}))

    def btn_rodar_backup(self, request):
        rotina_ativa = buscar_rotina_em_execucao("backup")
        if rotina_ativa:
            self.message_user(request, descrever_rotina_em_execucao("backup", rotina_ativa), messages.WARNING)
            return HttpResponseRedirect("../?" + urlencode({"tipo__exact": "backup"}))
        subprocess.Popen(["python", "scripts/integracoes/backup_manual.py", "manual", request.user.username])
        self.message_user(request, "Backup manual iniciado em segundo plano.", messages.SUCCESS)
        return HttpResponseRedirect("../?" + urlencode({"tipo__exact": "backup"}))

    def btn_rodar_respostas_email_cotacao(self, request):
        rotina_ativa = buscar_rotina_em_execucao("email_respostas_cotacao")
        if rotina_ativa:
            self.message_user(
                request,
                descrever_rotina_em_execucao("email_respostas_cotacao", rotina_ativa),
                messages.WARNING,
            )
            return HttpResponseRedirect("../?" + urlencode({"tipo__exact": "email_respostas_cotacao"}))

        subprocess.Popen([
            "python",
            "scripts/integracoes/sincronizar_respostas_email_cotacao.py",
            "manual",
            request.user.username,
        ])
        self.message_user(request, "Sincronizacao manual das respostas de e-mail iniciada.", messages.SUCCESS)
        return HttpResponseRedirect("../?" + urlencode({"tipo__exact": "email_respostas_cotacao"}))

    @admin.action(description="PARAR processos selecionados")
    def parar_sincronizacao(self, request, queryset):
        vivos = queryset.filter(status="rodando")
        if vivos.exists():
            vivos.update(detalhes="STOP")
            self.message_user(request, f"Sinal de parada enviado para {vivos.count()} processo(s).", messages.WARNING)
        else:
            self.message_user(request, "Nenhum processo em execucao foi selecionado.", messages.ERROR)

    def tempo_execucao(self, obj):
        if obj.data_fim:
            diff = obj.data_fim - obj.data_inicio
            return f"{diff.seconds} segundos"
        return "Em execucao..."
