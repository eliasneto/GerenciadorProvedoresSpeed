"""Camada de servicos do app leads.

Concentra a regra de negocio hoje misturada nas views: casamento e
sincronizacao entre o lead legado e os modelos estruturados
(LeadEmpresa/LeadEndereco), conversao de lead em parceiro/proposta,
transicoes de status, normalizacao de dados de planilha e as consultas de
busca/filtro usadas pelas telas de listagem. As views ficam responsaveis
apenas por HTTP: validar a requisicao, chamar o servico e devolver
mensagens/redirects (PO-011, ADR-005; mesmo padrao do apps/backoffice/services.py
criado na PO-023).
"""
import datetime
import math
import os
import re
import traceback
from decimal import Decimal, InvalidOperation

import pandas as pd
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.clientes.models import Endereco
from apps.escolas.models import (
    Campo, CampoValor, CotacaoParceiro, Escola, MapaCalor, RedeExterna, RedeInterna, Setor, SetorEscopo, SetorStatus,
)
from apps.core.integration_audit import dataframe_to_records, registrar_auditoria_integracao
from apps.core.models import RegistroHistorico
from apps.partners.models import Partner, Proposal
from apps.integracoes.google.APIGoogle_BuscaFornecedores import processar_planilha

from .models import AcessoSetor, LEAD_STATUS_CHOICES, Lead, LeadEmpresa, LeadEndereco


class PlanilhaLeadsError(Exception):
    """Erro ao processar a planilha de busca de fornecedores (Google)."""


# ---------------------------------------------------------------------------
# Casamento e sincronizacao entre Lead e Partner
# ---------------------------------------------------------------------------

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


def buscar_parceiro_existente_para_lead(lead):
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


def obter_ou_criar_parceiro_do_lead(lead):
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
        partner = buscar_parceiro_existente_para_lead(lead)
        if partner:
            created = False
        else:
            partner = Partner.objects.create(**partner_defaults)
            created = True

    if not created:
        _atualizar_dados_parceiro_com_lead(partner, lead)

    return partner, created


def converter_lead_em_parceiro_rapido(lead, enderecos, user, ticket_cliente=None, ticket_empresa=None, nome_proposta=None):
    """Cria ou reaproveita o parceiro e adiciona propostas sem remover o lead da cotacao."""
    with transaction.atomic():
        partner, created = obter_ou_criar_parceiro_do_lead(lead)

        proposta_base = Proposal.objects.create(
            partner=partner,
            responsavel=user,
            cliente=enderecos[0].cliente,
            client_address=enderecos[0],
            lead=lead,
            lead_endereco=lead.endereco_estruturado,
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
            clone.lead = proposta_base.lead
            clone.lead_endereco = proposta_base.lead_endereco
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


# ---------------------------------------------------------------------------
# Transicoes de status do lead
# ---------------------------------------------------------------------------

def lead_possui_parceiro_com_mesmo_documento(lead):
    return bool(lead.cnpj_cpf) and Partner.objects.filter(cnpj_cpf=lead.cnpj_cpf).exists()


def marcar_lead_inviavel(lead, observacao, arquivo, usuario):
    lead.status = 'inviavel'
    lead.save()

    if observacao:
        tipo_hist = 'anexo' if arquivo else 'sistema'
        texto_historico = f"❌ NEGOCIAÇÃO ENCERRADA (INVIÁVEL)\n\nMotivo / Observação:\n{observacao}"

        RegistroHistorico.objects.create(
            tipo=tipo_hist,
            acao=texto_historico,
            arquivo=arquivo,
            usuario=usuario,
            content_type=ContentType.objects.get_for_model(Lead),
            object_id=lead.id
        )


def mover_lead_para_negociacao(lead, usuario):
    status_antigo = lead.status
    lead.status = 'negociacao'
    lead.save()

    # Só gera o log se realmente houve uma mudança de status
    if status_antigo != 'negociacao':
        status_dict = dict(LEAD_STATUS_CHOICES)
        nome_antigo = status_dict.get(status_antigo, status_antigo).upper()

        RegistroHistorico.objects.create(
            tipo='sistema',
            acao=f"🔄 Status da cotação alterado de [{nome_antigo}] para [EM NEGOCIAÇÃO].",
            usuario=usuario,
            content_type=ContentType.objects.get_for_model(Lead),
            object_id=lead.id
        )


def adicionar_historico_lead(lead, descricao, arquivo, usuario):
    """Cria o registro de historico do lead. Devolve False quando nao ha o que gravar."""
    if not (descricao or arquivo):
        return False

    tipo = 'anexo' if arquivo else 'comentario'
    RegistroHistorico.objects.create(
        tipo=tipo,
        acao=descricao,
        arquivo=arquivo,
        usuario=usuario,
        content_type=ContentType.objects.get_for_model(Lead),
        object_id=lead.id
    )
    return True


# ---------------------------------------------------------------------------
# Conversao oficial do lead em parceiro (tela de conversao)
# ---------------------------------------------------------------------------

def montar_rascunho_parceiro_do_lead(lead):
    """Instancia (sem salvar) um Partner com os dados do lead, para preview na tela."""
    return Partner(
        nome_fantasia=lead.nome_fantasia or lead.razao_social,
        razao_social=lead.razao_social or lead.nome_fantasia,
        cnpj_cpf=lead.cnpj_cpf,
        telefone=lead.telefone
    )


def converter_lead_em_parceiro(lead, form, enderecos_ids, usuario):
    """Executa a conversao oficial: salva parceiro/proposta(s), transfere o
    historico do lead para o parceiro e remove o lead da base de cotacao.

    `form` e um ProposalForm ja validado. `enderecos_ids` e a lista (nao
    vazia) de ids de Endereco selecionados na tela.

    Devolve {'partner': Partner, 'qtd_links': int, 'partner_created': bool}.
    """
    lista_ids_historico = list(enderecos_ids)
    ids_restantes = list(enderecos_ids)

    # SALVAMENTO EM CASCATA
    partner_draft, partner_created = obter_ou_criar_parceiro_do_lead(lead)

    proposta_base = form.save(commit=False)
    primeiro_endereco_id = ids_restantes.pop(0)
    primeiro_endereco = get_object_or_404(Endereco, pk=primeiro_endereco_id)

    proposta_base.partner = partner_draft
    proposta_base.client_address = primeiro_endereco
    proposta_base.cliente = primeiro_endereco.cliente
    proposta_base.save()  # Cria Proposta Principal
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
        usuario=usuario,
        content_type=proposal_type,
        object_id=proposta_base.id
    )

    for end_id in ids_restantes:
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
            usuario=usuario,
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
        usuario=usuario,
        content_type=partner_type,
        object_id=partner_draft.id
    )

    lead.delete()

    return {
        'partner': partner_draft,
        'qtd_links': qtd_links,
        'partner_created': partner_created,
    }


# ---------------------------------------------------------------------------
# Normalizacao de dados (parsing de planilha / endereco do Google Maps)
# ---------------------------------------------------------------------------

def parse_ticket_value(raw_value):
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


def parse_google_maps_address(endereco_completo, cidade_padrao='', estado_padrao='', bairro_padrao='', cep_padrao=''):
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


def _normalizar_texto_lead(valor):
    return str(valor or '').strip()


def _lead_tem_dados_endereco(lead):
    return any([
        _normalizar_texto_lead(lead.cep),
        _normalizar_texto_lead(lead.endereco),
        _normalizar_texto_lead(lead.numero),
        _normalizar_texto_lead(lead.bairro),
        _normalizar_texto_lead(lead.cidade),
        _normalizar_texto_lead(lead.estado),
    ])


def sync_lead_to_structured_models(lead):
    """Espelha o lead legado nos modelos estruturados (LeadEmpresa/LeadEndereco)."""
    empresa = lead.empresa_estruturada

    if not empresa:
        cnpj_cpf = _normalizar_texto_lead(lead.cnpj_cpf)
        razao_social = _normalizar_texto_lead(lead.razao_social)
        if cnpj_cpf:
            empresa = LeadEmpresa.objects.filter(cnpj_cpf__iexact=cnpj_cpf).order_by('id').first()
        elif razao_social:
            empresa = LeadEmpresa.objects.filter(razao_social__iexact=razao_social).order_by('id').first()

    if not empresa:
        empresa = LeadEmpresa.objects.create()

    empresa.razao_social = lead.razao_social
    empresa.cnpj_cpf = lead.cnpj_cpf
    empresa.nome_fantasia = lead.nome_fantasia
    empresa.site = lead.site
    empresa.contato_nome = lead.contato_nome
    empresa.email = lead.email
    empresa.telefone = lead.telefone
    empresa.fonte = lead.fonte
    empresa.confianca = lead.confianca
    empresa.instagram_username = lead.instagram_username
    empresa.instagram_url = lead.instagram_url
    empresa.bio_instagram = lead.bio_instagram
    empresa.observacao_ia = lead.observacao_ia
    empresa.status = lead.status or 'novo'
    empresa.save()

    endereco = None
    if _lead_tem_dados_endereco(lead):
        endereco_existente = lead.endereco_estruturado
        pode_reaproveitar_existente = bool(
            endereco_existente
            and endereco_existente.empresa_id == empresa.id
            and endereco_existente.leads_legados.exclude(pk=lead.pk).count() == 0
        )

        if pode_reaproveitar_existente:
            endereco = endereco_existente
        else:
            endereco = LeadEndereco.objects.filter(
                empresa=empresa,
                endereco__iexact=_normalizar_texto_lead(lead.endereco),
                numero__iexact=_normalizar_texto_lead(lead.numero),
                bairro__iexact=_normalizar_texto_lead(lead.bairro),
                cidade__iexact=_normalizar_texto_lead(lead.cidade),
                estado__iexact=_normalizar_texto_lead(lead.estado),
                cep__iexact=_normalizar_texto_lead(lead.cep),
            ).order_by('id').first()

        if not endereco:
            endereco = LeadEndereco(empresa=empresa)

        endereco.empresa = empresa
        endereco.cep = lead.cep
        endereco.endereco = lead.endereco
        endereco.numero = lead.numero
        endereco.bairro = lead.bairro
        endereco.cidade = lead.cidade
        endereco.estado = lead.estado
        endereco.save()

    lead.empresa_estruturada = empresa
    lead.endereco_estruturado = endereco
    lead.save(update_fields=['empresa_estruturada', 'endereco_estruturado'])

    return empresa, endereco


def criar_ou_atualizar_lead_espelho_empresa_endereco(empresa, endereco):
    """Mantem o lead legado (espelho) sincronizado quando a empresa/endereco
    estruturado e criado ou editado diretamente."""
    lead = endereco.leads_legados.order_by('id').first()
    if not lead:
        lead = Lead(
            empresa_estruturada=empresa,
            endereco_estruturado=endereco,
        )

    lead.razao_social = empresa.razao_social
    lead.cnpj_cpf = empresa.cnpj_cpf
    lead.nome_fantasia = empresa.nome_fantasia
    lead.site = empresa.site
    lead.contato_nome = empresa.contato_nome
    lead.email = empresa.email
    lead.telefone = empresa.telefone
    lead.fonte = empresa.fonte
    lead.confianca = empresa.confianca
    lead.instagram_username = empresa.instagram_username
    lead.instagram_url = empresa.instagram_url
    lead.bio_instagram = empresa.bio_instagram
    lead.observacao_ia = empresa.observacao_ia
    lead.status = empresa.status or 'novo'
    lead.cep = endereco.cep
    lead.endereco = endereco.endereco
    lead.numero = endereco.numero
    lead.bairro = endereco.bairro
    lead.cidade = endereco.cidade
    lead.estado = endereco.estado
    lead.empresa_estruturada = empresa
    lead.endereco_estruturado = endereco
    lead.save()
    return lead


# ---------------------------------------------------------------------------
# Importacao da planilha de busca de fornecedores (Google Maps)
# ---------------------------------------------------------------------------

def processar_planilha_leads(planilha, usuario):
    """Processa a planilha de fornecedores encontrados via Google Maps,
    cria/atualiza os Leads correspondentes e devolve o relatorio gerado.

    Retorna (conteudo_bytes, filename) em caso de sucesso. Levanta
    PlanilhaLeadsError com a mensagem de erro em caso de falha.
    """
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
            usuario=usuario,
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
                endereco_parseado = parse_google_maps_address(
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
            usuario=usuario,
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
                conteudo = f.read()

            os.remove(caminho_entrada)
            os.remove(caminho_saida)

            return conteudo, 'Resultado_Fornecedores.xlsx'

        raise PlanilhaLeadsError('Falha ao gerar o arquivo de saída.')

    except PlanilhaLeadsError:
        raise
    except Exception as e:
        traceback.print_exc()
        raise PlanilhaLeadsError(str(e)) from e


# ---------------------------------------------------------------------------
# Cobertura regional de parceiros (usado pela busca de parceiros do Lastmile)
# ---------------------------------------------------------------------------

def montar_cobertura_parceiros_por_regiao(endereco):
    estado = (endereco.estado or '').strip().upper()
    cidade = (endereco.cidade or '').strip()
    bairro = (endereco.bairro or '').strip()

    partners = Partner.objects.all()

    if estado:
        parceiros_estado = partners.filter(
            proposals__client_address__estado__iexact=estado
        ).distinct()
    else:
        parceiros_estado = Partner.objects.none()

    if cidade:
        filtros_cidade = Q(proposals__client_address__cidade__iexact=cidade)
        if estado:
            filtros_cidade &= Q(proposals__client_address__estado__iexact=estado)
        parceiros_cidade = partners.filter(filtros_cidade).distinct()
    else:
        parceiros_cidade = Partner.objects.none()

    if bairro:
        filtros_bairro = Q(proposals__client_address__bairro__iexact=bairro)
        if cidade:
            filtros_bairro &= Q(proposals__client_address__cidade__iexact=cidade)
        if estado:
            filtros_bairro &= Q(proposals__client_address__estado__iexact=estado)
        parceiros_bairro = partners.filter(filtros_bairro).distinct()
    else:
        parceiros_bairro = Partner.objects.none()

    return {
        'bairro': {
            'nome': bairro or '',
            'count': parceiros_bairro.count() if bairro else None,
        },
        'cidade': {
            'nome': cidade or '',
            'count': parceiros_cidade.count() if cidade else None,
        },
        'estado': {
            'nome': estado or '',
            'count': parceiros_estado.count() if estado else None,
        },
    }


# ---------------------------------------------------------------------------
# Consultas de busca/filtro das telas de listagem
# ---------------------------------------------------------------------------

def filtrar_leads(busca_empresa='', busca_cidade='', busca_estado='', busca_bairro='', busca_cep=''):
    leads_list = Lead.objects.all().order_by('-id')

    if busca_empresa:
        leads_list = leads_list.filter(
            Q(nome_fantasia__icontains=busca_empresa) |
            Q(razao_social__icontains=busca_empresa)
        )

    if busca_estado:
        leads_list = leads_list.filter(estado__iexact=busca_estado)

    leads_por_regiao = leads_list

    if busca_cidade:
        leads_por_regiao = leads_por_regiao.filter(cidade__icontains=busca_cidade)

    if busca_bairro:
        leads_com_bairro = leads_por_regiao.filter(
            Q(bairro__icontains=busca_bairro) | Q(endereco__icontains=busca_bairro)
        )
        leads_list = leads_com_bairro if leads_com_bairro.exists() else leads_por_regiao
    else:
        leads_list = leads_por_regiao

    if busca_cep and not busca_bairro and not busca_cidade:
        leads_list = leads_list.filter(Q(cep__icontains=busca_cep) | Q(endereco__icontains=busca_cep))

    return leads_list


def anexar_parceiro_relacionado_leads(leads):
    """Anota, em cada lead, o parceiro relacionado e o total de propostas em
    negociacao (mutacao in-place, usada para a lista paginada de leads)."""
    for lead in leads:
        partner_relacionado = buscar_parceiro_existente_para_lead(lead)
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


def filtrar_lead_empresas(busca_empresa='', busca_cidade='', busca_estado=''):
    empresas = (
        LeadEmpresa.objects
        .annotate(total_enderecos=Count('enderecos', distinct=True))
        .order_by('-data_criacao', '-id')
    )

    if busca_empresa:
        empresas = empresas.filter(
            Q(nome_fantasia__icontains=busca_empresa) |
            Q(razao_social__icontains=busca_empresa) |
            Q(cnpj_cpf__icontains=busca_empresa) |
            Q(enderecos__endereco__icontains=busca_empresa) |
            Q(enderecos__numero__icontains=busca_empresa) |
            Q(enderecos__bairro__icontains=busca_empresa) |
            Q(enderecos__cidade__icontains=busca_empresa) |
            Q(enderecos__estado__icontains=busca_empresa) |
            Q(enderecos__cep__icontains=busca_empresa)
        ).distinct()

    if busca_cidade:
        empresas = empresas.filter(enderecos__cidade__icontains=busca_cidade).distinct()

    if busca_estado:
        empresas = empresas.filter(enderecos__estado__iexact=busca_estado).distinct()

    return empresas


def montar_filtro_enderecos_lead_empresa(busca_empresa='', busca_cidade='', busca_estado=''):
    """Monta o Q usado para filtrar os enderecos de cada empresa na lista
    (preview de enderecos), reaproveitando os mesmos termos da busca de
    empresas. Devolve (filtro, possui_filtro)."""
    filtros_endereco = Q()
    possui_filtro_endereco = False

    if busca_empresa:
        filtros_endereco &= (
            Q(endereco__icontains=busca_empresa) |
            Q(numero__icontains=busca_empresa) |
            Q(bairro__icontains=busca_empresa) |
            Q(cidade__icontains=busca_empresa) |
            Q(estado__icontains=busca_empresa) |
            Q(cep__icontains=busca_empresa)
        )
        possui_filtro_endereco = True

    if busca_cidade:
        filtros_endereco &= Q(cidade__icontains=busca_cidade)
        possui_filtro_endereco = True

    if busca_estado:
        filtros_endereco &= Q(estado__iexact=busca_estado)
        possui_filtro_endereco = True

    return filtros_endereco, possui_filtro_endereco


def anexar_lead_espelho_e_parceiro(enderecos):
    """Anota, em cada LeadEndereco, o lead legado (espelho) e o parceiro
    relacionado (mutacao in-place)."""
    for endereco in enderecos:
        endereco.lead_espelho = endereco.leads_legados.order_by('id').first()
        if endereco.lead_espelho:
            partner_relacionado = buscar_parceiro_existente_para_lead(endereco.lead_espelho)
            endereco.lead_espelho.partner_relacionado = partner_relacionado
        else:
            endereco.partner_relacionado = None


def anexar_enderecos_preview_empresas(empresas, filtros_endereco, possui_filtro_endereco):
    """Anota, em cada empresa da pagina, o preview (ate 3) dos enderecos que
    batem com o filtro atual e o endereco de acao rapida (mutacao in-place)."""
    for empresa in empresas:
        enderecos_qs = empresa.enderecos.all().order_by('cidade', 'bairro', 'endereco', 'id')
        if possui_filtro_endereco:
            enderecos_qs = enderecos_qs.filter(filtros_endereco)
            empresa.total_enderecos_filtrados = enderecos_qs.count()
            empresa.enderecos_filtrados_preview = list(enderecos_qs[:3])
        else:
            empresa.total_enderecos_filtrados = empresa.total_enderecos
            empresa.enderecos_filtrados_preview = []

        anexar_lead_espelho_e_parceiro(empresa.enderecos_filtrados_preview)

        empresa.endereco_acao_rapida = empresa.enderecos_filtrados_preview[0] if empresa.enderecos_filtrados_preview else None


def filtrar_enderecos_lead_empresa(empresa, q=''):
    enderecos = empresa.enderecos.all().order_by('cidade', 'bairro', 'endereco', 'id')

    if q:
        enderecos = enderecos.filter(
            Q(endereco__icontains=q) |
            Q(numero__icontains=q) |
            Q(bairro__icontains=q) |
            Q(cidade__icontains=q) |
            Q(estado__icontains=q) |
            Q(cep__icontains=q)
        )

    return enderecos


# ---------------------------------------------------------------------------
# Setores (RN-054/RN-055/ADR-028): grupo dedicado + concessao individual por
# nome de Setor dentro do modulo "Setores".
# ---------------------------------------------------------------------------

def nomes_setor_concedidos(usuario):
    """RN-055: nomes de Setor explicitamente concedidos a `usuario`
    (`AcessoSetor`). Superusuario nao usa esta funcao — continua vendo/
    acessando todos os nomes cadastrados, sem concessao explicita."""
    if not usuario or not usuario.is_authenticated:
        return set()

    return set(
        AcessoSetor.objects.filter(usuario=usuario).values_list('setor_nome', flat=True)
    )


def nomes_setor_visiveis_para_usuario(usuario):
    """RN-054/RN-055: nomes de Setor (RN-025) que `usuario` pode ver/acessar
    no modulo "Setores" — todos os cadastrados para superusuario, ou a
    intersecao entre o catalogo e o que foi concedido a ele (RN-055)."""
    nomes_cadastrados = list(Setor.objects.order_by('nome').values_list('nome', flat=True).distinct())

    if usuario and usuario.is_authenticated and usuario.is_superuser:
        return nomes_cadastrados

    concedidos = nomes_setor_concedidos(usuario)
    return [nome for nome in nomes_cadastrados if nome in concedidos]


def usuario_pode_acessar_setor(usuario, nome_setor):
    """RN-055: usado por `setor_detail` para negar acesso (403) a um nome
    de Setor existente no catalogo mas nao concedido ao usuario."""
    if usuario and usuario.is_authenticated and usuario.is_superuser:
        return True

    return nome_setor in nomes_setor_concedidos(usuario)


def usuarios_responsavel_opcoes(setor):
    """RN-060: usuarios elegiveis para o campo Responsavel de uma
    subatividade (RedeExterna/RedeInterna/MapaCalor, RN-052/ADR-027)
    atribuida a `setor`. Sem Setor definido (`setor=None`), nao ha
    filtro — devolve todos os usuarios ativos, mesmo comportamento de
    antes desta regra. Com Setor definido, restringe aos usuarios ativos
    com `AcessoSetor` concedido para aquele nome (RN-055/ADR-028), mais
    o(s) superusuario(s) — mesma excecao ja usada pela RN-055. Um Setor
    sem ninguem com acesso concedido devolve so os superusuarios (pode
    ser uma lista vazia)."""
    ativos = get_user_model().objects.filter(is_active=True)

    if setor is None:
        return ativos.order_by('first_name', 'last_name', 'username')

    usuarios_com_acesso = AcessoSetor.objects.filter(setor_nome=setor.nome).values_list('usuario_id', flat=True)
    return ativos.filter(
        Q(is_superuser=True) | Q(pk__in=usuarios_com_acesso)
    ).order_by('first_name', 'last_name', 'username')


def responsavel_opcoes_por_setor(setores):
    """RN-060: pre-calcula, para uma colecao de Setor (RN-025), a lista de
    usuarios elegiveis para Responsavel de cada um — usado pelo grid de
    Enderecos Lastmile para montar a opcao correta em cada linha sem
    disparar uma consulta de `AcessoSetor` por linha (N+1, CLAUDE.md
    secao 7). Devolve um dict `{setor_id: [usuarios]}`; setores com o
    mesmo nome (RN-025, espelhados entre Processos) compartilham a mesma
    lista, calculada uma unica vez por nome."""
    setores = list(setores)
    if not setores:
        return {}

    nomes = {setor.nome for setor in setores}
    ativos = list(get_user_model().objects.filter(is_active=True).order_by('first_name', 'last_name', 'username'))

    ids_com_acesso_por_nome = {}
    for usuario_id, setor_nome in AcessoSetor.objects.filter(setor_nome__in=nomes).values_list('usuario_id', 'setor_nome'):
        ids_com_acesso_por_nome.setdefault(setor_nome, set()).add(usuario_id)

    opcoes_por_nome = {
        nome: [
            usuario for usuario in ativos
            if usuario.is_superuser or usuario.id in ids_com_acesso_por_nome.get(nome, set())
        ]
        for nome in nomes
    }
    return {setor.id: opcoes_por_nome[setor.nome] for setor in setores}


#: RN-063: nomes de Setor onde a Escola some da tela do proprio Setor assim
#: que RedeExterna/RedeInterna vinculadas a ele estiverem "Concluido"
#: (Mapa Calor nunca entra no criterio, mesma convencao da RN-062). Nao
#: exige que o Setor ja exista no catalogo — "Qualidade" ainda nao esta
#: cadastrado no momento desta regra.
SETORES_OCULTAM_ESCOLA_CONCLUIDA = {"Implantacao", "Qualidade"}


#: RN-066: codigos aceitos pelo filtro de tipo de subatividade (checkbox
#: multiplo, exclusivo da Tela de Setor) e o campo de `ProcessoRedeBase`
#: (relacao reversa a partir de `Escola`) que cada codigo representa.
_RELACAO_POR_TIPO_SUBATIVIDADE = {
    're': 'rede_externa',
    'ri': 'rede_interna',
    'mc': 'mapa_calor',
}


def _q_cor_indicador_conectividade(cor):
    """RN-067: traduz para `Q()` o mesmo criterio de cor calculado pela
    property `Escola.indicador_conectividade` (RN-062), usado pelo filtro
    de cor (checkbox multiplo, exclusivo do grid global). RE/RI sem
    registro para a Escola contam como "nao concluida" — a negacao
    (`~Q(...)`) sobre uma relacao OneToOne reversa ja inclui a checagem de
    nulidade necessaria (Django adiciona `IS NOT NULL` na comparacao
    negada), entao nao e preciso tratar a ausencia do registro a parte."""
    re_concluida = Q(rede_externa__status__nome="Concluido")
    ri_concluida = Q(rede_interna__status__nome="Concluido")

    if cor == 'verde':
        return re_concluida & ri_concluida
    if cor == 'amarelo':
        return (re_concluida & ~ri_concluida) | (~re_concluida & ri_concluida)
    if cor == 'vermelho':
        return ~re_concluida & ~ri_concluida
    return None


def status_opcoes_por_nome_setor(setor_nome):
    """RN-066: nomes distintos de `SetorStatus` (RN-025) cadastrados em
    qualquer `Setor` (de qualquer Processo — RE, RI e MC compartilham o
    mesmo vocabulario de nome de Setor, PO-050) que tenha esse nome —
    opcoes do filtro de Status da Tela de Setor. Nao lista Status de
    outros Setores. Comparacao por nome (nao por id do catalogo) porque o
    mesmo nome de Setor tem uma linha de `Setor` (e portanto um catalogo
    de `SetorStatus` proprio) por Processo (RE/RI/MC) — mesmo vocabulario
    espelhado usado pelo indicador de conectividade (RN-062)."""
    if not setor_nome:
        return []

    return list(
        SetorStatus.objects.filter(setor__nome=setor_nome)
        .order_by('nome').values_list('nome', flat=True).distinct()
    )


def filtrar_escolas_lastmile(
    q='', cidade='', estado='', setor_nome=None,
    tipos_subatividade=None, responsavel_id=None, status_nome=None,
    cores_conectividade=None,
):
    """Tela global de Enderecos Lastmile (ADR-011): fonte de dados trocada
    de `Endereco` (sincronizado do IXC, ADR-008) para `Escola`
    (DashboardEACE, ADR-010). Sem filtro de elegibilidade — mostra todas as
    escolas sincronizadas.

    `setor_nome` (ADR-017/PO-053): quando informado, restringe a somente
    as escolas com RedeExterna, RedeInterna ou MapaCalor (RN-043)
    vinculada a um Setor com esse nome, em qualquer Processo (RE, RI e MC
    compartilham o mesmo vocabulario de nomes de Setor, PO-050) — usado
    pela tela de Setor.

    RN-063: quando `setor_nome` esta em `SETORES_OCULTAM_ESCOLA_CONCLUIDA`,
    a Escola tambem some dessa listagem se toda RedeExterna/RedeInterna
    vinculada a esse Setor especifico ja estiver "Concluido" — avaliado por
    Setor, sem olhar onde a outra subatividade esta. Mapa Calor nunca entra
    nesse criterio. Nao afeta o grid global (`setor_nome=None`) nem os
    demais Setores.

    RN-066: `tipos_subatividade` (codigos 're'/'ri'/'mc'), `responsavel_id`
    e `status_nome` sao filtros exclusivos da Tela de Setor — so tem
    efeito quando `setor_nome` esta presente (o grid global nunca os
    recebe da view, mas o parametro tambem e ignorado aqui como segunda
    camada de protecao). Os tres avaliam somente as subatividades
    vinculadas a `setor_nome` (nunca a mesma Escola vinculada a outro
    Setor): tipo e um OR entre os codigos marcados; Responsavel e Status
    sao avaliados cada um a parte (independente do tipo marcado) e
    combinados por E com os demais filtros ativos.

    RN-067: `cores_conectividade` (codigos 'verde'/'amarelo'/'vermelho') e
    o filtro exclusivo do grid global — so tem efeito quando `setor_nome`
    esta ausente (mesma segunda camada de protecao do RN-066, invertida:
    aqui o parametro e ignorado se `setor_nome` vier presente). OR entre
    as cores marcadas; traduz o mesmo criterio de
    `Escola.indicador_conectividade` (RN-062) para `Q()`.
    """
    escolas = Escola.objects.select_related(
        'rede_externa', 'rede_externa__setor', 'rede_externa__status', 'rede_externa__responsavel',
        'rede_interna', 'rede_interna__setor', 'rede_interna__status', 'rede_interna__responsavel',
        'mapa_calor', 'mapa_calor__setor', 'mapa_calor__status', 'mapa_calor__responsavel',
    ).prefetch_related(
        'rede_externa__setor__status_opcoes',
        'rede_interna__setor__status_opcoes',
        'mapa_calor__setor__status_opcoes',
    )

    if setor_nome:
        escolas = escolas.filter(
            Q(rede_externa__setor__nome=setor_nome)
            | Q(rede_interna__setor__nome=setor_nome)
            | Q(mapa_calor__setor__nome=setor_nome)
        )

        if setor_nome in SETORES_OCULTAM_ESCOLA_CONCLUIDA:
            re_aqui = Q(rede_externa__setor__nome=setor_nome)
            ri_aqui = Q(rede_interna__setor__nome=setor_nome)
            re_pendente_aqui = re_aqui & ~Q(rede_externa__status__nome="Concluido")
            ri_pendente_aqui = ri_aqui & ~Q(rede_interna__status__nome="Concluido")

            # RN-063: exclui quando RE e/ou RI estao vinculados a este
            # Setor (pelo menos um dos dois) e nenhum dos vinculados aqui
            # ainda esta pendente — Escola presente so via Mapa Calor (sem
            # RE/RI neste Setor) nao cai nesta exclusao.
            escolas = escolas.exclude(
                (re_aqui | ri_aqui) & ~re_pendente_aqui & ~ri_pendente_aqui
            )

        if tipos_subatividade:
            # RN-066: OR entre os tipos marcados — a Escola aparece se
            # pelo menos um tipo marcado tiver a subatividade
            # correspondente vinculada a este Setor.
            tipo_q = Q()
            for tipo in tipos_subatividade:
                relacao = _RELACAO_POR_TIPO_SUBATIVIDADE.get(tipo)
                if relacao:
                    tipo_q |= Q(**{f"{relacao}__setor__nome": setor_nome})
            if tipo_q:
                escolas = escolas.filter(tipo_q)

        if responsavel_id:
            # RN-066: pelo menos uma subatividade vinculada a este Setor
            # tem esse Responsavel — independe do filtro de tipo acima.
            escolas = escolas.filter(
                Q(rede_externa__setor__nome=setor_nome, rede_externa__responsavel_id=responsavel_id)
                | Q(rede_interna__setor__nome=setor_nome, rede_interna__responsavel_id=responsavel_id)
                | Q(mapa_calor__setor__nome=setor_nome, mapa_calor__responsavel_id=responsavel_id)
            )

        if status_nome:
            # RN-066: pelo menos uma subatividade vinculada a este Setor
            # tem esse Status (por nome — RN-062 ja usa o mesmo criterio
            # de comparacao, o catalogo de Status e espelhado por nome de
            # Setor entre os Processos RE/RI/MC) — independe do tipo.
            escolas = escolas.filter(
                Q(rede_externa__setor__nome=setor_nome, rede_externa__status__nome=status_nome)
                | Q(rede_interna__setor__nome=setor_nome, rede_interna__status__nome=status_nome)
                | Q(mapa_calor__setor__nome=setor_nome, mapa_calor__status__nome=status_nome)
            )

    if not setor_nome and cores_conectividade:
        # RN-067: OR entre as cores marcadas — a Escola aparece se
        # `indicador_conectividade["cor"]` corresponder a pelo menos uma
        # delas. Segunda camada de protecao: ignorado quando `setor_nome`
        # esta presente, mesmo que o parametro venha preenchido.
        cor_q = Q()
        for cor in cores_conectividade:
            criterio = _q_cor_indicador_conectividade(cor)
            if criterio:
                cor_q |= criterio
        if cor_q:
            escolas = escolas.filter(cor_q)

    if q:
        escolas = escolas.filter(
            Q(nome__icontains=q) |
            Q(inep__icontains=q) |
            Q(municipio__icontains=q) |
            Q(uf__icontains=q) |
            Q(jira_key__icontains=q) |
            Q(endereco_descricao__icontains=q)
        )

    if cidade:
        escolas = escolas.filter(municipio__icontains=cidade)

    if estado:
        escolas = escolas.filter(uf__iexact=estado)

    escolas = escolas.order_by('nome', 'id')

    return escolas


def contar_rede_externa_interna_por_setor(escolas, setor_nome):
    """RN-065: quantidade de RedeExterna e de RedeInterna vinculadas a
    `setor_nome`, dentro do queryset de `escolas` ja filtrado (mesmo
    queryset usado para `total_enderecos`/`paginator.count`, portanto ja
    reflete `q`/`cidade`/`estado`). Contagem bruta, sem olhar `status`
    (RN-025) — Mapa Calor nunca entra aqui (RN-043).

    Agregado numa unica consulta (evita N+1, CLAUDE.md secao 7): nao
    itera escola por escola."""
    agregado = escolas.aggregate(
        total_re=Count('rede_externa', filter=Q(rede_externa__setor__nome=setor_nome)),
        total_ri=Count('rede_interna', filter=Q(rede_interna__setor__nome=setor_nome)),
    )
    return agregado['total_re'], agregado['total_ri']


def historico_rede(rede):
    """PO-054/RN-029: historico proprio de um RedeExterna/RedeInterna/
    MapaCalor (RN-043), mais recente primeiro (Meta.ordering de
    RegistroHistorico)."""
    return RegistroHistorico.objects.filter(
        content_type=ContentType.objects.get_for_model(type(rede)), object_id=rede.id,
    ).select_related('usuario')


def adicionar_historico_rede(rede, descricao, arquivo, usuario):
    """PO-054/RN-029: cria o registro de comentario/anexo individual do
    RedeExterna/RedeInterna. Devolve False quando nao ha o que gravar."""
    if not (descricao or arquivo):
        return False

    tipo = 'anexo' if arquivo else 'comentario'
    RegistroHistorico.objects.create(
        tipo=tipo,
        acao=descricao,
        arquivo=arquivo,
        usuario=usuario,
        content_type=ContentType.objects.get_for_model(type(rede)),
        object_id=rede.id,
    )
    return True


def nome_usuario_ou_none(usuario):
    """RN-052/ADR-027: nome de exibicao de um usuario do sistema (nome
    completo, com fallback para o username) para o campo Responsavel de
    RE/RI/MapaCalor — mesmo padrao ja usado para `Proposal.responsavel`
    (`apps/partners/services.py`). Devolve None quando nao ha usuario, para
    comparar com o valor anterior no mesmo formato de Setor/Status/Parceiro."""
    if not usuario:
        return None
    return usuario.get_full_name() or usuario.username


def registrar_historico_alteracao_rede(
    rede, usuario, setor_anterior_nome, status_anterior_nome,
    parceiro_anterior_nome=None, responsavel_anterior_nome=None, setor_atual=None,
):
    """RN-029/RN-030/RN-052: alteracao de Setor/Status/Parceiro/Responsavel
    feita pela tela de Enderecos Lastmile (`escola_rede_editar`) gera um
    RegistroHistorico tipo 'sistema' com o valor anterior e o novo, mesmo
    padrao Antes/Depois ja usado em
    `apps/partners/services.py::processar_edicao_proposta`.
    Edicao feita direto no Django Admin nao passa por aqui.

    RN-041 (ampliada): cada campo alterado no mesmo submit (Setor, Status,
    Parceiro e/ou Responsavel) gera o seu proprio RegistroHistorico
    estruturado (rotulo/valor_anterior/valor_novo), em vez de um unico
    registro com frase combinada — inclusive quando mais de um campo muda de
    uma vez, como a cascata Setor->Status (RN-026/RN-033/RN-035) e a
    zeragem automatica de Responsavel ao trocar de Setor (RN-052/ADR-027).
    Todos os registros deste submit compartilham o mesmo `setor_nome`
    (setor_atual da tela) e o mesmo instante: `data` e sobrescrito apos a
    criacao porque `auto_now_add` ignora valor explicito passado em
    `.create()`."""
    setor_novo_nome = rede.setor.nome if rede.setor_id else None
    status_novo_nome = rede.status.nome if rede.status_id else None
    parceiro_novo_nome = str(rede.parceiro) if rede.parceiro_id else None
    responsavel_novo_nome = nome_usuario_ou_none(rede.responsavel) if rede.responsavel_id else None

    mudancas = []
    if setor_novo_nome != setor_anterior_nome:
        mudancas.append(("Setor", setor_anterior_nome, setor_novo_nome))
    if status_novo_nome != status_anterior_nome:
        mudancas.append(("Status", status_anterior_nome, status_novo_nome))
    if parceiro_novo_nome != parceiro_anterior_nome:
        mudancas.append(("Parceiro", parceiro_anterior_nome, parceiro_novo_nome))
    if responsavel_novo_nome != responsavel_anterior_nome:
        mudancas.append(("Responsavel", responsavel_anterior_nome, responsavel_novo_nome))

    if not mudancas:
        return

    content_type = ContentType.objects.get_for_model(type(rede))
    instante = timezone.now()
    ids_criados = []
    for rotulo, anterior, novo in mudancas:
        anterior_fmt = anterior or "Vazio"
        novo_fmt = novo or "Vazio"
        texto = (
            f"Atualizado:\n• {rotulo}: {novo_fmt}"
            "\n\n--------------------------------------\n\n"
            f"Antes:\n• {rotulo}: {anterior_fmt}"
        )
        registro = RegistroHistorico.objects.create(
            tipo='sistema',
            acao=texto,
            rotulo=rotulo,
            valor_anterior=anterior_fmt,
            valor_novo=novo_fmt,
            setor_nome=setor_atual,
            usuario=usuario,
            content_type=content_type,
            object_id=rede.id,
        )
        ids_criados.append(registro.id)

    RegistroHistorico.objects.filter(id__in=ids_criados).update(data=instante)


def candidatos_cotacao_rede(rede):
    """RN-044: candidatos em cotacao (Em cotacao/Selecionado/Recusado) do
    RedeExterna/RedeInterna informado, mais recente primeiro (Meta.ordering
    de CotacaoParceiro)."""
    return CotacaoParceiro.objects.filter(
        content_type=ContentType.objects.get_for_model(type(rede)), object_id=rede.id,
    ).select_related('parceiro')


def adicionar_candidato_cotacao_rede(rede, parceiro):
    """RN-044: adiciona um Parceiro candidato em cotacao para o RE/RI. Nao
    duplica candidato ja cadastrado (mesmo Parceiro, qualquer situacao) —
    devolve a linha existente nesse caso (`UniqueConstraint
    cotacaoparceiro_parceiro_unico_por_instancia`)."""
    candidato, _ = CotacaoParceiro.objects.get_or_create(
        content_type=ContentType.objects.get_for_model(type(rede)),
        object_id=rede.id,
        parceiro=parceiro,
        defaults={'situacao': CotacaoParceiro.SITUACAO_EM_COTACAO},
    )
    return candidato


def remover_candidato_cotacao_rede(candidato):
    """RN-044: remove um candidato ainda nao selecionado. Devolve False sem
    remover quando o candidato ja e o "Selecionado" da cotacao."""
    if candidato.situacao == CotacaoParceiro.SITUACAO_SELECIONADO:
        return False
    candidato.delete()
    return True


def selecionar_candidato_cotacao_rede(candidato, usuario, setor_atual=None):
    """RN-044/ADR-026: marca `candidato` como "Selecionado", move os demais
    candidatos do mesmo RE/RI para "Recusado" (regra de vencedor unico,
    reforcada aqui alem da UniqueConstraint condicional do model) e
    preenche `RedeExterna.parceiro`/`RedeInterna.parceiro` (RN-030) com
    esse Parceiro — gerando RegistroHistorico no mesmo padrao Antes/Depois
    ja usado para Parceiro (RN-030/041), via `registrar_historico_alteracao_rede`.
    A lista de candidatos em si nao gera RegistroHistorico proprio (fora do
    escopo da ADR-026); so a mudanca de `parceiro` decorrente entra no
    historico."""
    rede = candidato.content_object
    setor_anterior_nome = rede.setor.nome if rede.setor_id else None
    status_anterior_nome = rede.status.nome if rede.status_id else None
    parceiro_anterior_nome = str(rede.parceiro) if rede.parceiro_id else None

    with transaction.atomic():
        CotacaoParceiro.objects.filter(
            content_type=candidato.content_type, object_id=candidato.object_id,
        ).exclude(pk=candidato.pk).update(situacao=CotacaoParceiro.SITUACAO_RECUSADO)

        candidato.situacao = CotacaoParceiro.SITUACAO_SELECIONADO
        candidato.save(update_fields=['situacao', 'atualizado_em'])

        rede.parceiro = candidato.parceiro
        rede.save(update_fields=['parceiro', 'atualizado_em'])

    registrar_historico_alteracao_rede(
        rede, usuario, setor_anterior_nome, status_anterior_nome, parceiro_anterior_nome,
        setor_atual=setor_atual,
    )
    return rede


def historico_combinado_escola(escola):
    """PO-054/RN-029: historico de RE, RI e Mapa Calor (RN-043/PO-067)
    juntos para a Escola (registro 'pai' dos tres processos), marcando de
    qual processo cada entrada veio. Uma consulta por processo — sem N+1
    por entrada.

    PO-066/RN-042: passa a incluir tambem os registros gravados direto no
    nivel da Escola (ex.: e-mail enviado a partir da tela da Escola, nivel
    "Global") — sao os unicos visiveis nas tres sub-atividades (RE, RI e
    Mapa Calor), exatamente esta visao combinada."""
    entradas = []
    rede_externa = RedeExterna.objects.filter(escola=escola).first()
    if rede_externa:
        for item in historico_rede(rede_externa):
            item.origem_tipo = 're'
            entradas.append(item)

    rede_interna = RedeInterna.objects.filter(escola=escola).first()
    if rede_interna:
        for item in historico_rede(rede_interna):
            item.origem_tipo = 'ri'
            entradas.append(item)

    mapa_calor = MapaCalor.objects.filter(escola=escola).first()
    if mapa_calor:
        for item in historico_rede(mapa_calor):
            item.origem_tipo = 'mc'
            entradas.append(item)

    escola_content_type = ContentType.objects.get_for_model(Escola)
    for item in RegistroHistorico.objects.filter(
        content_type=escola_content_type, object_id=escola.id,
    ).select_related('usuario'):
        item.origem_tipo = 'escola'
        entradas.append(item)

    entradas.sort(key=lambda item: item.data, reverse=True)
    return entradas


_CAMPO_APLICA_POR_TIPO = {'re': 'aplica_re', 'ri': 'aplica_ri', 'mc': 'aplica_mapa_calor'}
"""RN-043: mapeia o `tipo` de processo (RE/RI/MapaCalor) para o campo
booleano correspondente de `SetorEscopo` (RN-037)."""


def _nomes_setor_fora_da_sub_atividade(tipo):
    """PO-062/RN-037/ADR-022: nomes de Setor cujo escopo (`SetorEscopo`)
    bloqueia a exibicao no modal de RE (`tipo='re'`), RI (`tipo='ri'`) ou
    Mapa Calor (`tipo='mc'`, RN-043) — ou porque o escopo e "Escola", ou
    porque a sub-atividade daquele tipo foi desmarcada. Setor sem
    `SetorEscopo` cadastrado nao entra aqui — mantem o comportamento
    legado (Sub-atividades: RE, RI e Mapa Calor)."""
    campo_aplica = _CAMPO_APLICA_POR_TIPO[tipo]
    bloqueados = SetorEscopo.objects.exclude(
        atividade=SetorEscopo.ATIVIDADE_SUB_ATIVIDADES, **{campo_aplica: True}
    )
    return set(bloqueados.values_list('setor_nome', flat=True))


def _campo_visivel(campo, status_atual_nome):
    """RN-039/ADR-024: Campo com Status condicionante preenchido so aparece
    no modal (RN-032) quando o Status atual (nome) do RE/RI exibido for
    igual; sem Status condicionante, mantem o comportamento anterior
    (sempre visivel). A Escola nao tem Status (RN-026 e exclusivo de
    RE/RI), entao `status_atual_nome=None` faz um Campo com Status
    condicionante nunca aparecer no modal de Campos da Escola."""
    if not campo.status_condicionante_nome:
        return True
    return campo.status_condicionante_nome == status_atual_nome


def _valor_campo_calculado(valor_base_iso, horas_prazo):
    """RN-039/ADR-024: valor de um Campo tipo Calculado, derivado ao vivo —
    soma ao valor atual (ISO) do Campo base os dias corridos equivalentes a
    `horas_prazo` (arredondado para cima quando nao for multiplo exato de
    24; 72h = exatos 3 dias). Em branco se o Campo base nao tiver valor."""
    if not valor_base_iso or not horas_prazo:
        return None
    try:
        data_base = datetime.date.fromisoformat(valor_base_iso)
    except (TypeError, ValueError):
        return None
    dias = math.ceil(horas_prazo / 24)
    return (data_base + datetime.timedelta(days=dias)).isoformat()


def _formatar_valor_campo_historico(campo, valor):
    """RN-040: formata o valor (bruto, ja validado por `_validar_valor_campo`)
    de um Campo para exibicao no historico, no mesmo vocabulario usado no
    modal de Campos (RN-032): data dd/mm/aaaa, Sim/Nao, ou o valor cru para
    os demais tipos. Valor ausente/vazio mostra "(vazio)" (RN-040)."""
    if valor is None or valor == "":
        return "(vazio)"
    if campo.tipo in (Campo.TIPO_DATA, Campo.TIPO_CALCULADO):
        try:
            return datetime.date.fromisoformat(valor).strftime("%d/%m/%Y")
        except (TypeError, ValueError):
            return str(valor)
    if campo.tipo == Campo.TIPO_SIM_NAO:
        return "Sim" if valor else "Não"
    if campo.tipo == Campo.TIPO_NUMERO and isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor)


def _registrar_historico_campo(content_object, usuario, campo, valor_anterior_bruto, valor_novo_bruto):
    """RN-040: alteracao de `CampoValor` feita pela tela (modal de Campos,
    RE/RI ou Escola) gera um RegistroHistorico tipo 'sistema' com o valor
    anterior/novo do Campo (RN-041: De/Para estruturado — rotulo, valor
    anterior, valor novo e Setor, alem de manter `acao` em frase, mesmo
    padrao Antes/Depois ja usado para Setor/Status/Parceiro). `setor_nome`
    usa o Setor dono do Campo (`campo.setor_nome`) — na tela de RE/RI isso
    e sempre igual ao `setor_atual` da edicao, ja que somente os Campos do
    Setor da tela ficam editaveis (RN-032); na Escola, sem tela por Setor,
    e o unico Setor disponivel para o registro.

    Quando `campo` e `campo_base` de algum Campo tipo Calculado (RN-039) do
    mesmo Setor, o mesmo registro tambem traz o valor calculado resultante
    (RN-040) — nao cria um RegistroHistorico separado para o Calculado, que
    continua sem CampoValor proprio. Edicao direta no Django Admin nao
    passa por aqui."""
    anterior_fmt = _formatar_valor_campo_historico(campo, valor_anterior_bruto)
    novo_fmt = _formatar_valor_campo_historico(campo, valor_novo_bruto)

    dependentes_texto = [
        f"{calculado.nome}: {_formatar_valor_campo_historico(calculado, _valor_campo_calculado(valor_novo_bruto, calculado.horas_prazo))}"
        for calculado in Campo.objects.filter(campo_base=campo, tipo=Campo.TIPO_CALCULADO)
    ]
    novo_fmt_completo = novo_fmt
    if dependentes_texto:
        novo_fmt_completo = f"{novo_fmt} ({'; '.join(dependentes_texto)})"

    texto = (
        f"Atualizado:\n• {campo.nome}: {novo_fmt_completo}"
        "\n\n--------------------------------------\n\n"
        f"Antes:\n• {campo.nome}: {anterior_fmt}"
    )

    RegistroHistorico.objects.create(
        tipo='sistema',
        acao=texto,
        rotulo=campo.nome,
        valor_anterior=anterior_fmt,
        valor_novo=novo_fmt_completo,
        setor_nome=campo.setor_nome,
        usuario=usuario,
        content_type=ContentType.objects.get_for_model(type(content_object)),
        object_id=content_object.id,
    )


def campos_grid_rede(rede, tipo, setor_atual):
    """PO-058/RN-032: Campos (RN-031) agrupados por Setor dono, com o
    valor atual (CampoValor) desta instancia de RedeExterna/RedeInterna.
    O grupo do `setor_atual` vem marcado como editavel/expandido; os
    demais ficam somente leitura — mesma regra de edicao ja usada para
    Parceiro (RN-030). PO-062/RN-037: Campo cujo Setor tem escopo "Escola",
    ou "Sub-atividades" sem aplicar a este `tipo` (RE/RI), nao aparece
    aqui — passa a aparecer no modal de Campos da Escola. PO-063/RN-039:
    Campo com Status condicionante so entra quando o Status atual do
    `rede` tiver o mesmo nome; Campo tipo Calculado nunca e editavel e seu
    valor e derivado do respectivo Campo base (mesma consulta de
    CampoValor ja feita aqui — sem N+1 adicional)."""
    nomes_bloqueados = _nomes_setor_fora_da_sub_atividade(tipo)
    campos = Campo.objects.exclude(setor_nome__in=nomes_bloqueados).order_by('setor_nome', 'nome')
    status_atual_nome = rede.status.nome if getattr(rede, 'status_id', None) else None

    valores = {}
    if rede.pk:
        content_type = ContentType.objects.get_for_model(type(rede))
        valores = {
            valor.campo_id: valor.valor
            for valor in CampoValor.objects.filter(content_type=content_type, object_id=rede.pk, campo__in=campos)
        }

    grupos = {}
    for campo in campos:
        if not _campo_visivel(campo, status_atual_nome):
            continue
        if campo.tipo == Campo.TIPO_CALCULADO:
            valor = _valor_campo_calculado(valores.get(campo.campo_base_id), campo.horas_prazo)
            editavel = False
        else:
            valor = valores.get(campo.id)
            editavel = campo.setor_nome == setor_atual
        grupos.setdefault(campo.setor_nome, []).append({
            "campo": campo,
            "valor": valor,
            "editavel": editavel,
        })

    return [
        {"setor_nome": setor_nome, "campos": itens, "expandido": setor_nome == setor_atual}
        for setor_nome, itens in grupos.items()
    ]


def _validar_valor_campo(campo, valor_bruto):
    """Valida `valor_bruto` (string vinda do POST) conforme `Campo.tipo`
    (ADR-019: validacao feita na view/service, nao somente na UI). Devolve
    uma tupla (valor_pronto_para_gravar, mensagem_de_erro)."""
    if not valor_bruto:
        return None, None

    if campo.tipo == Campo.TIPO_NUMERO:
        try:
            return float(valor_bruto), None
        except ValueError:
            return None, "informe um numero valido."

    if campo.tipo == Campo.TIPO_DATA:
        try:
            return datetime.date.fromisoformat(valor_bruto).isoformat(), None
        except ValueError:
            return None, "informe uma data valida."

    if campo.tipo == Campo.TIPO_SIM_NAO:
        if valor_bruto not in ("sim", "nao"):
            return None, "selecione Sim ou Nao."
        return valor_bruto == "sim", None

    if campo.tipo == Campo.TIPO_LISTA:
        if valor_bruto not in (campo.opcoes or []):
            return None, "selecione uma das opcoes cadastradas."
        return valor_bruto, None

    return valor_bruto, None


def salvar_campos_rede(rede, tipo, setor_atual, dados_post, usuario=None):
    """PO-058/RN-032: valida e grava CampoValor para os Campos cujo Setor
    dono e o `setor_atual` (mesma regra de edicao do Parceiro, RN-030) —
    campos de outros Setores sao ignorados mesmo que venham no POST.
    PO-062/RN-037: Campo cujo Setor tem escopo "Escola", ou "Sub-
    atividades" sem aplicar a este `tipo`, tambem e ignorado aqui, mesmo
    que `setor_atual` aponte para aquele nome de Setor. PO-063/RN-039:
    Campo tipo Calculado nunca e gravado (valor sempre derivado ao vivo) e
    Campo com Status condicionante cujo Status atual do `rede` nao bate e
    ignorado, mesmo enviado no POST. PO-064/RN-040: toda alteracao real de
    valor (diferente do valor anterior) gera RegistroHistorico tipo
    sistema — reenviar o mesmo valor nao gera log, mesmo padrao ja usado
    para Setor/Status/Parceiro (RN-029). Devolve a lista de erros de
    validacao; nada e gravado se houver algum."""
    if not setor_atual:
        return ["Edicao de Campos so e permitida pela tela de um Setor especifico."]

    if setor_atual in _nomes_setor_fora_da_sub_atividade(tipo):
        return [f"O Setor '{setor_atual}' nao esta configurado para Sub-atividades (RE/RI)."]

    status_atual_nome = rede.status.nome if getattr(rede, 'status_id', None) else None
    campos_editaveis = [
        campo for campo in Campo.objects.filter(setor_nome=setor_atual).exclude(tipo=Campo.TIPO_CALCULADO)
        if _campo_visivel(campo, status_atual_nome)
    ]
    if not campos_editaveis:
        return [f"Nenhum campo cadastrado para o Setor '{setor_atual}'."]

    erros = []
    valores_validados = {}

    for campo in campos_editaveis:
        valor_bruto = (dados_post.get(f"campo_{campo.id}") or "").strip()
        valor, erro = _validar_valor_campo(campo, valor_bruto)
        if erro:
            erros.append(f"{campo.nome}: {erro}")
        else:
            valores_validados[campo.id] = valor

    if erros:
        return erros

    content_type = ContentType.objects.get_for_model(type(rede))
    campos_por_id = {campo.id: campo for campo in campos_editaveis}
    valores_anteriores = {
        valor.campo_id: valor.valor
        for valor in CampoValor.objects.filter(content_type=content_type, object_id=rede.id, campo__in=campos_editaveis)
    }

    with transaction.atomic():
        for campo_id, valor in valores_validados.items():
            anterior = valores_anteriores.get(campo_id)
            CampoValor.objects.update_or_create(
                campo_id=campo_id, content_type=content_type, object_id=rede.id,
                defaults={"valor": valor},
            )
            if valor != anterior:
                _registrar_historico_campo(rede, usuario, campos_por_id[campo_id], anterior, valor)

    return []


def campos_obrigatorios_pendentes(rede, setor_origem_nome, setor_destino_nome):
    """PO-079/RN-061/ADR-031: nomes dos Campos (RN-031) que bloqueiam a
    troca do Setor `setor_origem_nome` para `setor_destino_nome` — regras
    cadastradas na tela "Campos" (`CampoObrigatoriedadeTransicao`) para
    algum Campo do Setor de origem, cujo `CampoValor` ainda esta vazio
    (`None`, nunca preenchido) para esta instancia de RedeExterna/
    RedeInterna/MapaCalor. Lista vazia libera a troca. So faz sentido
    chamar quando ja existe um Setor de origem real (troca, nao primeira
    atribuicao) — o chamador (RN-033: `enviado_a_outro_setor`) ja garante
    isso."""
    campos_regra = list(
        Campo.objects.filter(setor_nome=setor_origem_nome, regras_obrigatoriedade__setor_destino_nome=setor_destino_nome)
        .exclude(tipo=Campo.TIPO_CALCULADO)
    )
    if not campos_regra:
        return []

    valores = {}
    if rede.pk:
        content_type = ContentType.objects.get_for_model(type(rede))
        valores = {
            valor.campo_id: valor.valor
            for valor in CampoValor.objects.filter(content_type=content_type, object_id=rede.pk, campo__in=campos_regra)
        }

    return [campo.nome for campo in campos_regra if valores.get(campo.id) is None]


def campos_grid_escola(escola):
    """PO-062/RN-037/ADR-022: Campos (RN-031) cujo Setor dono tem escopo
    "Escola" (`SetorEscopo`), agrupados por Setor, com o valor atual
    (CampoValor) desta Escola. Sem trava de edicao por Setor atual — a
    informacao pertence a Escola, editavel por quem acessa esta tela
    (grupo LastMile), ao contrario da regra usada para RE/RI (RN-032).
    PO-063/RN-039: Escola nao tem Status (exclusivo de RE/RI, RN-026),
    entao Campo com Status condicionante nunca aparece aqui; Campo tipo
    Calculado tem o valor derivado do respectivo Campo base e nunca e
    editavel."""
    nomes_escola = set(
        SetorEscopo.objects.filter(atividade=SetorEscopo.ATIVIDADE_ESCOLA).values_list('setor_nome', flat=True)
    )
    campos = Campo.objects.filter(setor_nome__in=nomes_escola).order_by('setor_nome', 'nome')

    valores = {}
    if escola.pk:
        content_type = ContentType.objects.get_for_model(Escola)
        valores = {
            valor.campo_id: valor.valor
            for valor in CampoValor.objects.filter(content_type=content_type, object_id=escola.pk, campo__in=campos)
        }

    grupos = {}
    for campo in campos:
        if not _campo_visivel(campo, None):
            continue
        if campo.tipo == Campo.TIPO_CALCULADO:
            valor = _valor_campo_calculado(valores.get(campo.campo_base_id), campo.horas_prazo)
        else:
            valor = valores.get(campo.id)
        grupos.setdefault(campo.setor_nome, []).append({
            "campo": campo,
            "valor": valor,
            "editavel": campo.tipo != Campo.TIPO_CALCULADO,
        })

    return [
        {"setor_nome": setor_nome, "campos": itens, "expandido": True}
        for setor_nome, itens in grupos.items()
    ]


def salvar_campos_escola(escola, dados_post, usuario=None):
    """PO-062/RN-037/ADR-022: valida e grava CampoValor para os Campos cujo
    Setor dono tem escopo "Escola" — sem trava por setor_atual, ja que a
    informacao vem direto do cliente (Escola), nao de um processo interno
    de RE/RI. PO-063/RN-039: Campo tipo Calculado nunca e gravado, e Campo
    com Status condicionante e ignorado (Escola nao tem Status). PO-064/
    RN-040: toda alteracao real de valor (diferente do valor anterior) gera
    RegistroHistorico tipo sistema, mesmo padrao usado em
    `salvar_campos_rede`. Devolve a lista de erros; nada e gravado se
    houver algum."""
    nomes_escola = set(
        SetorEscopo.objects.filter(atividade=SetorEscopo.ATIVIDADE_ESCOLA).values_list('setor_nome', flat=True)
    )
    campos_editaveis = [
        campo for campo in Campo.objects.filter(setor_nome__in=nomes_escola).exclude(tipo=Campo.TIPO_CALCULADO)
        if _campo_visivel(campo, None)
    ]
    if not campos_editaveis:
        return ["Nenhum campo com escopo Escola cadastrado."]

    erros = []
    valores_validados = {}

    for campo in campos_editaveis:
        valor_bruto = (dados_post.get(f"campo_{campo.id}") or "").strip()
        valor, erro = _validar_valor_campo(campo, valor_bruto)
        if erro:
            erros.append(f"{campo.nome}: {erro}")
        else:
            valores_validados[campo.id] = valor

    if erros:
        return erros

    content_type = ContentType.objects.get_for_model(Escola)
    campos_por_id = {campo.id: campo for campo in campos_editaveis}
    valores_anteriores = {
        valor.campo_id: valor.valor
        for valor in CampoValor.objects.filter(content_type=content_type, object_id=escola.id, campo__in=campos_editaveis)
    }

    with transaction.atomic():
        for campo_id, valor in valores_validados.items():
            anterior = valores_anteriores.get(campo_id)
            CampoValor.objects.update_or_create(
                campo_id=campo_id, content_type=content_type, object_id=escola.id,
                defaults={"valor": valor},
            )
            if valor != anterior:
                _registrar_historico_campo(escola, usuario, campos_por_id[campo_id], anterior, valor)

    return []


def filtrar_enderecos_lastmile_cliente(cliente, q='', sort='logradouro'):
    enderecos = cliente.enderecos.filter(
        em_os_comercial_lastmile=True,
        os_atual_aberta=True,
    )

    if q:
        enderecos = enderecos.filter(
            Q(login_ixc__icontains=q) |
            Q(logradouro__icontains=q) |
            Q(numero__icontains=q) |
            Q(bairro__icontains=q) |
            Q(cidade__icontains=q) |
            Q(cep__icontains=q) |
            Q(agent_circuit_id__icontains=q) |
            Q(ticket_os_atual_ixc__icontains=q)
        )

    if sort == 'cidade':
        enderecos = enderecos.order_by('cidade', 'logradouro', 'id')
    elif sort == 'ticket':
        enderecos = enderecos.order_by('ticket_os_atual_ixc', 'logradouro', 'id')
    else:
        enderecos = enderecos.order_by('logradouro', 'numero', 'id')

    return enderecos


def buscar_lead_enderecos_grid(cidade='', estado='', q=''):
    enderecos = LeadEndereco.objects.select_related('empresa').all()

    if estado:
        enderecos = enderecos.filter(estado__iexact=estado)

    if cidade:
        enderecos = enderecos.filter(cidade__icontains=cidade)

    if q:
        enderecos = enderecos.filter(
            Q(empresa__razao_social__icontains=q) |
            Q(empresa__nome_fantasia__icontains=q) |
            Q(empresa__cnpj_cpf__icontains=q) |
            Q(endereco__icontains=q) |
            Q(numero__icontains=q) |
            Q(bairro__icontains=q) |
            Q(cidade__icontains=q) |
            Q(estado__icontains=q) |
            Q(cep__icontains=q)
        )

    return enderecos.order_by(
        'empresa__nome_fantasia', 'empresa__razao_social', 'estado', 'cidade', 'bairro', 'endereco', 'id'
    )[:400]


def buscar_empresas_para_api(q='', estado='', cidade=''):
    empresas = LeadEmpresa.objects.all()

    if q:
        empresas = empresas.filter(
            Q(razao_social__icontains=q) |
            Q(nome_fantasia__icontains=q) |
            Q(cnpj_cpf__icontains=q)
        )

    if estado:
        empresas = empresas.filter(enderecos__estado__iexact=estado)

    if cidade:
        empresas = empresas.filter(enderecos__cidade__icontains=cidade)

    return (
        empresas.annotate(total_enderecos=Count('enderecos', distinct=True))
        .distinct()
        .order_by('nome_fantasia', 'razao_social', 'id')[:30]
    )


def buscar_enderecos_empresa_para_api(empresa, q=''):
    enderecos = empresa.enderecos.all().order_by('cidade', 'bairro', 'endereco', 'id')

    if q:
        enderecos = enderecos.filter(
            Q(endereco__icontains=q) |
            Q(numero__icontains=q) |
            Q(bairro__icontains=q) |
            Q(cidade__icontains=q) |
            Q(estado__icontains=q) |
            Q(cep__icontains=q)
        )

    return enderecos
