from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from scripts.integracoes.Lastmile.APIGoogle_BuscaFornecedores import processar_planilha

import os
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.core.files.storage import FileSystemStorage

from .models import Lead
from .forms import LeadForm
from partners.models import Partner, Proposal
from partners.forms import ProposalForm

# IMPORTAÇÃO DA TIMELINE (HISTÓRICO)
from core.models import RegistroHistorico

# Adicione essa linha junto com as outras importações lá no topo do arquivo:
from django.db.models import Q

@login_required
def lead_list(request):
    """Lista todos os leads com paginação e filtros"""
    # 1. Pega todos os leads
    leads_list = Lead.objects.all().order_by('-id')

    # 2. Captura os parâmetros digitados nos filtros (se houver)
    busca_empresa = request.GET.get('empresa', '')
    busca_status = request.GET.get('status', '')
    busca_cidade = request.GET.get('cidade', '')
    busca_estado = request.GET.get('estado', '')

    # 3. Aplica os filtros na lista
    if busca_empresa:
        # Busca tanto no nome fantasia quanto na razão social
        leads_list = leads_list.filter(
            Q(nome_fantasia__icontains=busca_empresa) | 
            Q(razao_social__icontains=busca_empresa)
        )
    
    if busca_status:
        leads_list = leads_list.filter(status=busca_status)
        
    if busca_cidade:
        leads_list = leads_list.filter(cidade__icontains=busca_cidade)
        
    if busca_estado:
        leads_list = leads_list.filter(estado__iexact=busca_estado)

    # 4. Paginação (10 por página)
    paginator = Paginator(leads_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # 5. Manda as variáveis de volta para a tela (para os campos não ficarem em branco após filtrar)
    context = {
        'page_obj': page_obj,
        'busca_empresa': busca_empresa,
        'busca_status': busca_status,
        'busca_cidade': busca_cidade,
        'busca_estado': busca_estado,
    }
    
    return render(request, 'leads/lead_list.html', context)

@login_required
def lead_create(request):
    """Criação de novos leads de prospecção"""
    if request.method == 'POST':
        form = LeadForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Novo lead cadastrado com sucesso!")
            return redirect('lead_list')
    else:
        form = LeadForm()
    return render(request, 'leads/lead_form.html', {'form': form})

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

@login_required
def lead_add_historico(request, pk):
    """Mini-view que recebe o POST do comentário/anexo e salva no banco"""
    lead = get_object_or_404(Lead, pk=pk)
    
    if request.method == 'POST':
        descricao = request.POST.get('descricao')
        arquivo = request.FILES.get('arquivo') # Pega o anexo (se houver)
        
        if descricao or arquivo:
            tipo = 'anexo' if arquivo else 'comentario'
            
            RegistroHistorico.objects.create(
                tipo=tipo,
                descricao=descricao,
                arquivo=arquivo,
                criado_por=request.user,
                content_type=ContentType.objects.get_for_model(Lead),
                object_id=lead.id
            )
            messages.success(request, "Registro adicionado à linha do tempo do lead!")
            
    # Devolve o usuário para a tela de edição do lead (onde está a timeline)
    return redirect('lead_update', pk=pk)

@login_required
def lead_delete(request, pk):
    """Remoção de lead da base"""
    lead = get_object_or_404(Lead, pk=pk)
    if request.method == 'POST':
        lead.delete()
        messages.warning(request, "Lead removido da base de prospecção.")
        return redirect('lead_list')
    return redirect('lead_list')

@login_required
def update_lead_status(request, pk):
    """Valida a intenção e redireciona para a conversão ou atualiza o status."""
    if request.method == 'POST':
        lead = get_object_or_404(Lead, pk=pk)
        novo_status = request.POST.get('status')
        
        # Guarda o status atual antes de salvar a mudança para o relatório
        status_antigo = lead.status 
        
        if novo_status == 'andamento':
            # 1. Validação de campos obrigatórios para virar Parceiro
            campos_faltantes = []
            if not lead.cnpj_cpf: campos_faltantes.append("CNPJ/CPF")
            if not lead.email: campos_faltantes.append("E-mail")
            if not lead.telefone: campos_faltantes.append("Telefone")

            if campos_faltantes:
                msg = ", ".join(campos_faltantes)
                messages.error(request, f"Não é possível converter: Os campos [{msg}] são obrigatórios.")
                return redirect('lead_list')

            # 2. Evita duplicidade (verificando na base de parceiros)
            from partners.models import Partner
            if Partner.objects.filter(cnpj_cpf=lead.cnpj_cpf).exists():
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
                    descricao=texto_historico,
                    arquivo=arquivo,
                    criado_por=request.user,
                    content_type=ContentType.objects.get_for_model(Lead),
                    object_id=lead.id
                )
            
            messages.warning(request, f"O Lead '{lead.nome_fantasia or lead.razao_social}' foi marcado como Inviável.")
            return redirect('lead_list')
            
        elif novo_status == 'negociacao':
            # =========================================================
            # LÓGICA DE NEGOCIAÇÃO: Salva e gera Histórico
            # =========================================================
            lead.status = 'negociacao'
            lead.save()

            # Só gera o log se realmente houve uma mudança de status
            if status_antigo != 'negociacao':
                from core.models import RegistroHistorico
                from django.contrib.contenttypes.models import ContentType
                
                # Pega o nome bonitinho do status antigo para o log
                status_dict = dict(Lead.STATUS_CHOICES)
                nome_antigo = status_dict.get(status_antigo, status_antigo).upper()
                
                RegistroHistorico.objects.create(
                    tipo='sistema',
                    descricao=f"🔄 Status da prospecção alterado de [{nome_antigo}] para [EM NEGOCIAÇÃO].",
                    criado_por=request.user,
                    content_type=ContentType.objects.get_for_model(Lead),
                    object_id=lead.id
                )
            
            messages.info(request, "Lead movido para Em Negociação.")
            return redirect('lead_list')
        
    return redirect('lead_list')

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

            # SALVA UMA CÓPIA DA LISTA ORIGINAL PARA O RELATÓRIO ANTES DO POP()
            lista_ids_historico = list(enderecos_ids)

            # SALVAMENTO EM CASCATA
            partner_draft.save() # Cria Parceiro

            proposta_base = form.save(commit=False)
            primeiro_endereco_id = enderecos_ids.pop(0)
            from clientes.models import Endereco 
            primeiro_endereco = get_object_or_404(Endereco, pk=primeiro_endereco_id)
            
            proposta_base.partner = partner_draft
            proposta_base.client_address = primeiro_endereco
            proposta_base.cliente = primeiro_endereco.cliente
            proposta_base.save() # Cria Proposta Principal

            for end_id in enderecos_ids:
                endereco_extra = get_object_or_404(Endereco, pk=end_id)
                clone = Proposal.objects.get(pk=proposta_base.pk)
                clone.pk = None
                clone.client_address = endereco_extra
                clone.save()

            # --- TRANSFERÊNCIA DO HISTÓRICO SPEED ---
            # Pega todo o histórico do Lead antigo
            lead_type = ContentType.objects.get_for_model(Lead)
            partner_type = ContentType.objects.get_for_model(Partner)
            
            historicos = RegistroHistorico.objects.filter(content_type=lead_type, object_id=lead.id)
            
            # Muda a titularidade de todos os eventos para o novo Parceiro
            historicos.update(content_type=partner_type, object_id=partner_draft.id)
            
            # --- NOVO: SNAPSHOT INTELIGENTE COM VÍNCULO RELACIONAL ---
            dados_vinculo = []
            dados_tecnicos = []
            dados_financeiros = []
            outros_dados = []

            # 1. CAPTURA OS DADOS DE VÍNCULO RELACIONAL (Cliente e Endereços)
            enderecos_objs = Endereco.objects.filter(id__in=lista_ids_historico)
            if enderecos_objs.exists():
                cliente_alvo = enderecos_objs.first().cliente
                dados_vinculo.append(f"• Cliente Final: {cliente_alvo}")
                for end in enderecos_objs:
                    dados_vinculo.append(f"• Unidade de Instalação: {end}")

            # 2. CAPTURA OS DADOS DO FORMULÁRIO (Financeiro e Técnico)
            for campo, valor in form.cleaned_data.items():
                if valor and campo not in ['enderecos_selecionados', 'partner', 'cliente', 'client_address']:
                    nome_campo = campo.replace('_', ' ').title()
                    
                    # Se o nome do campo der a entender que é dinheiro, coloca R$
                    if any(palavra in campo for palavra in ['valor', 'taxa', 'custo', 'pago']):
                        valor_str = f"R$ {valor}"
                    elif campo in ['vigencia', 'tempo_contrato']:
                        valor_str = f"{valor} Meses"
                    else:
                        valor_str = str(valor)

                    linha = f"• {nome_campo}: {valor_str}"

                    # Separa os campos nas categorias certas
                    if any(palavra in campo for palavra in ['valor', 'taxa', 'custo', 'pago', 'vigencia', 'email']):
                        dados_financeiros.append(linha)
                    elif any(palavra in campo for palavra in ['velocidade', 'tecnologia', 'contato', 'telefone']):
                        dados_tecnicos.append(linha)
                    else:
                        outros_dados.append(linha)
            
            # Monta o relatório estruturado completo
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

            # Log Automático do Sistema gravando a "Fotografia" inicial estruturada
            RegistroHistorico.objects.create(
                tipo='sistema',
                descricao=texto_snapshot.strip(), 
                criado_por=request.user,
                content_type=partner_type,
                object_id=partner_draft.id
            )

            # Agora podemos deletar o Lead, o histórico já está a salvo!
            lead.delete() 
            
            messages.success(request, f"Conversão Concluída! {qtd_links} links gerados para {partner_draft.nome_fantasia}.")
            return redirect('partner_detail', pk=partner_draft.pk)
    else:
        form = ProposalForm()

    return render(request, 'partners/proposal_form.html', {
        'form': form,
        'partner': partner_draft, 
        'is_lead_conversion': True
    })



@login_required
def integracoes_view(request):
    if request.method == 'POST':
        planilha = request.FILES.get('arquivo_planilha')
        
        if not planilha:
            return JsonResponse({'erro': 'Nenhum arquivo anexado.'}, status=400)

        # 1. Cria uma pasta temporária (se não existir) para salvar as planilhas
        temp_dir = os.path.join(settings.BASE_DIR, 'media', 'temp_google')
        os.makedirs(temp_dir, exist_ok=True)

        # 2. Salva o arquivo enviado pelo usuário
        fs = FileSystemStorage(location=temp_dir)
        filename = fs.save(planilha.name, planilha)
        caminho_entrada = os.path.join(temp_dir, filename)
        
        # 3. Define o nome do arquivo de saída
        caminho_saida = os.path.join(temp_dir, f"resultado_{filename}")

        try:
            # 4. CHAMA O SEU SCRIPT DO SERPER!
            # Agora ele devolve os dados além de criar a planilha
            dados_encontrados = processar_planilha(caminho_entrada, caminho_saida)
            
            # 5. SALVANDO NO BANCO DE DADOS
            # Vamos garantir que os dados vieram para não quebrar
            if dados_encontrados:
                for item in dados_encontrados:
                    # Tratamento: Evita salvar "Não informado" em campos URL e lida com campos nulos
                    site_url = item.get('Site')
                    if site_url == 'Não informado' or pd.isna(site_url):
                         site_url = ''

                    tel_str = item.get('Telefone')
                    if tel_str == 'Não informado' or pd.isna(tel_str):
                         tel_str = ''

                    end_str = item.get('Endereço Completo')
                    if end_str == 'Não informado' or pd.isna(end_str):
                         end_str = ''
                    
                    nome_fantasia_str = item.get('Nome Fantasia', 'Lead sem nome')

                    # O get_or_create evita duplicar a mesma empresa na mesma cidade!
                    Lead.objects.get_or_create(
                        nome_fantasia=nome_fantasia_str, 
                        cidade=item.get('Cidade', ''),
                        estado=item.get('Estado', ''),
                        defaults={
                            'razao_social': nome_fantasia_str, # Copia o fantasia provisoriamente
                            'telefone': tel_str,
                            'site': site_url,
                            'endereco': end_str,
                            'cnpj_cpf': '', # Fica em branco para o consultor preencher depois
                            'status': 'novo'
                        }
                    )

            # 6. Verifica se o script gerou o arquivo de saída
            if os.path.exists(caminho_saida):
                with open(caminho_saida, 'rb') as f:
                    response = HttpResponse(
                        f.read(), 
                        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )
                    # Força o navegador a baixar o arquivo
                    response['Content-Disposition'] = f'attachment; filename="Resultado_Fornecedores.xlsx"'
                    
                    # Limpeza: Apaga os arquivos temporários após enviar
                    os.remove(caminho_entrada)
                    os.remove(caminho_saida)
                    
                    # Como é uma requisição AJAX (Javascript), mensagens do Django não funcionam bem aqui.
                    # O seu frontend (JS) já mostra "Busca Concluída!" quando o arquivo baixa.
                    return response
            else:
                return JsonResponse({'erro': 'Falha ao gerar o arquivo de saída.'}, status=500)

        except Exception as e:
            # Se der algum erro (ex: chave invalida)
            import traceback
            traceback.print_exc() # Isso ajuda a ver o erro exato no console do Docker
            return JsonResponse({'erro': str(e)}, status=500)
            
    # Se for GET, apenas renderiza a página
    return render(request, 'leads/integracoes.html')

import pandas as pd # Adicione isso no topo do arquivo se já não tiver
from django.http import HttpResponse

def download_modelo_google_view(request):
    # 1. Cria a estrutura da planilha com as colunas exatas
    df = pd.DataFrame(columns=['Serviço', 'Cidade', 'Estado'])
    
    # 2. Adiciona dados de exemplo para o usuário entender como preencher
    df.loc[0] = ['Provedor de Internet', 'Fortaleza', 'CE']
    df.loc[1] = ['Link Dedicado', 'Eusébio', 'CE']
    
    # 3. Prepara a resposta HTTP avisando que é um arquivo Excel
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="Modelo_Busca_Google.xlsx"'
    
    # 4. Salva os dados direto na resposta (sem criar arquivo no HD do servidor)
    df.to_excel(response, index=False)
    
    return response    