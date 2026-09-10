from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.http import Http404, HttpResponse, JsonResponse

import pandas as pd

from .models import Lead, LeadEmpresa, LeadEndereco
from .forms import LeadForm, LeadEnderecoForm, LeadEmpresaForm
from apps.partners.forms import ProposalForm
from apps.partners.models import Partner
from apps.clientes.models import Cliente, Endereco
from apps.escolas.models import CotacaoParceiro, Escola, MapaCalor, Processo, RedeExterna, RedeInterna, Setor, SetorStatus

from apps.core.integration_audit import registrar_auditoria_integracao
from apps.core.models import RegistroHistorico

from . import services


# 1. Cria a regra de verificação
def grupo_LastMile_required(user):
    if not user.is_authenticated:
        return False
    # O Superuser (você) sempre passa. Os outros precisam estar no grupo.
    if user.groups.filter(name='LastMile').exists() or user.is_superuser:
        return True
    # Se não for do grupo, joga um Erro 403 (Acesso Negado)
    raise PermissionDenied


def grupo_Setor_required(user):
    """RN-054/ADR-028: grupo Django `Setor` — controla so a visibilidade do
    modulo "Setores" (menu + `setores_list`/`setor_detail`). Nao confundir
    com o model `apps.escolas.models.Setor` (catalogo, RN-025) nem com o
    nome do modulo/menu "Setores" — sao tres coisas diferentes com o mesmo
    nome. Independente do grupo `LastMile`. A restricao adicional por nome
    de Setor individual (RN-055) e verificada dentro das views, nao aqui."""
    if not user.is_authenticated:
        return False
    if user.groups.filter(name='Setor').exists() or user.is_superuser:
        return True
    raise PermissionDenied


# Pagina inicial ('/') do sistema. Vive aqui (nao em apps.core) porque o unico
# dado que ela exibe hoje e a contagem de leads, dona deste app.
@login_required
def home(request):
    context = {
        'total_leads': Lead.objects.count(),
    }
    return render(request, 'core/home.html', context)


def _get_request_param_or_default(request, name, default=''):
    if name in request.GET:
        return (request.GET.get(name) or '').strip()
    return (default or '').strip()


@user_passes_test(grupo_LastMile_required)
@login_required
def lead_list(request):
    """Lista todos os leads com paginação e filtros"""
    busca_empresa = request.GET.get('empresa', '')
    busca_cidade = request.GET.get('cidade', '')
    busca_estado = request.GET.get('estado', '')
    busca_bairro = request.GET.get('bairro', '')
    busca_cep = request.GET.get('cep', '')

    leads_list = services.filtrar_leads(
        busca_empresa=busca_empresa,
        busca_cidade=busca_cidade,
        busca_estado=busca_estado,
        busca_bairro=busca_bairro,
        busca_cep=busca_cep,
    )

    paginator = Paginator(leads_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    services.anexar_parceiro_relacionado_leads(page_obj.object_list)

    context = {
        'page_obj': page_obj,
        'busca_empresa': busca_empresa,
        'busca_cidade': busca_cidade,
        'busca_estado': busca_estado,
        'busca_bairro': busca_bairro,
        'busca_cep': busca_cep,
    }

    return render(request, 'leads/lead_list.html', context)

@user_passes_test(grupo_LastMile_required)
@login_required
def lead_create(request):
    """Criação de novos leads de cotação"""
    if request.method == 'POST':
        form = LeadForm(request.POST)
        if form.is_valid():
            lead = form.save()
            empresa, _ = services.sync_lead_to_structured_models(lead)
            messages.success(request, "Provedor cadastrado! Agora adicione o primeiro endereço.")
            return redirect('lead_empresa_endereco_create', pk=empresa.pk)
    else:
        form = LeadForm()
    return render(request, 'leads/lead_form.html', {'form': form})

@user_passes_test(grupo_LastMile_required)
@login_required
def lead_update(request, pk):
    """Edição de dados básicos do lead e Visualização do Histórico"""
    lead = get_object_or_404(Lead, pk=pk)

    # --- MÁGICA SPEED: Busca todo o histórico vinculado a este Lead ---
    lead_type = ContentType.objects.get_for_model(Lead)
    historico = RegistroHistorico.objects.filter(content_type=lead_type, object_id=lead.id)

    if request.method == 'POST':
        form = LeadForm(request.POST, instance=lead)
        if form.is_valid():
            lead = form.save()
            services.sync_lead_to_structured_models(lead)
            messages.success(request, "Dados da prospecção atualizados!")
            return redirect('lead_list')
    else:
        form = LeadForm(instance=lead)

    return render(request, 'leads/lead_form.html', {
        'form': form,
        'lead': lead, # Injetamos o lead para a tela saber o ID
        'historico': historico, # Injetamos a lista de eventos
        'title': 'Editar Prospecção'
    })

@user_passes_test(grupo_LastMile_required)
@login_required
def lead_add_historico(request, pk):
    """Mini-view que recebe o POST do comentário/anexo e salva no banco"""
    lead = get_object_or_404(Lead, pk=pk)

    if request.method == 'POST':
        descricao_texto = request.POST.get('descricao')
        arquivo = request.FILES.get('arquivo')

        if services.adicionar_historico_lead(lead, descricao_texto, arquivo, request.user):
            messages.success(request, "Registro adicionado à linha do tempo da prospecção!")

    return redirect('lead_update', pk=pk)

@user_passes_test(grupo_LastMile_required)
@login_required
def lead_delete(request, pk):
    """Remoção de lead da base"""
    lead = get_object_or_404(Lead, pk=pk)
    if request.method == 'POST':
        lead.delete()
        messages.warning(request, "Prospecção removida da base de provedores.")
        return redirect('lead_list')
    return redirect('lead_list')

@user_passes_test(grupo_LastMile_required)
@login_required
def update_lead_status(request, pk):
    """Valida a intenção e redireciona para a conversão ou atualiza o status."""
    if request.method == 'POST':
        lead = get_object_or_404(Lead, pk=pk)
        novo_status = request.POST.get('status')

        if novo_status == 'andamento':
            # Evita duplicidade somente quando houver documento informado
            if services.lead_possui_parceiro_com_mesmo_documento(lead):
                messages.error(request, f"O CNPJ {lead.cnpj_cpf} já é um parceiro ativo.")
                return redirect('lead_list')

            # REDIRECIONA PARA A TELA DE CONVERSÃO
            return redirect('lead_convert', pk=lead.pk)

        elif novo_status == 'inviavel':
            observacao = request.POST.get('observacao')
            arquivo = request.FILES.get('arquivo')

            services.marcar_lead_inviavel(lead, observacao, arquivo, request.user)

            messages.warning(request, f"A prospecção '{lead.nome_fantasia or lead.razao_social}' foi marcada como inviável.")
            return redirect('lead_list')

        elif novo_status == 'negociacao':
            services.mover_lead_para_negociacao(lead, request.user)

            messages.info(request, "Prospecção movida para Em Negociação.")
            return redirect('lead_list')

    return redirect('lead_list')


@user_passes_test(grupo_LastMile_required)
@login_required
def lead_quick_proposal(request, pk):
    """Abertura rápida de proposta diretamente na lista de leads."""
    if request.method != 'POST':
        return redirect('lead_list')

    lead = get_object_or_404(Lead, pk=pk)
    cliente_id = request.POST.get('cliente_id')
    enderecos_ids = request.POST.getlist('enderecos_selecionados')
    nome_proposta = (request.POST.get('nome_proposta') or '').strip()
    ticket_cliente = services.parse_ticket_value(request.POST.get('ticket_cliente'))
    ticket_empresa = services.parse_ticket_value(request.POST.get('ticket_empresa'))

    if not cliente_id:
        messages.error(request, "Selecione o cliente final para abrir a cotação.")
        return redirect('lead_list')

    if not enderecos_ids:
        messages.error(request, "Selecione pelo menos um login/unidade para abrir a cotação.")
        return redirect('lead_list')

    if request.POST.get('ticket_cliente') and ticket_cliente is None:
        messages.error(request, "Informe um valor válido para o ticket do cliente.")
        return redirect('lead_list')

    if request.POST.get('ticket_empresa') and ticket_empresa is None:
        messages.error(request, "Informe um valor válido para o ticket da empresa.")
        return redirect('lead_list')

    enderecos = list(
        Endereco.objects.filter(
            cliente_id=cliente_id,
            pk__in=enderecos_ids,
        ).select_related('cliente')
    )

    if len(enderecos) != len(set(enderecos_ids)):
        messages.error(request, "Os logins selecionados não pertencem ao cliente informado.")
        return redirect('lead_list')

    partner = services.converter_lead_em_parceiro_rapido(
        lead,
        enderecos,
        request.user,
        ticket_cliente=ticket_cliente,
        ticket_empresa=ticket_empresa,
        nome_proposta=nome_proposta or None,
    )
    messages.success(
        request,
        f"Cotação aberta com sucesso! {len(enderecos)} link(s) criado(s) para {partner.nome_fantasia or partner.razao_social}.",
    )
    return redirect('partner_detail', pk=partner.pk)


@user_passes_test(grupo_LastMile_required)
@login_required
def lead_convert(request, pk):
    """Tela Oficial de Conversão: Salva Parceiro, Proposta e TRANSFERE HISTÓRICO"""
    lead = get_object_or_404(Lead, pk=pk)

    partner_draft = services.montar_rascunho_parceiro_do_lead(lead)

    if request.method == 'POST':
        form = ProposalForm(request.POST)
        enderecos_ids = request.POST.getlist('enderecos_selecionados')

        if form.is_valid():
            if not enderecos_ids:
                messages.error(request, "Selecione pelo menos uma unidade de instalação.")
                return render(request, 'partners/proposal_form.html', {'form': form, 'partner': partner_draft, 'is_lead_conversion': True})

            resultado = services.converter_lead_em_parceiro(lead, form, enderecos_ids, request.user)
            partner_draft = resultado['partner']
            qtd_links = resultado['qtd_links']

            if resultado['partner_created']:
                messages.success(request, f"Conversão Concluída! {qtd_links} links gerados para {partner_draft.nome_fantasia}.")
            else:
                messages.success(request, f"Conversão concluída! {qtd_links} links foram vinculados ao parceiro já existente {partner_draft.nome_fantasia or partner_draft.razao_social}.")
            return redirect('partner_detail', pk=partner_draft.pk)
    else:
        form = ProposalForm()

    return render(request, 'partners/proposal_form.html', {
        'form': form,
        'partner': partner_draft,
        'is_lead_conversion': True
    })


@user_passes_test(grupo_LastMile_required)
@login_required
def integracoes_view(request):
    if request.method == 'POST':
        planilha = request.FILES.get('arquivo_planilha')

        if not planilha:
            return JsonResponse({'erro': 'Nenhum arquivo anexado.'}, status=400)

        try:
            conteudo, filename = services.processar_planilha_leads(planilha, request.user)
        except services.PlanilhaLeadsError as exc:
            return JsonResponse({'erro': str(exc)}, status=500)

        response = HttpResponse(
            conteudo,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    return render(request, 'leads/integracoes.html')


def _render_enderecos_lastmile(request, setor_atual=None):
    """Grid de Escola + RE/RI/Mapa Calor (ADR-011/ADR-013/ADR-015/RN-043).
    `setor_atual` (ADR-017/PO-053) filtra para as escolas com atividade
    naquele Setor, e faz o template mostrar so a(s) linha(s) de RE/RI/MC
    que de fato estiverem nesse Setor — usado tanto pela tela global
    quanto pela tela de Setor, que reaproveita este mesmo grid."""
    q = (request.GET.get('q') or '').strip()
    cidade = (request.GET.get('cidade') or '').strip()
    estado = (request.GET.get('estado') or '').strip().upper()

    # RN-066: filtros exclusivos da Tela de Setor (tipo de subatividade,
    # Responsavel e Status) — lidos sempre, mas so tem efeito quando
    # `setor_atual` esta presente (aplicado dentro do service). O grid
    # global nunca os recebe do template (RN-066), e o service tambem os
    # ignora sem `setor_nome` como segunda camada de protecao.
    tipos_subatividade = [
        tipo for tipo in request.GET.getlist('tipo') if tipo in ('re', 'ri', 'mc')
    ]
    responsavel_filtro_raw = (request.GET.get('responsavel') or '').strip()
    responsavel_filtro_id = int(responsavel_filtro_raw) if responsavel_filtro_raw.isdigit() else None
    status_filtro_nome = (request.GET.get('status') or '').strip()

    # RN-067: filtro de cor do indicador de conectividade (RN-062) —
    # exclusivo do grid global. Lido sempre (mesmo padrao do RN-066
    # acima), mas so tem efeito quando `setor_atual` esta ausente
    # (segunda camada de protecao aplicada dentro do service).
    cores_conectividade = [
        cor for cor in request.GET.getlist('cor') if cor in ('verde', 'amarelo', 'vermelho')
    ]

    escolas = services.filtrar_escolas_lastmile(
        q=q, cidade=cidade, estado=estado, setor_nome=setor_atual,
        tipos_subatividade=tipos_subatividade, responsavel_id=responsavel_filtro_id, status_nome=status_filtro_nome,
        cores_conectividade=cores_conectividade,
    )

    # RN-065: card de RE/RI so existe na tela de Setor (setor_atual
    # presente) — evita a consulta extra no grid global.
    total_rede_externa = total_rede_interna = 0
    if setor_atual:
        total_rede_externa, total_rede_interna = services.contar_rede_externa_interna_por_setor(escolas, setor_atual)

    paginator = Paginator(escolas, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    processo_re_padrao = Processo.objects.filter(nome=RedeExterna.NOME_PROCESSO_PADRAO).prefetch_related('setores').first()
    processo_ri_padrao = Processo.objects.filter(nome=RedeInterna.NOME_PROCESSO_PADRAO).prefetch_related('setores').first()
    processo_mc_padrao = Processo.objects.filter(nome=MapaCalor.NOME_PROCESSO_PADRAO).prefetch_related('setores').first()

    # RN-060: Responsavel filtrado por AcessoSetor do Setor de cada linha.
    # Pre-calcula a lista elegivel por Setor do catalogo (uma unica vez por
    # pagina, nao por linha/escola) para nao gerar N+1 (CLAUDE.md secao 7).
    todos_ativos = list(get_user_model().objects.filter(is_active=True).order_by('first_name', 'last_name', 'username'))
    setores_catalogo = [
        setor
        for processo in (processo_re_padrao, processo_ri_padrao, processo_mc_padrao)
        if processo
        for setor in processo.setores.all()
    ]
    responsavel_opcoes_por_setor = services.responsavel_opcoes_por_setor(setores_catalogo)

    def _opcoes_responsavel(rede):
        if rede and rede.setor_id:
            return responsavel_opcoes_por_setor.get(rede.setor_id, todos_ativos)
        return todos_ativos

    for escola in page_obj:
        # RedeExterna/RedeInterna/MapaCalor sao OneToOne reverso — sem
        # registro para a escola, o acesso direto (fora do template)
        # levanta RelatedObjectDoesNotExist; getattr com default trata
        # esse caso como "sem rede ainda", igual ao template.
        escola.responsavel_opcoes_re = _opcoes_responsavel(getattr(escola, 'rede_externa', None))
        escola.responsavel_opcoes_ri = _opcoes_responsavel(getattr(escola, 'rede_interna', None))
        escola.responsavel_opcoes_mc = _opcoes_responsavel(getattr(escola, 'mapa_calor', None))

    # RN-066: opcoes dos filtros exclusivos da Tela de Setor — so calculadas
    # com `setor_atual` presente (evita consulta extra no grid global).
    responsavel_opcoes_filtro = []
    status_opcoes_filtro = []
    if setor_atual:
        setores_do_nome_atual = [setor for setor in setores_catalogo if setor.nome == setor_atual]
        if setores_do_nome_atual:
            responsavel_opcoes_filtro = responsavel_opcoes_por_setor.get(setores_do_nome_atual[0].id, [])
        status_opcoes_filtro = services.status_opcoes_por_nome_setor(setor_atual)

    return render(request, 'leads/enderecos_lastmile.html', {
        'page_obj': page_obj,
        'total_enderecos': paginator.count,
        'total_rede_externa': total_rede_externa,
        'total_rede_interna': total_rede_interna,
        'processo_re_padrao': processo_re_padrao,
        'processo_ri_padrao': processo_ri_padrao,
        'processo_mc_padrao': processo_mc_padrao,
        'setor_atual': setor_atual,
        'editavel_parceiro': setor_atual == SETOR_PARCEIRO_EDITAVEL,
        'responsavel_opcoes': todos_ativos,
        'q': q,
        'cidade': cidade,
        'estado': estado,
        'tipos_subatividade_selecionados': tipos_subatividade,
        'responsavel_opcoes_filtro': responsavel_opcoes_filtro,
        'responsavel_filtro_id': responsavel_filtro_id,
        'status_opcoes_filtro': status_opcoes_filtro,
        'status_filtro_nome': status_filtro_nome,
        'cores_conectividade_selecionadas': cores_conectividade,
    })


@user_passes_test(grupo_LastMile_required)
@login_required
def enderecos_lastmile_view(request):
    return _render_enderecos_lastmile(request)


@user_passes_test(grupo_LastMile_required)
@login_required
def enderecos_lastmile_cliente_view(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    q = (request.GET.get('q') or '').strip()
    sort = (request.GET.get('sort') or 'logradouro').strip()

    enderecos = services.filtrar_enderecos_lastmile_cliente(cliente, q=q, sort=sort)

    paginator = Paginator(enderecos, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'leads/enderecos_lastmile_cliente.html', {
        'cliente': cliente,
        'page_obj': page_obj,
        'total_enderecos': enderecos.count(),
        'q': q,
        'sort': sort,
    })


@user_passes_test(grupo_LastMile_required)
@login_required
def lead_empresa_list(request):
    busca_empresa = (request.GET.get('empresa') or '').strip()
    busca_cidade = (request.GET.get('cidade') or '').strip()
    busca_estado = (request.GET.get('estado') or '').strip()

    empresas = services.filtrar_lead_empresas(
        busca_empresa=busca_empresa,
        busca_cidade=busca_cidade,
        busca_estado=busca_estado,
    )

    paginator = Paginator(empresas, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    filtros_endereco, possui_filtro_endereco = services.montar_filtro_enderecos_lead_empresa(
        busca_empresa=busca_empresa,
        busca_cidade=busca_cidade,
        busca_estado=busca_estado,
    )
    services.anexar_enderecos_preview_empresas(page_obj.object_list, filtros_endereco, possui_filtro_endereco)

    return render(request, 'leads/lead_empresa_list.html', {
        'page_obj': page_obj,
        'busca_empresa': busca_empresa,
        'busca_cidade': busca_cidade,
        'busca_estado': busca_estado,
    })


@user_passes_test(grupo_LastMile_required)
@login_required
def lead_empresa_detail(request, pk):
    empresa = get_object_or_404(LeadEmpresa, pk=pk)
    q = (request.GET.get('q') or '').strip()

    enderecos = services.filtrar_enderecos_lead_empresa(empresa, q=q)

    paginator = Paginator(enderecos, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    services.anexar_lead_espelho_e_parceiro(page_obj.object_list)

    return render(request, 'leads/lead_empresa_detail.html', {
        'empresa': empresa,
        'page_obj': page_obj,
        'q': q,
        'total_enderecos': enderecos.count(),
    })


@user_passes_test(grupo_LastMile_required)
@login_required
def lead_empresa_endereco_create(request, pk):
    empresa = get_object_or_404(LeadEmpresa, pk=pk)

    if request.method == 'POST':
        form = LeadEnderecoForm(request.POST, empresa=empresa)
        if form.is_valid():
            endereco = form.save(commit=False)
            endereco.empresa = empresa
            endereco.save()
            services.criar_ou_atualizar_lead_espelho_empresa_endereco(empresa, endereco)
            messages.success(request, "Novo endereco cadastrado com sucesso para este provedor.")
            return redirect('lead_empresa_detail', pk=empresa.pk)
    else:
        form = LeadEnderecoForm(empresa=empresa)

    return render(request, 'leads/lead_endereco_form.html', {
        'empresa': empresa,
        'form': form,
    })


@user_passes_test(grupo_LastMile_required)
@login_required
def lead_empresa_endereco_update(request, empresa_pk, pk):
    empresa = get_object_or_404(LeadEmpresa, pk=empresa_pk)
    endereco = get_object_or_404(LeadEndereco, pk=pk, empresa=empresa)

    if request.method == 'POST':
        form = LeadEnderecoForm(request.POST, instance=endereco, empresa=empresa)
        if form.is_valid():
            form.save()
            services.criar_ou_atualizar_lead_espelho_empresa_endereco(empresa, endereco)
            messages.success(request, "Endereço atualizado com sucesso.")
            return redirect('lead_empresa_detail', pk=empresa.pk)
    else:
        form = LeadEnderecoForm(instance=endereco, empresa=empresa)

    return render(request, 'leads/lead_endereco_form.html', {
        'empresa': empresa,
        'form': form,
        'endereco': endereco,
    })


@user_passes_test(grupo_LastMile_required)
@login_required
def lead_empresa_update(request, pk):
    empresa = get_object_or_404(LeadEmpresa, pk=pk)

    if request.method == 'POST':
        form = LeadEmpresaForm(request.POST, instance=empresa)
        if form.is_valid():
            form.save()
            for lead in empresa.leads_legados.all():
                services.sync_lead_to_structured_models(lead)
            messages.success(request, "Dados do provedor atualizados com sucesso.")
            return redirect('lead_empresa_detail', pk=empresa.pk)
    else:
        form = LeadEmpresaForm(instance=empresa)

    return render(request, 'leads/lead_empresa_form.html', {
        'empresa': empresa,
        'form': form,
    })


@user_passes_test(grupo_LastMile_required)
@login_required
def api_lead_empresa_search(request):
    q = (request.GET.get('q') or '').strip()
    estado = (request.GET.get('estado') or '').strip().upper()
    cidade = (request.GET.get('cidade') or '').strip()

    empresas = services.buscar_empresas_para_api(q=q, estado=estado, cidade=cidade)

    return JsonResponse({
        'results': [{
            'id': empresa.id,
            'nome': empresa.nome_fantasia or empresa.razao_social,
            'razao_social': empresa.razao_social,
            'documento': empresa.cnpj_cpf or '',
            'total_enderecos': empresa.total_enderecos,
        } for empresa in empresas]
    })


@user_passes_test(grupo_LastMile_required)
@login_required
def api_lead_empresa_enderecos(request, pk):
    empresa = get_object_or_404(LeadEmpresa, pk=pk)
    q = (request.GET.get('q') or '').strip()

    enderecos = services.buscar_enderecos_empresa_para_api(empresa, q=q)

    return JsonResponse({
        'results': [{
            'id': endereco.id,
            'endereco': endereco.endereco or '',
            'numero': endereco.numero or 'S/N',
            'bairro': endereco.bairro or '',
            'cidade': endereco.cidade or '',
            'estado': endereco.estado or '',
            'cep': endereco.cep or '',
            'label': f"{endereco.endereco or 'Endereço não informado'}, {endereco.numero or 'S/N'}",
        } for endereco in enderecos[:100]]
    })


@user_passes_test(grupo_LastMile_required)
@login_required
def endereco_lastmile_lead_address_grid(request, endereco_pk):
    endereco = get_object_or_404(
        Endereco.objects.select_related('cliente'),
        pk=endereco_pk,
        em_os_comercial_lastmile=True,
        os_atual_aberta=True,
    )

    q = (request.GET.get('q') or '').strip()
    cidade = _get_request_param_or_default(request, 'cidade', endereco.cidade)
    estado = _get_request_param_or_default(request, 'estado', endereco.estado).upper()

    enderecos = services.buscar_lead_enderecos_grid(cidade=cidade, estado=estado, q=q)

    return JsonResponse({
        'filtros': {
            'cidade': cidade,
            'estado': estado,
        },
        'results': [{
            'id': item.id,
            'lead_nome': item.empresa.nome_fantasia or item.empresa.razao_social or f'Lead #{item.empresa_id}',
            'lead_documento': item.empresa.cnpj_cpf or '',
            'estado': item.estado or '',
            'cidade': item.cidade or '',
            'bairro': item.bairro or '',
            'cep': item.cep or '',
            'endereco': item.endereco or '',
            'numero': item.numero or 'S/N',
            'logradouro_label': f"{item.endereco or 'Não informado'}, {item.numero or 'S/N'}",
        } for item in enderecos]
    })


def download_modelo_google_view(request):
    df = pd.DataFrame(columns=['Serviço', 'Cidade', 'Estado', 'Bairro', 'CEP'])

    df.loc[0] = ['Provedor de Internet', 'Fortaleza', 'CE', 'Centro', '60000-000']
    df.loc[1] = ['Link Dedicado', 'Eusébio', 'CE', 'Guaribas', '61760-000']

    registrar_auditoria_integracao(
        integration='buscar_fornecedores',
        action='download_modelo',
        usuario=request.user if request.user.is_authenticated else None,
        arquivo_nome='Modelo_Busca_Google.xlsx',
        detalhes={'colunas': list(df.columns)},
    )

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="Modelo_Busca_Google.xlsx"'

    df.to_excel(response, index=False)

    return response


_MODELO_REDE_POR_TIPO = {'re': RedeExterna, 'ri': RedeInterna, 'mc': MapaCalor}

_ROTULO_CURTO_POR_TIPO = {'re': 'RE', 'ri': 'RI', 'mc': 'MC'}
"""RN-043: rotulo curto do badge/mensagem, generico para os tres processos
(RedeExterna/RedeInterna/MapaCalor) que compartilham as mesmas telas."""

_MENSAGEM_ATUALIZACAO_POR_TIPO = {
    're': "Rede Externa atualizada.",
    'ri': "Rede Interna atualizada.",
    'mc': "Mapa Calor atualizado.",
}

SETOR_PARCEIRO_EDITAVEL = "Lastmile"
"""RN-030/ADR-018: Parceiro de RE/RI so pode ser vinculado a partir da tela
deste Setor de negocio (catalogo RN-025) — nao do grupo de permissao
Django `LastMile`, que ja protege a tela inteira."""

STATUS_ENVIO_OUTRO_SETOR = "Aguardando"
"""RN-033: Status aplicado automaticamente quando o Setor selecionado na
Tela de Setor deixa de ser o Setor atual (subatividade enviada a outro
Setor) — criado no Setor de destino se ainda nao existir."""

STATUS_INICIAL_GRID_GLOBAL = "Novo"
"""RN-035: no grid global de Enderecos Lastmile (sem `setor_atual`), o
Status deixa de ser escolhido manualmente — fica sempre neste Status do
Setor escolhido, criado automaticamente se ainda nao existir (mesmo
padrao do "Aguardando" na Tela de Setor, RN-033)."""

_MODELO_REDE_COTACAO_POR_TIPO = {'re': RedeExterna, 'ri': RedeInterna}
"""RN-044/ADR-026: cotacao de Parceiro (N candidatos, um vencedor) so se
aplica a RE/RI — Mapa Calor fica fora do escopo desta feature."""

STATUS_COTACAO = "Cotacao"
"""RN-044: nome do SetorStatus (catalogo RN-025) que libera o modal de
gestao de cotacao na linha expandida da Tela do Setor "Lastmile" —
semeado pela migration `0016_seed_status_cotacao_lastmile` para o Setor
"Lastmile" dos Processos de RE e de RI."""


@user_passes_test(grupo_LastMile_required)
@login_required
def escola_rede_editar(request, escola_pk, tipo):
    """PO-051/ADR-015: edita Setor/Status do processo interno (RedeExterna,
    RedeInterna ou MapaCalor, RN-043/PO-067) de uma escola, direto no grid
    de Enderecos Lastmile.
    Cria o registro se ainda nao existir. O Processo e fixo por tipo
    (`NOME_PROCESSO_PADRAO`, configurado uma vez na tela de Processos,
    PO-050) — nao e escolhido linha a linha. PO-056/RN-030: Parceiro tambem
    e editado aqui, mas so quando `setor_atual` for o Setor "Lastmile".
    RN-033: na Tela de Setor, o Status enviado pelo POST so e aplicado
    quando o Setor escolhido continua sendo o `setor_atual`; ao mudar para
    outro Setor, o Status vira automaticamente "Aguardando" do Setor de
    destino, independente do que foi submetido. RN-035: no grid global
    (sem `setor_atual`), o Status nao e recebido do POST — fica sempre
    "Novo" do Setor escolhido, criado automaticamente se faltar.

    RN-052/ADR-027: Responsavel (usuario do sistema) e atribuivel/
    reatribuivel manualmente nas duas telas (mesmo `<select>` de Setor/
    Status) e e zerado automaticamente junto com o Status quando a
    subatividade e enviada a outro Setor. Setor/Status/Responsavel
    continuam opcionais no banco; a obrigatoriedade dos tres so e cobrada
    no momento em que o submit resultaria num Setor e Status preenchidos
    (a combinacao que RN-026/033/035 ja tratam como "atribuicao concluida")
    sem Responsavel — isso preserva as edicoes parciais ja existentes (ex.:
    so Parceiro, ou Status deixado em branco na Tela de Setor).

    RN-056: Responsavel so e obrigatorio dentro da Tela do proprio Setor
    (`setor_atual` definido) e quando a subatividade permanece nesse mesmo
    Setor apos a edicao — nunca no grid global (`elif not setor_atual`
    abaixo), nem quando a subatividade e enviada a outro Setor
    (`enviado_a_outro_setor` abaixo). Isso vale tambem para a primeira
    atribuicao de Setor pelo grid global (subatividade que ainda nao tinha
    nenhum): quem atribui por ali nao esta necessariamente dentro do Setor
    de destino, entao nao ha como exigir que ja saiba o Responsavel.

    RN-061/ADR-031: enviar a subatividade a outro Setor (`enviado_a_outro_setor`)
    tambem verifica se ha Campo do Setor de origem com regra de
    obrigatoriedade cadastrada (tela "Campos") para o Setor de destino
    escolhido; havendo algum `CampoValor` ainda vazio, a troca inteira e
    bloqueada (nada e salvo), com erro indicando o(s) Campo(s) faltante(s).
    So se aplica numa troca real (Setor de origem ja definido) — nunca na
    primeira atribuicao de Setor."""
    modelo = _MODELO_REDE_POR_TIPO.get(tipo)
    if modelo is None:
        raise Http404("Tipo de rede invalido.")

    User = get_user_model()
    escola = get_object_or_404(Escola, pk=escola_pk)
    rede = modelo.objects.filter(escola=escola).select_related("responsavel").first()
    setor_anterior_nome = rede.setor.nome if rede and rede.setor_id else None
    status_anterior_nome = rede.status.nome if rede and rede.status_id else None
    parceiro_anterior_nome = str(rede.parceiro) if rede and rede.parceiro_id else None
    responsavel_anterior_nome = services.nome_usuario_ou_none(rede.responsavel) if rede and rede.responsavel_id else None
    processo_padrao = Processo.objects.filter(nome=modelo.NOME_PROCESSO_PADRAO).first()
    setor_atual = (request.POST.get("setor_atual") or request.GET.get("setor_atual") or "").strip() or None
    ja_tem_setor = bool(rede and rede.setor_id)
    editavel = bool(setor_atual) or not ja_tem_setor
    editavel_parceiro = setor_atual == SETOR_PARCEIRO_EDITAVEL
    erro = None
    sucesso = None

    if request.method == "POST":
        if not editavel:
            erro = (
                f"Este {_ROTULO_CURTO_POR_TIPO[tipo]} ja esta no Setor '{rede.setor.nome}'. "
                "So e possivel alterar pela tela desse Setor."
            )
        elif processo_padrao is None:
            erro = f"Processo padrao '{modelo.NOME_PROCESSO_PADRAO}' nao esta cadastrado na tela de Processos."
        else:
            setor_id = request.POST.get("setor") or None
            status_id = request.POST.get("status") or None

            rede = rede or modelo(escola=escola)
            rede.processo = processo_padrao
            rede.setor = Setor.objects.filter(pk=setor_id).first() if setor_id else None

            enviado_a_outro_setor = bool(setor_atual) and bool(rede.setor) and rede.setor.nome != setor_atual
            # RN-061/ADR-031: enviar a outro Setor pode exigir Campos do
            # Setor de origem preenchidos (regra cadastrada na tela
            # "Campos") — calculado aqui, antes de aplicar qualquer mudanca,
            # para bloquear a troca inteira quando houver pendencia.
            campos_obrigatorios_pendentes = (
                services.campos_obrigatorios_pendentes(rede, setor_atual, rede.setor.nome)
                if enviado_a_outro_setor else []
            )
            # RN-056: Responsavel so e obrigatorio dentro da Tela do proprio
            # Setor, permanecendo nesse mesmo Setor — nunca no grid global
            # (setor_atual vazio), nem ao enviar a outro Setor.
            permanece_no_setor_atual = bool(setor_atual) and not enviado_a_outro_setor
            if enviado_a_outro_setor:
                rede.status, _ = SetorStatus.objects.get_or_create(
                    setor=rede.setor, nome=STATUS_ENVIO_OUTRO_SETOR,
                )
                # RN-052/ADR-027: Responsavel e zerado junto com o Status ao
                # enviar a subatividade a outro Setor, liberando para
                # reatribuicao por quem estiver no Setor de destino.
                rede.responsavel = None
            elif not setor_atual:
                # RN-035: grid global — Status nao vem do POST, fica sempre
                # "Novo" do Setor escolhido (sem Setor, fica sem Status).
                rede.status = None
                if rede.setor:
                    rede.status, _ = SetorStatus.objects.get_or_create(
                        setor=rede.setor, nome=STATUS_INICIAL_GRID_GLOBAL,
                    )
                responsavel_id = request.POST.get("responsavel") or None
                rede.responsavel = User.objects.filter(pk=responsavel_id).first() if responsavel_id else None
            else:
                rede.status = SetorStatus.objects.filter(pk=status_id).first() if status_id else None
                responsavel_id = request.POST.get("responsavel") or None
                rede.responsavel = User.objects.filter(pk=responsavel_id).first() if responsavel_id else None
            if editavel_parceiro:
                parceiro_id = request.POST.get("parceiro") or None
                rede.parceiro = Partner.objects.filter(pk=parceiro_id).first() if parceiro_id else None

            # RN-060: Responsavel so pode ser um usuario com AcessoSetor
            # concedido para o Setor que a subatividade tem agora (ou
            # superusuario) — validado no servidor, nao so no HTML do
            # <select>, para nao aceitar um responsavel_id fora da lista
            # permitida mesmo que o formulario tenha sido manipulado.
            responsavel_valido = (
                not rede.responsavel_id
                or services.usuarios_responsavel_opcoes(rede.setor).filter(pk=rede.responsavel_id).exists()
            )

            if not responsavel_valido:
                erro = "Este usuário não tem acesso a este Setor para ser Responsável."
            elif campos_obrigatorios_pendentes:
                erro = (
                    f"Preencha antes de enviar para o Setor '{rede.setor.nome}': "
                    f"{', '.join(campos_obrigatorios_pendentes)} (RN-061)."
                )
            else:
                try:
                    rede.full_clean()
                except ValidationError as exc:
                    erro = " ".join(sum(exc.message_dict.values(), []))
                else:
                    # RN-052/RN-056: Setor e Status continuam opcionais no
                    # banco, mas dentro da Tela do proprio Setor,
                    # permanecendo nele, Responsavel tambem precisa estar
                    # preenchido quando Setor e Status ja estao preenchidos.
                    # Fora dai — grid global (RN-035) ou envio a outro Setor,
                    # que zera Responsavel de proposito — a obrigatoriedade
                    # nao se aplica (ver acima).
                    if permanece_no_setor_atual and rede.setor_id and rede.status_id and not rede.responsavel_id:
                        erro = "Selecione um Responsável para salvar — Setor, Status e Responsável são obrigatórios juntos."
                    else:
                        rede.save()
                        services.registrar_historico_alteracao_rede(
                            rede, request.user, setor_anterior_nome, status_anterior_nome, parceiro_anterior_nome,
                            responsavel_anterior_nome=responsavel_anterior_nome, setor_atual=setor_atual,
                        )
                        sucesso = _MENSAGEM_ATUALIZACAO_POR_TIPO[tipo]

    if tipo == "re":
        referencia = escola.referencia_rede_externa
    elif tipo == "ri":
        referencia = escola.referencia_rede_interna
    else:
        referencia = escola.referencia_mapa_calor
    # PO: quando ha erro, nada foi salvo — o pertencimento ao Setor atual da
    # tela precisa refletir o valor persistido antes da tentativa
    # (setor_anterior_nome), nao o Setor que o usuario tentou atribuir em
    # memoria (`rede.setor`, ja alterado pelo POST antes do bloqueio).
    # Sem isso, uma troca de Setor bloqueada por erro (ex.: RN-061) fazia o
    # front remover a linha da tela como se a subatividade tivesse saido do
    # Setor, embora nada tenha sido salvo — so um refresh de pagina trazia
    # os inputs de volta.
    setor_nome_persistido = setor_anterior_nome if erro else (rede.setor.nome if rede and rede.setor_id else None)
    pertence_ao_setor_atual = (not setor_atual) or (setor_nome_persistido == setor_atual)

    return render(request, "leads/partials/escola_rede_row.html", {
        "escola": escola,
        "tipo": tipo,
        "rede": rede,
        "processo_padrao": processo_padrao,
        "referencia": referencia,
        "erro": erro,
        "sucesso": sucesso,
        # PO: faltava aqui — sem isso, o template (`{% if setor_atual or not
        # rede.setor_id %}`) sempre caia no ramo somente-leitura quando a
        # subatividade ja tinha Setor, fazendo os selects sumirem apos
        # qualquer Salvar (erro ou sucesso) dentro da Tela do Setor, so
        # voltando com um refresh de pagina inteira.
        "setor_atual": setor_atual,
        "pertence_ao_setor_atual": pertence_ao_setor_atual,
        "editavel_parceiro": editavel_parceiro,
        # RN-060: opcoes de Responsavel do Setor atual da linha (ou de
        # todos os usuarios ativos, sem Setor definido).
        "responsavel_opcoes": services.usuarios_responsavel_opcoes(rede.setor if rede and rede.setor_id else None),
    })


@user_passes_test(grupo_LastMile_required)
@login_required
def escola_rede_parceiro_modal(request, escola_pk, tipo):
    """PO-056/RN-030/ADR-018: modal de selecao de Parceiro para vincular ao
    processo interno (RedeExterna/RedeInterna/MapaCalor, RN-043) de uma
    Escola. So retorna
    resultados quando `setor_atual` for o Setor "Lastmile" — a mesma
    condicao que libera a edicao em `escola_rede_editar`. Nao salva nada;
    apenas preenche o campo na linha, que e persistido pelo botao "Salvar"
    ja existente."""
    modelo = _MODELO_REDE_POR_TIPO.get(tipo)
    if modelo is None:
        raise Http404("Tipo de rede invalido.")

    escola = get_object_or_404(Escola, pk=escola_pk)
    setor_atual = (request.GET.get("setor_atual") or "").strip()
    q = (request.GET.get("q") or "").strip()
    cidade = (request.GET.get("cidade") or "").strip()
    estado = (request.GET.get("estado") or "").strip().upper()
    bairro = (request.GET.get("bairro") or "").strip()
    erro = None
    parceiros = []

    if setor_atual != SETOR_PARCEIRO_EDITAVEL:
        erro = f"Parceiro so pode ser vinculado pela tela do Setor {SETOR_PARCEIRO_EDITAVEL}."
    else:
        parceiros_queryset = Partner.objects.all()
        if q:
            parceiros_queryset = parceiros_queryset.filter(
                Q(nome_fantasia__icontains=q) | Q(razao_social__icontains=q) | Q(cnpj_cpf__icontains=q)
            )
        if estado:
            parceiros_queryset = parceiros_queryset.filter(proposals__client_address__estado__iexact=estado)
        if cidade:
            parceiros_queryset = parceiros_queryset.filter(proposals__client_address__cidade__icontains=cidade)
        if bairro:
            parceiros_queryset = parceiros_queryset.filter(proposals__client_address__bairro__icontains=bairro)
        parceiros = list(parceiros_queryset.distinct().order_by("nome_fantasia", "razao_social", "id")[:50])

    return render(request, "leads/partials/escola_rede_parceiro_modal.html", {
        "escola": escola,
        "tipo": tipo,
        "q": q,
        "cidade": cidade,
        "bairro": bairro,
        "estado": estado,
        "parceiros": parceiros,
        "erro": erro,
    })


@user_passes_test(grupo_LastMile_required)
@login_required
def escola_rede_historico(request, escola_pk, tipo):
    """PO-054/RN-029: historico individual (comentarios, anexos e
    alteracao de status/dados) de um RedeExterna/RedeInterna/MapaCalor
    (RN-043), exibido em modal no grid de Enderecos Lastmile. RE/RI/MC so
    tem historico depois de criados pelo menos uma vez
    (`escola_rede_editar`)."""
    modelo = _MODELO_REDE_POR_TIPO.get(tipo)
    if modelo is None:
        raise Http404("Tipo de rede invalido.")

    escola = get_object_or_404(Escola, pk=escola_pk)
    rede = get_object_or_404(modelo, escola=escola)
    erro = None

    if request.method == "POST":
        descricao = request.POST.get("descricao")
        arquivo = request.FILES.get("arquivo")
        if not services.adicionar_historico_rede(rede, descricao, arquivo, request.user):
            erro = "Informe um comentario ou selecione um arquivo para anexar."

    return render(request, "leads/partials/escola_rede_historico_modal.html", {
        "escola": escola,
        "tipo": tipo,
        "rede": rede,
        "historico": services.historico_rede(rede),
        "erro": erro,
    })


@user_passes_test(grupo_LastMile_required)
@login_required
def escola_rede_campos(request, escola_pk, tipo):
    """PO-058/RN-032/ADR-019: modal com os Campos personalizados (RN-031)
    de um RedeExterna/RedeInterna/MapaCalor (RN-043), agrupados por Setor
    dono. Editavel somente nos campos cujo Setor dono e o `setor_atual`
    (mesma regra do Parceiro, RN-030). RE/RI/MC so tem Campos depois de
    criados pelo menos uma vez (`escola_rede_editar`)."""
    modelo = _MODELO_REDE_POR_TIPO.get(tipo)
    if modelo is None:
        raise Http404("Tipo de rede invalido.")

    escola = get_object_or_404(Escola, pk=escola_pk)
    rede = get_object_or_404(modelo, escola=escola)
    setor_atual = (request.POST.get("setor_atual") or request.GET.get("setor_atual") or "").strip() or None
    erros = []
    sucesso = None

    if request.method == "POST":
        erros = services.salvar_campos_rede(rede, tipo, setor_atual, request.POST, usuario=request.user)
        if not erros:
            sucesso = "Campos atualizados."

    return render(request, "leads/partials/escola_rede_campos_modal.html", {
        "escola": escola,
        "tipo": tipo,
        "rede": rede,
        "setor_atual": setor_atual,
        "grupos": services.campos_grid_rede(rede, tipo, setor_atual),
        "erros": erros,
        "sucesso": sucesso,
    })


def _contexto_modal_cotacao(escola, tipo, rede, setor_atual, erro=None, parceiros=None, q='', cidade='', bairro='', estado=''):
    """RN-044: contexto comum do modal de cotacao, reaproveitado pelas 4
    views (abrir/buscar, adicionar, selecionar, remover) para nao repetir a
    montagem em cada uma."""
    return {
        "escola": escola,
        "tipo": tipo,
        "rede": rede,
        "setor_atual": setor_atual,
        "q": q,
        "cidade": cidade,
        "bairro": bairro,
        "estado": estado,
        "parceiros": parceiros or [],
        "candidatos": services.candidatos_cotacao_rede(rede),
        "erro": erro,
    }


def _erro_trava_cotacao(rede, tipo, setor_atual):
    """RN-044/ADR-026: mesma trava da RN-030 (Parceiro), aplicada tambem ao
    modal de cotacao — disponivel somente na Tela do Setor "Lastmile" e com
    o RE/RI exibido no Status "Cotacao"."""
    if setor_atual != SETOR_PARCEIRO_EDITAVEL:
        return f"A cotação só pode ser gerida pela tela do Setor {SETOR_PARCEIRO_EDITAVEL}."
    if not (rede.status_id and rede.status.nome == STATUS_COTACAO):
        return f'Este {_ROTULO_CURTO_POR_TIPO[tipo]} não está no Status "{STATUS_COTACAO}".'
    return None


@user_passes_test(grupo_LastMile_required)
@login_required
def escola_rede_cotacao_modal(request, escola_pk, tipo):
    """PO-068/RN-044/ADR-026: modal de gestao da cotacao (N Parceiros
    candidatos, um vencedor) de um RedeExterna/RedeInterna. Disponivel
    somente na Tela do Setor "Lastmile" (mesma trava da RN-030) e com o
    RE/RI exibido no Status "Cotacao" (catalogo RN-025). A busca de
    Parceiro para adicionar reaproveita o mesmo filtro por nome/cidade/UF/
    bairro de `escola_rede_parceiro_modal` (RN-030)."""
    modelo = _MODELO_REDE_COTACAO_POR_TIPO.get(tipo)
    if modelo is None:
        raise Http404("Tipo de rede invalido para cotacao.")

    escola = get_object_or_404(Escola, pk=escola_pk)
    rede = get_object_or_404(modelo, escola=escola)
    setor_atual = (request.GET.get("setor_atual") or "").strip()
    q = (request.GET.get("q") or "").strip()
    cidade = (request.GET.get("cidade") or "").strip()
    estado = (request.GET.get("estado") or "").strip().upper()
    bairro = (request.GET.get("bairro") or "").strip()
    erro = _erro_trava_cotacao(rede, tipo, setor_atual)
    parceiros = []

    if not erro:
        parceiros_queryset = Partner.objects.all()
        if q:
            parceiros_queryset = parceiros_queryset.filter(
                Q(nome_fantasia__icontains=q) | Q(razao_social__icontains=q) | Q(cnpj_cpf__icontains=q)
            )
        if estado:
            parceiros_queryset = parceiros_queryset.filter(proposals__client_address__estado__iexact=estado)
        if cidade:
            parceiros_queryset = parceiros_queryset.filter(proposals__client_address__cidade__icontains=cidade)
        if bairro:
            parceiros_queryset = parceiros_queryset.filter(proposals__client_address__bairro__icontains=bairro)
        parceiros = list(parceiros_queryset.distinct().order_by("nome_fantasia", "razao_social", "id")[:50])

    return render(request, "leads/partials/escola_rede_cotacao_modal.html", _contexto_modal_cotacao(
        escola, tipo, rede, setor_atual, erro=erro, parceiros=parceiros, q=q, cidade=cidade, bairro=bairro, estado=estado,
    ))


@user_passes_test(grupo_LastMile_required)
@login_required
def escola_rede_cotacao_adicionar(request, escola_pk, tipo):
    """RN-044: adiciona (POST) um Parceiro como candidato em cotacao."""
    modelo = _MODELO_REDE_COTACAO_POR_TIPO.get(tipo)
    if modelo is None or request.method != "POST":
        raise Http404("Tipo de rede invalido para cotacao.")

    escola = get_object_or_404(Escola, pk=escola_pk)
    rede = get_object_or_404(modelo, escola=escola)
    setor_atual = (request.POST.get("setor_atual") or "").strip()
    erro = _erro_trava_cotacao(rede, tipo, setor_atual)

    if not erro:
        parceiro = Partner.objects.filter(pk=request.POST.get("parceiro")).first()
        if not parceiro:
            erro = "Selecione um Parceiro válido para adicionar."
        else:
            services.adicionar_candidato_cotacao_rede(rede, parceiro)

    return render(request, "leads/partials/escola_rede_cotacao_modal.html", _contexto_modal_cotacao(
        escola, tipo, rede, setor_atual, erro=erro,
    ))


@user_passes_test(grupo_LastMile_required)
@login_required
def escola_rede_cotacao_selecionar(request, escola_pk, tipo, candidato_pk):
    """RN-044/ADR-026: marca (POST) o candidato como "Selecionado" — os
    demais candidatos do mesmo RE/RI passam para "Recusado" e o Parceiro
    vencedor preenche `rede.parceiro` (RN-030), gerando RegistroHistorico
    Antes/Depois (RN-030/041)."""
    modelo = _MODELO_REDE_COTACAO_POR_TIPO.get(tipo)
    if modelo is None or request.method != "POST":
        raise Http404("Tipo de rede invalido para cotacao.")

    escola = get_object_or_404(Escola, pk=escola_pk)
    rede = get_object_or_404(modelo, escola=escola)
    setor_atual = (request.POST.get("setor_atual") or "").strip()
    content_type = ContentType.objects.get_for_model(modelo)
    candidato = get_object_or_404(CotacaoParceiro, pk=candidato_pk, content_type=content_type, object_id=rede.id)
    erro = _erro_trava_cotacao(rede, tipo, setor_atual)

    if not erro:
        rede = services.selecionar_candidato_cotacao_rede(candidato, request.user, setor_atual=setor_atual)

    return render(request, "leads/partials/escola_rede_cotacao_modal.html", _contexto_modal_cotacao(
        escola, tipo, rede, setor_atual, erro=erro,
    ))


@user_passes_test(grupo_LastMile_required)
@login_required
def escola_rede_cotacao_remover(request, escola_pk, tipo, candidato_pk):
    """RN-044: remove (POST) um candidato ainda nao selecionado."""
    modelo = _MODELO_REDE_COTACAO_POR_TIPO.get(tipo)
    if modelo is None or request.method != "POST":
        raise Http404("Tipo de rede invalido para cotacao.")

    escola = get_object_or_404(Escola, pk=escola_pk)
    rede = get_object_or_404(modelo, escola=escola)
    setor_atual = (request.POST.get("setor_atual") or "").strip()
    content_type = ContentType.objects.get_for_model(modelo)
    candidato = get_object_or_404(CotacaoParceiro, pk=candidato_pk, content_type=content_type, object_id=rede.id)
    erro = _erro_trava_cotacao(rede, tipo, setor_atual)

    if not erro and not services.remover_candidato_cotacao_rede(candidato):
        erro = "Não é possível remover um candidato já selecionado."

    return render(request, "leads/partials/escola_rede_cotacao_modal.html", _contexto_modal_cotacao(
        escola, tipo, rede, setor_atual, erro=erro,
    ))


@user_passes_test(grupo_LastMile_required)
@login_required
def escola_campos(request, escola_pk):
    """PO-062/RN-037/ADR-022: modal com os Campos (RN-031) cujo Setor dono
    tem escopo "Escola" — informacao que vem direto do cliente, sem vinculo
    com RE/RI. Sem trava por setor_atual: editavel por quem acessa esta
    tela (grupo LastMile), diferente da regra usada para RE/RI (RN-032)."""
    escola = get_object_or_404(Escola, pk=escola_pk)
    erros = []
    sucesso = None

    if request.method == "POST":
        erros = services.salvar_campos_escola(escola, request.POST, usuario=request.user)
        if not erros:
            sucesso = "Campos atualizados."

    return render(request, "leads/partials/escola_campos_modal.html", {
        "escola": escola,
        "grupos": services.campos_grid_escola(escola),
        "erros": erros,
        "sucesso": sucesso,
    })


@user_passes_test(grupo_LastMile_required)
@login_required
def escola_historico(request, escola_pk):
    """PO-054/RN-029: historico combinado de RE, RI e Mapa Calor (RN-043)
    de uma Escola (o registro 'pai' dos tres processos), somente leitura."""
    escola = get_object_or_404(Escola, pk=escola_pk)

    return render(request, "leads/partials/escola_historico_modal.html", {
        "escola": escola,
        "historico": services.historico_combinado_escola(escola),
    })


@user_passes_test(grupo_LastMile_required)
@login_required
def setor_status_opcoes(request):
    setor_id = request.GET.get("setor") or None
    status_opcoes = SetorStatus.objects.filter(setor_id=setor_id).order_by('nome') if setor_id else SetorStatus.objects.none()

    return render(request, "leads/partials/status_opcoes.html", {"status_opcoes": status_opcoes})


@user_passes_test(grupo_LastMile_required)
@login_required
def setor_responsavel_opcoes(request):
    """RN-060: usado pelo cascata Setor->Responsavel do grid de Enderecos
    Lastmile (`carregarStatusRede`, `enderecos_lastmile.html`) para
    atualizar as opcoes de Responsavel quando o Setor selecionado muda,
    sem submeter o formulario."""
    setor_id = request.GET.get("setor") or None
    setor = Setor.objects.filter(pk=setor_id).first() if setor_id else None

    return render(request, "leads/partials/responsavel_opcoes.html", {
        "responsavel_opcoes": services.usuarios_responsavel_opcoes(setor),
    })


@user_passes_test(grupo_Setor_required)
@login_required
def setores_list(request):
    """PO-052/ADR-016: lista os nomes de Setor cadastrados (RN-025), ponto
    de entrada da secao "Setores" do menu.

    PO-075/RN-055: mostra somente os nomes concedidos ao usuario logado
    (todos, para superusuario) — nao automaticamente todos os cadastrados."""
    nomes_setor = services.nomes_setor_visiveis_para_usuario(request.user)

    return render(request, "leads/setores_list.html", {"nomes_setor": nomes_setor})


@user_passes_test(grupo_Setor_required)
@login_required
def setor_detail(request, nome):
    """PO-053/ADR-017: reaproveita o grid de Enderecos Lastmile (Escola +
    RE/RI), filtrado para as escolas com atividade neste Setor. Mostra so
    a(s) linha(s) de RE/RI que de fato estiverem neste Setor.

    PO-075/RN-055: 403 quando o nome existe no catalogo mas nao foi
    concedido ao usuario logado (superusuario sempre passa)."""
    if not Setor.objects.filter(nome=nome).exists():
        raise Http404("Setor nao encontrado.")

    if not services.usuario_pode_acessar_setor(request.user, nome):
        raise PermissionDenied

    return _render_enderecos_lastmile(request, setor_atual=nome)
