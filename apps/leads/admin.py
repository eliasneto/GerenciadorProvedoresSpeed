from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from .models import Lead, LeadEmpresa, LeadEndereco


def _normalizar_merge(valor):
    return str(valor or "").strip().lower()


def _assinatura_endereco(endereco):
    return (
        _normalizar_merge(endereco.endereco),
        _normalizar_merge(endereco.numero),
        _normalizar_merge(endereco.bairro),
        _normalizar_merge(endereco.cidade),
        _normalizar_merge(endereco.estado),
        _normalizar_merge(endereco.cep),
    )


def _campos_empresa_merge():
    return [
        "razao_social",
        "cnpj_cpf",
        "nome_fantasia",
        "site",
        "contato_nome",
        "email",
        "telefone",
        "fonte",
        "confianca",
        "instagram_username",
        "instagram_url",
        "bio_instagram",
        "observacao_ia",
        "status",
    ]


def _buscar_candidatas_duplicadas(empresa):
    filtros = None
    cnpj_cpf = _normalizar_merge(empresa.cnpj_cpf)
    razao_social = _normalizar_merge(empresa.razao_social)

    if cnpj_cpf:
        filtros = {"cnpj_cpf__iexact": empresa.cnpj_cpf}
    elif razao_social:
        filtros = {"razao_social__iexact": empresa.razao_social}
    else:
        return LeadEmpresa.objects.none()

    return LeadEmpresa.objects.filter(**filtros).exclude(pk=empresa.pk).order_by("id")


def _consolidar_empresa_raiz(empresa_raiz):
    assinaturas_raiz = {
        _assinatura_endereco(endereco): endereco
        for endereco in empresa_raiz.enderecos.all().order_by("id")
    }
    candidatas = []

    for candidata in _buscar_candidatas_duplicadas(empresa_raiz):
        assinaturas_candidata = {
            _assinatura_endereco(endereco)
            for endereco in candidata.enderecos.all().order_by("id")
        }
        if assinaturas_raiz.intersection(assinaturas_candidata):
            candidatas.append(candidata)

    if not candidatas:
        return {
            "empresas_removidas": 0,
            "enderecos_movidos": 0,
            "enderecos_fundidos": 0,
            "leads_reapontados": 0,
        }

    empresas_grupo = sorted([empresa_raiz, *candidatas], key=lambda item: item.id)
    canonica = empresas_grupo[0]
    duplicadas = empresas_grupo[1:]

    enderecos_movidos = 0
    enderecos_fundidos = 0
    leads_reapontados = 0

    for duplicada in duplicadas:
        campos_update = []
        for campo in _campos_empresa_merge():
            valor_canonico = getattr(canonica, campo)
            valor_duplicada = getattr(duplicada, campo)
            if (valor_canonico in [None, ""] or campo == "status" and valor_canonico == "novo") and valor_duplicada not in [None, ""]:
                setattr(canonica, campo, valor_duplicada)
                campos_update.append(campo)

        if campos_update:
            canonica.save(update_fields=sorted(set(campos_update)))

        for endereco in duplicada.enderecos.all().order_by("id"):
            assinatura = _assinatura_endereco(endereco)
            endereco_canonico = assinaturas_raiz.get(assinatura)

            if endereco_canonico:
                qtd_proposals = endereco.proposals.update(lead_endereco=endereco_canonico)
                qtd = endereco.leads_legados.update(
                    empresa_estruturada=canonica,
                    endereco_estruturado=endereco_canonico,
                )
                leads_reapontados += qtd + qtd_proposals
                endereco.delete()
                enderecos_fundidos += 1
            else:
                endereco.empresa = canonica
                endereco.save(update_fields=["empresa"])
                assinaturas_raiz[assinatura] = endereco
                enderecos_movidos += 1

        leads_reapontados += duplicada.leads_legados.update(empresa_estruturada=canonica)
        duplicada.delete()

    return {
        "empresas_removidas": len(duplicadas),
        "enderecos_movidos": enderecos_movidos,
        "enderecos_fundidos": enderecos_fundidos,
        "leads_reapontados": leads_reapontados,
    }


class LeadEnderecoInline(admin.TabularInline):
    model = LeadEndereco
    extra = 0
    fields = ('cep', 'endereco', 'numero', 'bairro', 'cidade', 'estado')


@admin.register(LeadEmpresa)
class LeadEmpresaAdmin(admin.ModelAdmin):
    change_list_template = "admin/leads/leadempresa/change_list.html"
    list_display = ('nome_fantasia', 'razao_social', 'cnpj_cpf', 'cidade_principal', 'status', 'data_criacao')
    list_filter = ('status', 'confianca', 'fonte')
    search_fields = ('nome_fantasia', 'razao_social', 'cnpj_cpf', 'email', 'telefone')
    inlines = [LeadEnderecoInline]
    actions = ["consolidar_empresas_duplicadas"]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "consolidar-duplicadas/",
                self.admin_site.admin_view(self.consolidar_duplicadas_view),
                name="leads_leadempresa_consolidar_duplicadas",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["consolidar_duplicadas_url"] = reverse(
            "admin:leads_leadempresa_consolidar_duplicadas"
        )
        return super().changelist_view(request, extra_context=extra_context)

    def cidade_principal(self, obj):
        primeiro_endereco = obj.enderecos.order_by('id').first()
        return (primeiro_endereco.cidade if primeiro_endereco else '') or '-'

    cidade_principal.short_description = 'Cidade Principal'

    def _executar_consolidacao_queryset(self, request, queryset):
        empresas_removidas = 0
        enderecos_movidos = 0
        enderecos_fundidos = 0
        leads_reapontados = 0
        ids_ignorados = set()

        with transaction.atomic():
            for empresa in queryset.order_by("id"):
                if empresa.pk in ids_ignorados:
                    continue

                resultado = _consolidar_empresa_raiz(empresa)
                empresas_removidas += resultado["empresas_removidas"]
                enderecos_movidos += resultado["enderecos_movidos"]
                enderecos_fundidos += resultado["enderecos_fundidos"]
                leads_reapontados += resultado["leads_reapontados"]

                for candidata in _buscar_candidatas_duplicadas(empresa):
                    ids_ignorados.add(candidata.pk)

        if empresas_removidas == 0:
            self.message_user(
                request,
                "Nenhuma empresa duplicada foi encontrada dentro da selecao.",
                level=messages.INFO,
            )
            return

        self.message_user(
            request,
            (
                f"Consolidacao concluida: {empresas_removidas} empresa(s) duplicada(s) removida(s), "
                f"{enderecos_movidos} endereco(s) movido(s), {enderecos_fundidos} endereco(s) fundido(s) "
                f"e {leads_reapontados} lead(s) reapontado(s)."
            ),
            level=messages.SUCCESS,
        )

    def consolidar_duplicadas_view(self, request):
        termo = (request.GET.get("q") or request.POST.get("q") or "").strip()
        empresas = LeadEmpresa.objects.none()

        if termo:
            empresas = (
                LeadEmpresa.objects.annotate(total_enderecos=Count("enderecos", distinct=True))
                .filter(
                    Q(nome_fantasia__icontains=termo)
                    | Q(razao_social__icontains=termo)
                    | Q(cnpj_cpf__icontains=termo)
                )
                .order_by("nome_fantasia", "razao_social", "id")
            )

        if request.method == "POST" and request.POST.get("action") == "consolidar":
            ids = request.POST.getlist("empresa_ids")
            queryset = LeadEmpresa.objects.filter(pk__in=ids)
            if not queryset.exists():
                self.message_user(
                    request,
                    "Selecione ao menos uma empresa para consolidar.",
                    level=messages.WARNING,
                )
            else:
                self._executar_consolidacao_queryset(request, queryset)
                redirect_url = f"{reverse('admin:leads_leadempresa_consolidar_duplicadas')}?q={termo}"
                return HttpResponseRedirect(redirect_url)

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Consolidar empresas duplicadas",
            "subtitle": "Busca manual por nome ou documento",
            "empresas": empresas,
            "termo": termo,
            "total_resultados": empresas.count() if termo else 0,
            "has_view_permission": self.has_view_permission(request),
            "changelist_url": reverse("admin:leads_leadempresa_changelist"),
        }
        return TemplateResponse(
            request,
            "admin/leads/leadempresa/consolidar_duplicadas.html",
            context,
        )

    @admin.action(description="Consolidar duplicadas (mesmo documento/nome + mesmo endereco)")
    def consolidar_empresas_duplicadas(self, request, queryset):
        self._executar_consolidacao_queryset(request, queryset)


@admin.register(LeadEndereco)
class LeadEnderecoAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'endereco', 'numero', 'bairro', 'cidade', 'estado')
    list_filter = ('estado', 'cidade')
    search_fields = ('empresa__nome_fantasia', 'empresa__razao_social', 'empresa__cnpj_cpf', 'endereco', 'bairro', 'cidade', 'cep')


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('nome_fantasia', 'cidade', 'estado', 'status', 'confianca', 'data_criacao')
    list_filter = ('status', 'estado', 'confianca', 'fonte')
    search_fields = ('nome_fantasia', 'razao_social', 'cnpj_cpf', 'cidade', 'bairro', 'cep')

    fieldsets = (
        ('Identificacao do Parceiro', {
            'fields': ('razao_social', 'nome_fantasia', 'cnpj_cpf', 'site', 'status')
        }),
        ('Localizacao', {
            'fields': ('cep', 'endereco', 'numero', 'bairro', 'cidade', 'estado')
        }),
        ('Contato', {
            'fields': ('contato_nome', 'email', 'telefone')
        }),
        ('Estrutura Nova', {
            'fields': ('empresa_estruturada', 'endereco_estruturado'),
            'classes': ('collapse',)
        }),
        ('Inteligencia Artificial & Captacao', {
            'fields': ('fonte', 'confianca', 'instagram_username', 'instagram_url', 'bio_instagram', 'observacao_ia'),
            'classes': ('collapse',)
        }),
    )
