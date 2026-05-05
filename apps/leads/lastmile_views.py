from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy

from clientes.models import Endereco
from core.models import RegistroHistorico
from partners.models import Partner, Proposal

from .models import LeadEndereco
from .views import (
    grupo_LastMile_required,
    _montar_cobertura_parceiros_por_regiao,
    _obter_ou_criar_parceiro_do_lead,
)


@user_passes_test(grupo_LastMile_required)
@login_required
def endereco_lastmile_partner_search(request, endereco_pk):
    endereco = get_object_or_404(
        Endereco.objects.select_related('cliente'),
        pk=endereco_pk,
        em_os_comercial_lastmile=True,
        os_atual_aberta=True,
    )

    q = (request.GET.get('q') or '').strip()
    estado = (request.GET.get('estado') or endereco.estado or '').strip().upper()
    cidade = (request.GET.get('cidade') or endereco.cidade or '').strip()
    parceiros_queryset = Partner.objects.all()

    if q:
        parceiros_queryset = parceiros_queryset.filter(
            Q(nome_fantasia__icontains=q)
            | Q(razao_social__icontains=q)
            | Q(cnpj_cpf__icontains=q)
        )

    if estado:
        parceiros_queryset = parceiros_queryset.filter(
            proposals__client_address__estado__iexact=estado
        )

    if cidade:
        parceiros_queryset = parceiros_queryset.filter(
            proposals__client_address__cidade__icontains=cidade
        )

    parceiros = list(
        parceiros_queryset.distinct().order_by('nome_fantasia', 'razao_social', 'id')[:100]
    )

    parceiros_ids = [partner.id for partner in parceiros]
    parceiros_com_cotacao_aberta = set(
        Proposal.objects.filter(
            client_address=endereco,
            partner_id__in=parceiros_ids,
            status='analise',
        ).values_list('partner_id', flat=True)
    )

    resultados = [
        {
            'id': partner.id,
            'nome': partner.nome_fantasia or partner.razao_social or f'Parceiro #{partner.id}',
            'razao_social': partner.razao_social or '',
            'cnpj_cpf': partner.cnpj_cpf or '',
            'status': partner.status or '',
            'ja_possui_cotacao_aberta': partner.id in parceiros_com_cotacao_aberta,
        }
        for partner in parceiros
    ]

    return JsonResponse({
        'endereco': {
            'id': endereco.id,
            'login_ixc': endereco.login_ixc or '',
            'bairro': endereco.bairro or '',
            'cidade': endereco.cidade or '',
            'estado': endereco.estado or '',
        },
        'cobertura': _montar_cobertura_parceiros_por_regiao(endereco),
        'resultados': resultados,
    })


def _obter_ou_criar_parceiro_do_endereco_lead(lead_endereco_item):
    lead_espelho_item = lead_endereco_item.leads_legados.order_by('id').first()
    if lead_espelho_item:
        partner_item, _ = _obter_ou_criar_parceiro_do_lead(lead_espelho_item)
        return partner_item, lead_espelho_item

    empresa = lead_endereco_item.empresa
    partner_item = None

    if empresa.cnpj_cpf:
        partner_item = Partner.objects.filter(cnpj_cpf=empresa.cnpj_cpf).order_by('-id').first()

    if not partner_item:
        filtro_nomes = Q()
        for nome in [empresa.nome_fantasia, empresa.razao_social]:
            nome_limpo = (nome or '').strip()
            if nome_limpo:
                filtro_nomes |= Q(nome_fantasia__iexact=nome_limpo) | Q(razao_social__iexact=nome_limpo)
        if filtro_nomes:
            partner_item = Partner.objects.filter(filtro_nomes).order_by('-id').first()

    if not partner_item and empresa.email:
        partner_item = Partner.objects.filter(email__iexact=empresa.email).order_by('-id').first()

    if not partner_item and empresa.telefone:
        partner_item = Partner.objects.filter(telefone=empresa.telefone).order_by('-id').first()

    if not partner_item:
        partner_item = Partner.objects.create(
            nome_fantasia=empresa.nome_fantasia or empresa.razao_social,
            razao_social=empresa.razao_social or empresa.nome_fantasia,
            cnpj_cpf=empresa.cnpj_cpf,
            contato_nome=empresa.contato_nome,
            email=empresa.email,
            telefone=empresa.telefone,
            status='ativo',
        )
    else:
        campos_atualizados = []
        if not partner_item.nome_fantasia and empresa.nome_fantasia:
            partner_item.nome_fantasia = empresa.nome_fantasia
            campos_atualizados.append('nome_fantasia')
        if not partner_item.razao_social and empresa.razao_social:
            partner_item.razao_social = empresa.razao_social
            campos_atualizados.append('razao_social')
        if not partner_item.cnpj_cpf and empresa.cnpj_cpf:
            partner_item.cnpj_cpf = empresa.cnpj_cpf
            campos_atualizados.append('cnpj_cpf')
        if not partner_item.contato_nome and empresa.contato_nome:
            partner_item.contato_nome = empresa.contato_nome
            campos_atualizados.append('contato_nome')
        if not partner_item.email and empresa.email:
            partner_item.email = empresa.email
            campos_atualizados.append('email')
        if not partner_item.telefone and empresa.telefone:
            partner_item.telefone = empresa.telefone
            campos_atualizados.append('telefone')
        if campos_atualizados:
            partner_item.save(update_fields=campos_atualizados)

    return partner_item, lead_espelho_item


@user_passes_test(grupo_LastMile_required)
@login_required
def endereco_lastmile_batch_proposal_create(request, endereco_pk):
    if request.method != 'POST':
        return redirect('enderecos_lastmile')

    endereco = get_object_or_404(
        Endereco.objects.select_related('cliente'),
        pk=endereco_pk,
        em_os_comercial_lastmile=True,
        os_atual_aberta=True,
    )

    partner_ids = request.POST.getlist('partner_ids')
    force_lead_partner_fallback = request.POST.get('force_lead_partner_fallback') == '1'
    lead_endereco_ids = [
        int(value) for value in request.POST.getlist('lead_endereco_ids')
        if value and str(value).isdigit()
    ]
    lead_endereco_id = request.POST.get('lead_endereco_id')
    if not lead_endereco_ids and lead_endereco_id and str(lead_endereco_id).isdigit():
        lead_endereco_ids = [int(lead_endereco_id)]
    redirect_url = (
        request.POST.get('next')
        or request.META.get('HTTP_REFERER')
        or reverse_lazy('enderecos_lastmile_cliente', kwargs={'pk': endereco.cliente_id})
    )

    if not lead_endereco_ids:
        messages.error(request, "Selecione pelo menos um endereço da prospecção antes de criar as cotações.")
        return redirect(redirect_url)

    lead_enderecos = list(
        LeadEndereco.objects.select_related('empresa')
        .filter(pk__in=lead_endereco_ids)
        .order_by('empresa__razao_social', 'cidade', 'bairro', 'endereco', 'id')
    )
    if not lead_enderecos:
        messages.error(request, "Nenhum endereço válido da prospecção foi selecionado.")
        return redirect(redirect_url)

    partner_ids_limpos = []
    for value in partner_ids:
        if value and str(value).isdigit():
            partner_ids_limpos.append(int(value))

    if not partner_ids_limpos and not force_lead_partner_fallback:
        messages.error(request, "Selecione pelo menos um parceiro para abrir a cotação.")
        return redirect(redirect_url)

    parceiros = list(
        Partner.objects.filter(id__in=partner_ids_limpos).order_by('nome_fantasia', 'razao_social', 'id')
    )
    if not parceiros and not force_lead_partner_fallback:
        messages.error(request, "Nenhum parceiro válido foi selecionado.")
        return redirect(redirect_url)

    parceiros_com_cotacao_aberta = set(
        Proposal.objects.filter(
            client_address=endereco,
            partner_id__in=[partner.id for partner in parceiros],
            status='analise',
        ).values_list('partner_id', flat=True)
    )

    proposal_type = ContentType.objects.get_for_model(Proposal)
    criadas = 0
    parceiros_ignorados = 0

    with transaction.atomic():
        if force_lead_partner_fallback:
            parceiros_processados = set()

            for lead_endereco_item in lead_enderecos:
                partner, lead_espelho_item = _obter_ou_criar_parceiro_do_endereco_lead(lead_endereco_item)
                if partner.id in parceiros_processados:
                    continue
                parceiros_processados.add(partner.id)

                if Proposal.objects.filter(
                    client_address=endereco,
                    partner=partner,
                    status='analise',
                ).exists():
                    parceiros_ignorados += 1
                    continue

                proposal = Proposal.objects.create(
                    partner=partner,
                    responsavel=request.user,
                    cliente=endereco.cliente,
                    client_address=endereco,
                    lead=lead_espelho_item,
                    lead_endereco=lead_endereco_item,
                )
                proposal.grupo_proposta_id = proposal.id
                proposal.codigo_proposta = Proposal.montar_codigo_proposta(proposal.id)
                proposal.save(update_fields=['grupo_proposta_id', 'codigo_proposta'])

                RegistroHistorico.objects.create(
                    tipo='sistema',
                    acao=(
                        "Cotação criada a partir da fila de endereços Lastmile.\n\n"
                        f"ID da proposta: #{proposal.codigo_exibicao}\n"
                        f"Parceiro: {partner}\n"
                        f"Prospecção: {lead_endereco_item.empresa}\n"
                        f"Endereço da prospecção: {lead_endereco_item}\n"
                        f"Cliente: {proposal.cliente or '--'}\n"
                        f"Unidade: {proposal.client_address or '--'}"
                    ),
                    usuario=request.user,
                    content_type=proposal_type,
                    object_id=proposal.id,
                )
                criadas += 1
        else:
            for partner in parceiros:
                if partner.id in parceiros_com_cotacao_aberta:
                    parceiros_ignorados += 1
                    continue

                for lead_endereco_item in lead_enderecos:
                    lead_espelho_item = lead_endereco_item.leads_legados.order_by('id').first()

                    proposal = Proposal.objects.create(
                        partner=partner,
                        responsavel=request.user,
                        cliente=endereco.cliente,
                        client_address=endereco,
                        lead=lead_espelho_item,
                        lead_endereco=lead_endereco_item,
                    )
                    proposal.grupo_proposta_id = proposal.id
                    proposal.codigo_proposta = Proposal.montar_codigo_proposta(proposal.id)
                    proposal.save(update_fields=['grupo_proposta_id', 'codigo_proposta'])

                    RegistroHistorico.objects.create(
                        tipo='sistema',
                        acao=(
                            "Cotação criada a partir da fila de endereços Lastmile.\n\n"
                            f"ID da proposta: #{proposal.codigo_exibicao}\n"
                            f"Parceiro: {partner}\n"
                            f"Prospecção: {lead_endereco_item.empresa}\n"
                            f"Endereço da prospecção: {lead_endereco_item}\n"
                            f"Cliente: {proposal.cliente or '--'}\n"
                            f"Unidade: {proposal.client_address or '--'}"
                        ),
                        usuario=request.user,
                        content_type=proposal_type,
                        object_id=proposal.id,
                    )
                    criadas += 1

    if criadas and parceiros_ignorados:
        messages.success(request, f"{criadas} cotação(ões) criada(s). {parceiros_ignorados} provedor(es) já tinham cotação em Em negociação para este endereço.")
    elif criadas:
        messages.success(request, f"{criadas} cotação(ões) criada(s) com sucesso para este endereço.")
    else:
        messages.info(request, "Nenhuma cotação nova foi criada porque os provedores selecionados já possuem cotação em Em negociação para este endereço.")

    return redirect(redirect_url)
