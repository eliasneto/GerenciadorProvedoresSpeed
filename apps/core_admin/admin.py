import os

import MySQLdb
from django.apps import apps
from django.conf import settings
from django.contrib import admin, messages
from django.utils import timezone

from .models import AcessoBancoDados, TabelaAcessoBanco


def sincronizar_tabelas_do_sistema():
    tabelas_sincronizadas = 0

    for model in apps.get_models():
        meta = model._meta

        if not meta.managed or meta.proxy or meta.auto_created:
            continue

        nome_tabela = meta.db_table
        descricao = f"{meta.verbose_name_plural} | app: {meta.app_label} | model: {meta.model_name}"

        _, created = TabelaAcessoBanco.objects.update_or_create(
            nome_tabela=nome_tabela,
            defaults={'descricao': descricao},
        )
        if created:
            tabelas_sincronizadas += 1

    return tabelas_sincronizadas


@admin.register(TabelaAcessoBanco)
class TabelaAcessoBancoAdmin(admin.ModelAdmin):
    list_display = ('nome_tabela', 'status', 'descricao')
    list_filter = ('status',)
    search_fields = ('nome_tabela', 'descricao')
    actions = ('sincronizar_tabelas',)

    def changelist_view(self, request, extra_context=None):
        sincronizar_tabelas_do_sistema()
        return super().changelist_view(request, extra_context=extra_context)

    @admin.action(description='Sincronizar tabelas do sistema')
    def sincronizar_tabelas(self, request, queryset):
        total_novas = sincronizar_tabelas_do_sistema()
        self.message_user(
            request,
            f'Sincronização concluída. {total_novas} nova(s) tabela(s) adicionada(s).',
            level=messages.SUCCESS,
        )


@admin.register(AcessoBancoDados)
class AcessoBancoDadosAdmin(admin.ModelAdmin):
    list_display = ('nome', 'usuario_banco', 'host_acesso', 'status', 'ultimo_aplicado_em')
    list_filter = ('status',)
    search_fields = ('nome', 'usuario_banco', 'host_acesso')
    filter_horizontal = ('tabelas_permitidas',)
    readonly_fields = ('ultimo_aplicado_em', 'ultimo_erro')
    actions = ('aplicar_acessos_no_banco',)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == 'tabelas_permitidas':
            sincronizar_tabelas_do_sistema()
            kwargs['queryset'] = TabelaAcessoBanco.objects.filter(status='ativo').order_by('nome_tabela')
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    @admin.action(description='Aplicar acessos selecionados no banco')
    def aplicar_acessos_no_banco(self, request, queryset):
        sucesso = 0
        falha = 0

        for acesso in queryset:
            try:
                self._aplicar_acesso(acesso)
                sucesso += 1
            except Exception as exc:
                acesso.ultimo_erro = str(exc)
                acesso.save(update_fields=['ultimo_erro'])
                falha += 1
                self.message_user(
                    request,
                    f'Erro ao aplicar {acesso.usuario_banco}: {exc}',
                    level=messages.ERROR,
                )

        if sucesso:
            self.message_user(request, f'{sucesso} acesso(s) aplicado(s) com sucesso.', level=messages.SUCCESS)
        if falha:
            self.message_user(request, f'{falha} acesso(s) falharam na aplicação.', level=messages.WARNING)

    def _aplicar_acesso(self, acesso):
        db_conf = settings.DATABASES['default']
        host = db_conf.get('HOST') or 'localhost'
        port = int(db_conf.get('PORT') or 3306)
        database = db_conf.get('NAME')

        admin_user = os.getenv('DB_ADMIN_USER', 'root')
        admin_password = os.getenv('DB_ADMIN_PASSWORD', os.getenv('MYSQL_ROOT_PASSWORD', 'SpeedRoot!2026#Prod'))

        conn = MySQLdb.connect(
            host=host,
            user=admin_user,
            passwd=admin_password,
            port=port,
            charset='utf8mb4',
        )

        try:
            with conn.cursor() as cursor:
                usuario = acesso.usuario_banco.replace("`", "").replace("'", "")
                host_acesso = acesso.host_acesso.replace("`", "").replace("'", "")

                cursor.execute(
                    f"CREATE USER IF NOT EXISTS '{usuario}'@'{host_acesso}' IDENTIFIED BY %s",
                    [acesso.senha_banco],
                )
                cursor.execute(
                    f"ALTER USER '{usuario}'@'{host_acesso}' IDENTIFIED BY %s",
                    [acesso.senha_banco],
                )
                cursor.execute(f"REVOKE ALL PRIVILEGES, GRANT OPTION FROM '{usuario}'@'{host_acesso}'")

                if acesso.status == 'ativo':
                    tabelas = list(acesso.tabelas_permitidas.filter(status='ativo').values_list('nome_tabela', flat=True))
                    for tabela in tabelas:
                        tabela_limpa = tabela.replace('`', '')
                        cursor.execute(
                            f"GRANT SELECT ON `{database}`.`{tabela_limpa}` TO '{usuario}'@'{host_acesso}'"
                        )

                cursor.execute("FLUSH PRIVILEGES")

            conn.commit()
        finally:
            conn.close()

        acesso.ultimo_aplicado_em = timezone.now()
        acesso.ultimo_erro = ''
        acesso.save(update_fields=['ultimo_aplicado_em', 'ultimo_erro'])
