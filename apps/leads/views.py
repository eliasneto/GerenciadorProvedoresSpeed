from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from scripts.integracoes.Lastmile.APIGoogle_BuscaFornecedores import processar_planilha
import os
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.core.files.storage import FileSystemStorage

from .models import Lead
from .forms import LeadForm
from partners.models import Partner, Proposal
from partners.forms import ProposalForm
from clientes.models import Endereco
import re

# IMPORTAÇÃO DA TIMELINE (HISTÓRICO)
from core.models import IntegrationAudit, RegistroHistorico
from apps.core.integration_audit import dataframe_to_records, registrar_auditoria_integracao

from django.db.models import Q
from decimal import Decimal, InvalidOperation
import pandas as pd

# 1. Cria a regra de verificação
def grupo_LastMile_required(user):
    if not user.is_authenticated:
        return False
    # O Superuser (você) sempre passa. Os outros precisam estar no grupo.
    if user.groups.filter(name='LastMile').exists() or user.is_superuser:
        return True
    # Se não for do grupo, joga um Erro 403 (Acesso Negado)
    raise PermissionDenied


def _nomes_candidatos_lead(lead):
    nomes = []
    vistos = set()
    for valor in [lead.nome_fantasia, lead.razao_social]:
        valor_limpo = (valor or '').strip()
        chave = valor_limpo.lower()
        if valor_limpo and chave not in vistos:
            nomes.append(valor_limpo)
            vistos.add(chave)
    return nomes


def _buscar_parceiro_existente_para_lead(lead):
    if lead.cnpj_cpf:
        parceiro = Partner.objects.filter(cnpj_cpf=lead.cnpj_cpf).order_by('-id').first()
        if parceiro:
            return parceiro

    nomes = _nomes_candidatos_lead(lead)
    filtro_nomes = Q()
    for nome in nomes:
        filtro_nomes |= Q(nome_fantasia__iexact=nome) | Q(razao_social__iexact=nome)

    if filtro_nomes:
        parceiro = Partner.objects.filter(filtro_nomes).order_by('-id').first()
        if parceiro:
            return parceiro

    if lead.email:
        parceiro = Partner.objects.filter(email__iexact=lead.email).order_by('-id').first()
        if parceiro:
            return parceiro

    if lead.telefone:
        parceiro = Partner.objects.filter(telefone=lead.telefone).order_by('-id').first()
        if parceiro:
            return parceiro

    return None


def _atualizar_dados_parceiro_com_lead(partner, lead):
    campos_atualizados = []

    if not partner.nome_fantasia and lead.nome_fantasia:
        partner.nome_fantasia = lead.nome_fantasia
        campos_atualizados.append('nome_fantasia')
    if not partner.razao_social and lead.razao_social:
        partner.razao_social = lead.razao_social
        campos_atualizados.append('razao_social')
    if not partner.telefone and lead.telefone:
        partner.telefone = lead.telefone
        campos_atualizados.append('telefone')
    if not partner.contato_nome and lead.contato_nome:
        partner.contato_nome = lead.contato_nome
        campos_atualizados.append('contato_nome')
    if not partner.email and lead.email:
        partner.email = lead.email
        campos_atualizados.append('email')
    if not partner.cnpj_cpf and lead.cnpj_cpf:
        partner.cnpj_cpf = lead.cnpj_cpf
        campos_atualizados.append('cnpj_cpf')

    if campos_atualizados:
        partner.save(update_fields=campos_atualizados)

    return partner


def _obter_ou_criar_parceiro_do_lead(lead):
    partner_defaults = {
        'nome_fantasia': lead.nome_fantasia or lead.razao_social,
        'razao_social': lead.razao_social or lead.nome_fantasia,
        'telefone': lead.telefone,
        'contato_nome': lead.contato_nome,
        'email': lead.email,
        'status': 'ativo',
    }

    if lead.cnpj_cpf:
        partner, created = Partner.objects.get_or_create(
            cnpj_cpf=lead.cnpj_cpf,
            defaults=partner_defaults,
        )
    else:
        partner = _buscar_parceiro_existente_para_lead(lead)
        if partner:
            created = False
        else:
            partner = Partner.objects.create(**partner_defaults)
            created = True

    if not created:
        _atualizar_dados_parceiro_com_lead(partner, lead)

    return partner, created


def _converter_lead_em_parceiro_rapido(lead, enderecos, user, ticket_cliente=None, ticket_empresa=None, nome_proposta=None):
    """Cria ou reaproveita o parceiro e adiciona propostas sem remover o lead da cotacao."""
    with transaction.atomic():
        partner, created = _obter_ou_criar_parceiro_do_lead(lead)

        proposta_base = Proposal.objects.create(
            partner=partner,
            cliente=enderecos[0].cliente,
            client_address=enderecos[0],
            nome_proposta=nome_proposta,
            ticket_cliente=ticket_cliente,
            ticket_empresa=ticket_empresa,
        )
        proposta_base.grupo_proposta_id = proposta_base.id
        proposta_base.codigo_proposta = Proposal.montar_codigo_proposta(proposta_base.grupo_proposta_id)
        proposta_base.save(update_fields=['grupo_proposta_id', 'codigo_proposta'])

        proposal_type = ContentType.objects.get_for_model(Proposal)
        RegistroHistorico.objects.create(
            tipo='sistema',
            acao=(
                "Proposta criada a partir da cotacao.\n\n"
                f"ID da proposta: #{proposta_base.codigo_exibicao}\n"
                f"Cliente: {proposta_base.cliente or '--'}\n"
                f"Unidade: {proposta_base.client_address or '--'}"
            ),
            usuario=user,
            content_type=proposal_type,
            object_id=proposta_base.id
        )

        for endereco_extra in enderecos[1:]:
            clone = Proposal.objects.get(pk=proposta_base.pk)
            clone.pk = None
            clone.grupo_proposta_id = proposta_base.grupo_proposta_id
            clone.codigo_proposta = proposta_base.codigo_proposta
            clone.nome_proposta = proposta_base.nome_proposta
            clone.client_address = endereco_extra
            clone.cliente = endereco_extra.cliente
            clone.save()
            RegistroHistorico.objects.create(
                tipo='sistema',
                acao=(
                    "Proposta criada a partir da cotacao.\n\n"
                    f"ID da proposta: #{clone.codigo_exibicao}\n"
                    f"Cliente: {clone.cliente or '--'}\n"
                    f"Unidade: {clone.client_address or '--'}"
                ),
                usuario=user,
                content_type=proposal_type,
                object_id=clone.id
            )

        lead_type = ContentType.objects.get_for_model(Lead)
        partner_type = ContentType.objects.get_for_model(Partner)

        dados_vinculo = [f"Cliente Final: {enderecos[0].cliente}"]
        for endereco in enderecos:
            dados_vinculo.append(f"Unidade de Instalacao: {endereco}")

        mensagem_base = (
            f"Numero da proposta: #{proposta_base.codigo_exibicao}\n"
            f"{len(enderecos)} link(s) criado(s).\n\n"
            "VINCULO RELACIONAL:\n"
            + "\n".join(dados_vinculo)
        )

        RegistroHistorico.objects.create(
            tipo='sistema',
            acao=(
                ("Parceiro reaproveitado para nova abertura de proposta.\n\n" if not created else "Proposta rapida aberta a partir da cotacao.\n\n")
                + mensagem_base
            ),
            usuario=user,
            content_type=partner_type,
            object_id=partner.id
        )

        RegistroHistorico.objects.create(
            tipo='sistema',
            acao=(
                ("Nova proposta vinculada a parceiro existente.\n\n" if not created else "Proposta rapida aberta a partir da cotacao.\n\n")
                + mensagem_base
                + f"\n\nRegistro mantido na base de cotacao para acompanhamento. Parceiro vinculado: {partner}."
            ),
            usuario=user,
            content_type=lead_type,
            object_id=lead.id
        )

    return partner


def _parse_ticket_value(raw_value):
    if not raw_value:
        return None

    valor_limpo = raw_value.strip().replace('R$', '').replace(' ', '')
    if ',' in valor_limpo:
        valor_limpo = valor_limpo.replace('.', '').replace(',', '.')

    try:
        return Decimal(valor_limpo)
    except (InvalidOperation, AttributeError):
        return None


def _formatar_cep(valor):
    numeros = ''.join(ch for ch in str(valor or '') if ch.isdigit())
    if len(numeros) == 8:
        return f"{numeros[:5]}-{numeros[5:]}"
    return ''


def _parse_google_maps_address(endereco_completo, cidade_padrao='', estado_padrao='', bairro_padrao='', cep_padrao=''):
    texto = str(endereco_completo or '').strip()
    if not texto:
        return {
            'cep': _formatar_cep(cep_padrao),
            'endereco': '',
            'numero': '',
            'bairro': str(bairro_padrao or '').strip()[:100],
            'cidade': str(cidade_padrao or '').strip()[:100],
            'estado': str(estado_padrao or '').strip()[:2].upper(),
        }

    cep = _formatar_cep(cep_padrao)
    cep_match = pd.Series([texto]).str.extract(r'(\d{5}-?\d{3})', expand=False).iloc[0]
    if isinstance(cep_match, str) and cep_match:
        cep = _formatar_cep(cep_match)
        texto = texto.replace(cep_match, '').strip(' ,')

    estado = str(estado_padrao or '').strip()[:2].upper()
    estado_match = re.search(r'(?:^|,|\s-\s)([A-Z]{2})$', texto)
    if estado_match:
        estado = estado_match.group(1).upper()
        texto = re.sub(r'(?:^|,|\s-\s)[A-Z]{2}$', '', texto).strip(' ,-_')

    partes_hifen = [parte.strip(' ,') for parte in texto.split(' - ') if parte.strip(' ,')]
    trecho_logradouro = partes_hifen[0] if partes_hifen else texto
    trecho_localizacao = ' - '.join(partes_hifen[1:]).strip(' ,') if len(partes_hifen) > 1 else ''

    endereco = trecho_logradouro
    numero = ''
    match_numero = re.match(r'^(?P<endereco>.*?)(?:,\s*(?P<numero>\d+[A-Za-z0-9./-]*))?$', trecho_logradouro)
    if match_numero:
        endereco = (match_numero.group('endereco') or '').strip(' ,')
        numero = (match_numero.group('numero') or '').strip(' ,')

    bairro = str(bairro_padrao or '').strip()
    cidade = str(cidade_padrao or '').strip()

    if trecho_localizacao:
        tokens_localizacao = [token.strip(' ,') for token in trecho_localizacao.split(',') if token.strip(' ,')]
        if len(tokens_localizacao) >= 2:
            cidade = tokens_localizacao[-1]
            bairro = ', '.join(tokens_localizacao[:-1])
        elif tokens_localizacao:
            cidade = tokens_localizacao[0]
    else:
        tokens = [token.strip(' ,') for token in texto.split(',') if token.strip(' ,')]
        if len(tokens) >= 4 and not numero:
            endereco = tokens[0]
            if re.fullmatch(r'\d+[A-Za-z0-9./-]*', tokens[1]):
                numero = tokens[1]
            bairro = tokens[-2]
            cidade = tokens[-1]
        elif len(tokens) >= 3:
            bairro = tokens[-2]
            cidade = tokens[-1]
        elif len(tokens) == 2 and not cidade:
            endereco = endereco or tokens[0]
            cidade = tokens[1]

    return {
        'cep': cep[:20],
        'endereco': endereco[:255],
        'numero': numero[:20],
        'bairro': bairro[:100],
        'cidade': cidade[:100],
        'estado': estado[:2],
    }

@user_passes_test(grupo_LastMile_required)
@login_required
def lead_list(request):
    """Lista todos os leads com paginação e filtros"""
    # 1. Pega todos os leads
    leads_list = Lead.objects.all().order_by('-id')

    # 2. Captura os parâmetros digitados nos filtros (se houver)
    busca_empresa = request.GET.get('empresa', '')
    busca_cidade = request.GET.get('cidade', '')
    busca_estado = request.GET.get('estado', '')
    busca_bairro = request.GET.get('bairro', '')
    busca_cep = request.GET.get('cep', '')

    # 3. Aplica os filtros na lista
    if busca_empresa:
        # Busca tanto no nome fantasia quanto na razão social
        leads_list = leads_list.filter(
            Q(nome_fantasia__icontains=busca_empresa) | 
            Q(razao_social__icontains=busca_empresa)
        )
    
    if busca_estado:
        leads_list = leads_list.filter(estado__iexact=busca_estado)

    if busca_cep:
        leads_list = leads_list.filter(Q(cep__icontains=busca_cep) | Q(endereco__icontains=busca_cep))
    elif busca_cidade:
        leads_list = leads_list.filter(cidade__icontains=busca_cidade)

    if busca_bairro:
        leads_list = leads_list.filter(Q(bairro__icontains=busca_bairro) | Q(endereco__icontains=busca_bairro))

    # 4. Paginação (10 por página)
    paginator = Paginator(leads_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    for lead in page_obj.object_list:
        partner_relacionado = _buscar_parceiro_existente_para_lead(lead)
        lead.partner_relacionado = partner_relacionado
        if partner_relacionado:
            propostas_em_negociacao = partner_relacionado.proposals.filter(status='analise')
            codigos_unicos = {
                proposal.codigo_proposta or f"proposal-{proposal.pk}"
                for proposal in propostas_em_negociacao
            }
            lead.total_propostas_relacionadas = len(codigos_unicos)
        else:
            lead.total_propostas_relacionadas = 0
    
    # 5. Manda as variáveis de volta para a tela (para os campos não ficarem em branco após filtrar)
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
            form.save()
            messages.success(request, "Novo lead cadastrado com sucesso!")
            return redirect('lead_list')
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
            form.save()
            messages.success(request, "Dados do lead atualizados!")
            return redirect('lead_list')
    else:
        form = LeadForm(instance=lead)
        
    return render(request, 'leads/lead_form.html', {
        'form': form,
        'lead': lead, # Injetamos o lead para a tela saber o ID
        'historico': historico, # Injetamos a lista de eventos
        'title': 'Editar Lead'
    })

@user_passes_test(grupo_LastMile_required)
@login_required
def lead_add_historico(request, pk):
    """Mini-view que recebe o POST do comentário/anexo e salva no banco"""
    lead = get_object_or_404(Lead, pk=pk)
    
    if request.method == 'POST':
        descricao_texto = request.POST.get('descricao')
        arquivo = request.FILES.get('arquivo') 
        
        if descricao_texto or arquivo:
            tipo = 'anexo' if arquivo else 'comentario'
            
            RegistroHistorico.objects.create(
                tipo=tipo,
                acao=descricao_texto,
                arquivo=arquivo,
                usuario=request.user,
                content_type=ContentType.objects.get_for_model(Lead),
                object_id=lead.id
            )
            messages.success(request, "Registro adicionado à linha do tempo do lead!")
            
    return redirect('lead_update', pk=pk)

@user_passes_test(grupo_LastMile_required)
@login_required
def lead_delete(request, pk):
    """Remoção de lead da base"""
    lead = get_object_or_404(Lead, pk=pk)
    if request.method == 'POST':
        lead.delete()
        messages.warning(request, "Lead removido da base de cotação.")
        return redirect('lead_list')
    return redirect('lead_list')

@user_passes_test(grupo_LastMile_required)
@login_required
def update_lead_status(request, pk):
    """Valida a intenção e redireciona para a conversão ou atualiza o status."""
    if request.method == 'POST':
        lead = get_object_or_404(Lead, pk=pk)
        novo_status = request.POST.get('status')
        
        # Guarda o status atual antes de salvar a mudança para o relatório
        status_antigo = lead.status 
        
        if novo_status == 'andamento':
            # Evita duplicidade somente quando houver documento informado
            from partners.models import Partner
            if lead.cnpj_cpf and Partner.objects.filter(cnpj_cpf=lead.cnpj_cpf).exists():
                messages.error(request, f"O CNPJ {lead.cnpj_cpf} já é um parceiro ativo.")
                return redirect('lead_list')

            # REDIRECIONA PARA A TELA DE CONVERSÃO
            return redirect('lead_convert', pk=lead.pk)
            
        elif novo_status == 'inviavel':
            observacao = request.POST.get('observacao')
            arquivo = request.FILES.get('arquivo')
            
            lead.status = 'inviavel'
            lead.save()

            if observacao:
                from core.models import RegistroHistorico
                from django.contrib.contenttypes.models import ContentType
                
                tipo_hist = 'anexo' if arquivo else 'sistema'
                texto_historico = f"❌ NEGOCIAÇÃO ENCERRADA (INVIÁVEL)\n\nMotivo / Observação:\n{observacao}"
                
                RegistroHistorico.objects.create(
                    tipo=tipo_hist,
                    acao=texto_historico,
                    arquivo=arquivo,
                    usuario=request.user,
                    content_type=ContentType.objects.get_for_model(Lead),
                    object_id=lead.id
                )
            
            messages.warning(request, f"O Lead '{lead.nome_fantasia or lead.razao_social}' foi marcado como Inviável.")
            return redirect('lead_list')
            
        elif novo_status == 'negociacao':
            lead.status = 'negociacao'
            lead.save()

            # Só gera o log se realmente houve uma mudança de status
            if status_antigo != 'negociacao':
                from core.models import RegistroHistorico
                from django.contrib.contenttypes.models import ContentType
                
                status_dict = dict(Lead.STATUS_CHOICES)
                nome_antigo = status_dict.get(status_antigo, status_antigo).upper()
                
                RegistroHistorico.objects.create(
                    tipo='sistema',
                    acao=f"🔄 Status da cotação alterado de [{nome_antigo}] para [EM NEGOCIAÇÃO].",
                    usuario=request.user,
                    content_type=ContentType.objects.get_for_model(Lead),
                    object_id=lead.id
                )
            
            messages.info(request, "Lead movido para Em Negociação.")
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
    ticket_cliente = _parse_ticket_value(request.POST.get('ticket_cliente'))
    ticket_empresa = _parse_ticket_value(request.POST.get('ticket_empresa'))

    if not cliente_id:
        messages.error(request, "Selecione o cliente final para abrir a cotação.")
        return redirect('lead_list')

    if not enderecos_ids:
        messages.error(request, "Selecione pelo menos um login/unidade para abrir a cotação.")
        return redirect('lead_list')

    if not nome_proposta:
        messages.error(request, "Informe o nome da cotação para continuar.")
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

    partner = _converter_lead_em_parceiro_rapido(
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
    
    partner_draft = Partner(
        nome_fantasia=lead.nome_fantasia or lead.razao_social,
        razao_social=lead.razao_social or lead.nome_fantasia,
        cnpj_cpf=lead.cnpj_cpf,
        telefone=lead.telefone
    )

    if request.method == 'POST':
        form = ProposalForm(request.POST)
        enderecos_ids = request.POST.getlist('enderecos_selecionados')

        if form.is_valid():
            if not enderecos_ids:
                messages.error(request, "Selecione pelo menos uma unidade de instalação.")
                return render(request, 'partners/proposal_form.html', {'form': form, 'partner': partner_draft, 'is_lead_conversion': True})

            lista_ids_historico = list(enderecos_ids)

            # SALVAMENTO EM CASCATA
            partner_draft, partner_created = _obter_ou_criar_parceiro_do_lead(lead)

            proposta_base = form.save(commit=False)
            primeiro_endereco_id = enderecos_ids.pop(0)
            from clientes.models import Endereco 
            primeiro_endereco = get_object_or_404(Endereco, pk=primeiro_endereco_id)
            
            proposta_base.partner = partner_draft
            proposta_base.client_address = primeiro_endereco
            proposta_base.cliente = primeiro_endereco.cliente
            proposta_base.save() # Cria Proposta Principal
            proposta_base.grupo_proposta_id = proposta_base.id
            proposta_base.codigo_proposta = Proposal.montar_codigo_proposta(proposta_base.grupo_proposta_id)
            proposta_base.save(update_fields=['grupo_proposta_id', 'codigo_proposta'])

            proposal_type = ContentType.objects.get_for_model(Proposal)
            RegistroHistorico.objects.create(
                tipo='sistema',
                acao=(
                    "Proposta criada na conversao do lead.\n\n"
                    f"ID da proposta: #{proposta_base.codigo_exibicao}\n"
                    f"Cliente: {proposta_base.cliente or '--'}\n"
                    f"Unidade: {proposta_base.client_address or '--'}"
                ),
                usuario=request.user,
                content_type=proposal_type,
                object_id=proposta_base.id
            )

            for end_id in enderecos_ids:
                endereco_extra = get_object_or_404(Endereco, pk=end_id)
                clone = Proposal.objects.get(pk=proposta_base.pk)
                clone.pk = None
                clone.grupo_proposta_id = proposta_base.grupo_proposta_id
                clone.codigo_proposta = proposta_base.codigo_proposta
                clone.nome_proposta = proposta_base.nome_proposta
                clone.client_address = endereco_extra
                clone.cliente = endereco_extra.cliente
                clone.save()
                RegistroHistorico.objects.create(
                    tipo='sistema',
                    acao=(
                        "Proposta criada na conversao do lead.\n\n"
                        f"ID da proposta: #{clone.codigo_exibicao}\n"
                        f"Cliente: {clone.cliente or '--'}\n"
                        f"Unidade: {clone.client_address or '--'}"
                    ),
                    usuario=request.user,
                    content_type=proposal_type,
                    object_id=clone.id
                )

            # --- TRANSFERÊNCIA DO HISTÓRICO SPEED ---
            lead_type = ContentType.objects.get_for_model(Lead)
            partner_type = ContentType.objects.get_for_model(Partner)
            
            historicos = RegistroHistorico.objects.filter(content_type=lead_type, object_id=lead.id)
            historicos.update(content_type=partner_type, object_id=partner_draft.id)
            
            # --- SNAPSHOT INTELIGENTE COM VÍNCULO RELACIONAL ---
            dados_vinculo = []
            dados_tecnicos = []
            dados_financeiros = []
            outros_dados = []

            enderecos_objs = Endereco.objects.filter(id__in=lista_ids_historico)
            if enderecos_objs.exists():
                cliente_alvo = enderecos_objs.first().cliente
                dados_vinculo.append(f"• Cliente Final: {cliente_alvo}")
                for end in enderecos_objs:
                    dados_vinculo.append(f"• Unidade de Instalação: {end}")

            for campo, valor in form.cleaned_data.items():
                if valor and campo not in ['enderecos_selecionados', 'partner', 'cliente', 'client_address']:
                    nome_campo = campo.replace('_', ' ').title()
                    
                    if any(palavra in campo for palavra in ['valor', 'taxa', 'custo', 'pago']):
                        valor_str = f"R$ {valor}"
                    elif campo in ['vigencia', 'tempo_contrato']:
                        valor_str = f"{valor} Meses"
                    else:
                        valor_str = str(valor)

                    linha = f"• {nome_campo}: {valor_str}"

                    if any(palavra in campo for palavra in ['valor', 'taxa', 'custo', 'pago', 'vigencia', 'email']):
                        dados_financeiros.append(linha)
                    elif any(palavra in campo for palavra in ['velocidade', 'tecnologia', 'contato', 'telefone']):
                        dados_tecnicos.append(linha)
                    else:
                        outros_dados.append(linha)
            
            qtd_links = len(lista_ids_historico)
            texto_snapshot = f"🚀 Lead convertido para Parceiro Ativo com {qtd_links} link(s) configurado(s).\n\n"
            
            if dados_vinculo:
                texto_snapshot += "🔗 VÍNCULO RELACIONAL:\n" + "\n".join(dados_vinculo) + "\n\n"
            if dados_tecnicos:
                texto_snapshot += "⚡ PARÂMETROS DE CONECTIVIDADE:\n" + "\n".join(dados_tecnicos) + "\n\n"
            if dados_financeiros:
                texto_snapshot += "💰 COMERCIAL E FATURAMENTO:\n" + "\n".join(dados_financeiros) + "\n\n"
            if outros_dados:
                texto_snapshot += "📋 OUTRAS INFORMAÇÕES:\n" + "\n".join(outros_dados)

            RegistroHistorico.objects.create(
                tipo='sistema',
                acao=texto_snapshot.strip(),
                usuario=request.user,
                content_type=partner_type,
                object_id=partner_draft.id
            )

            lead.delete() 
            
            if partner_created:
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

        temp_dir = os.path.join(settings.BASE_DIR, 'media', 'temp_google')
        os.makedirs(temp_dir, exist_ok=True)

        fs = FileSystemStorage(location=temp_dir)
        filename = fs.save(planilha.name, planilha)
        caminho_entrada = os.path.join(temp_dir, filename)
        
        caminho_saida = os.path.join(temp_dir, f"resultado_{filename}")

        try:
            try:
                df_entrada = pd.read_excel(caminho_entrada)
            except Exception:
                df_entrada = pd.DataFrame()

            itens_importados = dataframe_to_records(df_entrada) if not df_entrada.empty else []
            registrar_auditoria_integracao(
                integration='buscar_fornecedores',
                action='importacao_planilha',
                usuario=request.user,
                arquivo_nome=planilha.name,
                total_registros=len(itens_importados),
                detalhes={'colunas': list(df_entrada.columns)},
                itens=itens_importados,
            )

            dados_encontrados = processar_planilha(caminho_entrada, caminho_saida)
            itens_execucao = []
            
            # 5. SALVANDO NO BANCO DE DADOS
            if dados_encontrados:
                for index, item in enumerate(dados_encontrados, start=2):
                    # 1. Tratamento e Normalização Básica
                    nome_fantasia_str = str(item.get('Nome Fantasia') or item.get('Razão Social') or 'Lead Sem Nome').strip()[:200]
                    razao_social_str = str(item.get('Razão Social') or nome_fantasia_str).strip()[:200]
                    
                    site_url = str(item.get('Site', '')).strip()
                    if site_url == 'Não informado' or pd.isna(item.get('Site')): site_url = ''

                    email_str = str(item.get('Email', '')).strip()
                    if email_str == 'Não informado' or pd.isna(item.get('Email')): email_str = ''

                    tel_str = str(item.get('WhatsApp') or item.get('Telefone', '')).strip()
                    if tel_str == 'Não informado' or pd.isna(tel_str): tel_str = ''

                    end_str = str(item.get('Endereço Completo', '')).strip()
                    if end_str == 'Não informado' or pd.isna(item.get('Endereço Completo')): end_str = ''

                    # 2. Captura dos Novos Dados da IA
                    endereco_parseado = _parse_google_maps_address(
                        end_str,
                        cidade_padrao=str(item.get('Cidade', '')).strip(),
                        estado_padrao=str(item.get('Estado', '')).strip(),
                        bairro_padrao=str(item.get('Bairro', '')).strip(),
                        cep_padrao=str(item.get('CEP', '')).strip(),
                    )
                    fonte_str = str(item.get('Fonte', '')).strip()[:100]
                    confianca_str = str(item.get('Confiança', '')).strip()[:50]
                    insta_user = str(item.get('Instagram Username', '')).strip()[:100]
                    insta_url = str(item.get('Instagram URL', '')).strip()[:255]
                    bio = str(item.get('Bio Instagram', '')).strip()
                    obs = str(item.get('Observação', '')).strip()

                    # 3. O get_or_create com as colunas novas
                    Lead.objects.get_or_create(
                        nome_fantasia=nome_fantasia_str, 
                        cidade=endereco_parseado['cidade'],
                        estado=endereco_parseado['estado'],
                        defaults={
                            'razao_social': razao_social_str,
                            'telefone': tel_str[:20],
                            'site': site_url[:200],
                            'cep': endereco_parseado['cep'],
                            'endereco': endereco_parseado['endereco'],
                            'numero': endereco_parseado['numero'],
                            'bairro': endereco_parseado['bairro'],
                            'cnpj_cpf': str(item.get('CNPJ', '')).strip()[:20], 
                            'email': email_str[:254],
                            'status': 'novo',
                            # 🚀 Salvando os dados nas colunas novas:
                            'fonte': fonte_str,
                            'confianca': confianca_str,
                            'instagram_username': insta_user,
                            'instagram_url': insta_url,
                            'bio_instagram': bio,
                            'observacao_ia': obs
                        }
                    )
                    itens_execucao.append(
                        {
                            'linha_numero': index,
                            'status': 'sucesso',
                            'mensagem': 'Fornecedor processado com sucesso.',
                            'dados_json': item,
                        }
                    )

            registrar_auditoria_integracao(
                integration='buscar_fornecedores',
                action='execucao_integracao',
                usuario=request.user,
                arquivo_nome=planilha.name,
                total_registros=len(dados_encontrados or []),
                total_sucessos=len(dados_encontrados or []),
                total_erros=0,
                detalhes={
                    'arquivo_saida': os.path.basename(caminho_saida),
                    'colunas_entrada': list(df_entrada.columns),
                },
                itens=itens_execucao,
            )

            if os.path.exists(caminho_saida):
                with open(caminho_saida, 'rb') as f:
                    response = HttpResponse(
                        f.read(), 
                        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )
                    response['Content-Disposition'] = f'attachment; filename="Resultado_Fornecedores.xlsx"'
                    
                    os.remove(caminho_entrada)
                    os.remove(caminho_saida)
                    
                    return response
            else:
                return JsonResponse({'erro': 'Falha ao gerar o arquivo de saída.'}, status=500)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'erro': str(e)}, status=500)
            
    return render(request, 'leads/integracoes.html')

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
