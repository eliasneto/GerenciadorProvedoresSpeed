from django.contrib import admin

from .models import (
    Campo, Escola, MapaCalor, Processo, RedeExterna, RedeInterna, Setor, SetorEscopo, SetorStatus,
    TargetRedeExterna,
)


class RedeExternaInline(admin.StackedInline):
    model = RedeExterna
    extra = 0
    fields = ('setor', 'status', 'parceiro', 'dados_adicionais')


class RedeInternaInline(admin.StackedInline):
    model = RedeInterna
    extra = 0
    fields = ('setor', 'status', 'parceiro', 'dados_adicionais')


class MapaCalorInline(admin.StackedInline):
    model = MapaCalor
    extra = 0
    fields = ('setor', 'status', 'parceiro', 'dados_adicionais')


@admin.register(Escola)
class EscolaAdmin(admin.ModelAdmin):
    list_display = (
        'jira_key', 'inep', 'nome', 'uf', 'municipio', 'status_escola',
        'velocidade_dl_minima', 'kit_inicial', 'atualizado_em',
    )
    list_filter = ('uf', 'status_escola')
    search_fields = ('jira_key', 'inep', 'nome', 'municipio')
    ordering = ('jira_key',)
    inlines = [RedeExternaInline, RedeInternaInline, MapaCalorInline]
    # RN-057 Parte 3/ADR-029: TARGET EACE nunca e armazenado — so no
    # formulario de detalhe (1 lookup por pagina), nunca no list_display
    # (evitaria N+1: 1 consulta extra por linha da listagem).
    readonly_fields = ('target_eace_display',)

    @admin.display(description="TARGET EACE")
    def target_eace_display(self, obj):
        return obj.target_eace if obj.pk else "—"


@admin.register(RedeExterna)
class RedeExternaAdmin(admin.ModelAdmin):
    list_display = ('id', 'escola', 'processo', 'setor', 'status', 'parceiro', 'atualizado_em')
    list_filter = ('processo', 'setor', 'status')
    search_fields = ('escola__jira_key', 'escola__inep', 'escola__nome', 'setor__nome', 'status__nome')
    autocomplete_fields = ('escola', 'parceiro', 'processo', 'setor', 'status')
    ordering = ('escola__jira_key',)


@admin.register(RedeInterna)
class RedeInternaAdmin(admin.ModelAdmin):
    list_display = ('id', 'escola', 'processo', 'setor', 'status', 'parceiro', 'atualizado_em')
    list_filter = ('processo', 'setor', 'status')
    search_fields = ('escola__jira_key', 'escola__inep', 'escola__nome', 'setor__nome', 'status__nome')
    autocomplete_fields = ('escola', 'parceiro', 'processo', 'setor', 'status')
    ordering = ('escola__jira_key',)


@admin.register(MapaCalor)
class MapaCalorAdmin(admin.ModelAdmin):
    list_display = ('id', 'escola', 'processo', 'setor', 'status', 'parceiro', 'atualizado_em')
    list_filter = ('processo', 'setor', 'status')
    search_fields = ('escola__jira_key', 'escola__inep', 'escola__nome', 'setor__nome', 'status__nome')
    autocomplete_fields = ('escola', 'parceiro', 'processo', 'setor', 'status')
    ordering = ('escola__jira_key',)


class SetorInline(admin.TabularInline):
    model = Setor
    extra = 0
    fields = ('nome',)


@admin.register(Processo)
class ProcessoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'criado_em')
    search_fields = ('nome',)
    ordering = ('nome',)
    inlines = [SetorInline]


class SetorStatusInline(admin.TabularInline):
    model = SetorStatus
    extra = 0
    fields = ('nome',)


@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'processo', 'criado_em')
    list_filter = ('processo',)
    search_fields = ('nome', 'processo__nome')
    autocomplete_fields = ('processo',)
    ordering = ('processo__nome', 'nome')
    inlines = [SetorStatusInline]


@admin.register(SetorStatus)
class SetorStatusAdmin(admin.ModelAdmin):
    list_display = ('nome', 'setor', 'criado_em')
    list_filter = ('setor__processo',)
    search_fields = ('nome', 'setor__nome', 'setor__processo__nome')
    autocomplete_fields = ('setor',)
    ordering = ('setor__processo__nome', 'setor__nome', 'nome')


@admin.register(Campo)
class CampoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'setor_nome', 'criado_em')
    list_filter = ('tipo', 'setor_nome')
    search_fields = ('nome', 'setor_nome')
    ordering = ('setor_nome', 'nome')


@admin.register(TargetRedeExterna)
class TargetRedeExternaAdmin(admin.ModelAdmin):
    """RN-057 Parte 3/ADR-029: catalogo de referencia (UF + Velocidade ->
    Valor), sem vinculo direto com Escola. Cadastro manual complementar ao
    management command `importar_target_rede_externa`."""

    list_display = ('uf', 'velocidade_mbps', 'valor', 'atualizado_em')
    list_filter = ('uf',)
    search_fields = ('uf',)
    ordering = ('uf', 'velocidade_mbps')


@admin.register(SetorEscopo)
class SetorEscopoAdmin(admin.ModelAdmin):
    list_display = ('setor_nome', 'atividade', 'aplica_re', 'aplica_ri', 'aplica_mapa_calor', 'atualizado_em')
    list_filter = ('atividade',)
    search_fields = ('setor_nome',)
    ordering = ('setor_nome',)
