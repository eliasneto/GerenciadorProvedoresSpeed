import pandas as pd
from django.shortcuts import render, redirect
from django.contrib import messages
from partners.models import Partner
from .forms import ExcelUploadForm
import pandas as pd
from django.http import HttpResponse
from io import BytesIO

def import_prospects(request):
    if request.method == 'POST':
        form = ExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            
            try:
                # Lendo a planilha (funciona para Excel e CSV)
                if file.name.endswith('.csv'):
                    df = pd.read_csv(file)
                else:
                    df = pd.read_excel(file)

                df = df.fillna('') # Remove valores nulos para não quebrar o Django
                
                success_count = 0
                for _, row in df.iterrows():
                    # Mapeamento das colunas da planilha para o Model
                    # Ajuste os nomes entre [''] conforme os cabeçalhos da sua planilha
                    Partner.objects.update_or_create(
                        cnpj_cpf=str(row['CNPJ']).strip(), # Chave única para evitar duplicados
                        defaults={
                            'razao_social': row['Razao Social'],
                            'nome_fantasia': row.get('Nome Fantasia', ''),
                            'contato_nome': row.get('Contato', 'A definir'),
                            'email': row.get('Email', 'import@ageis.com'),
                            'telefone': str(row.get('Telefone', '')),
                            'status': 'inativo', # Já entra fora da base ativa
                        }
                    )
                    success_count += 1
                
                messages.success(request, f'Sucesso! {success_count} prospectos importados/atualizados.')
                return redirect('partner_list')

            except Exception as e:
                messages.error(request, f'Erro ao processar: {str(e)}')
    else:
        form = ExcelUploadForm()
    
    return render(request, 'core_admin/import_form.html', {'form': form})



def download_template(request):
    # Definimos as colunas exatamente como o importador vai ler
    columns = [
        'CNPJ_CPF', 'RAZAO_SOCIAL', 'NOME_FANTASIA', 
        'CONTATO_NOME', 'EMAIL', 'TELEFONE'
    ]
    
    # Criamos um DataFrame vazio apenas com os cabeçalhos
    df = pd.DataFrame(columns=columns)
    
    # Exemplo de preenchimento para orientar o usuário
    df.loc[0] = ['00.000.000/0001-00', 'Empresa Exemplo LTDA', 'Exemplo Telecom', 'João Silva', 'contato@exemplo.com', '(85) 99999-9999']

    # Gerando o arquivo na memória (BytesIO)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Importar_Cotacao')
    
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=modelo_importacao_ageis.xlsx'
    
    return response


def import_prospects(request):
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        
        try:
            # Lendo a planilha (Pandas é vida!)
            df = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)
            
            # Normalização: remove espaços e garante que as colunas sejam strings
            df.columns = [c.strip().upper() for c in df.columns]
            df = df.fillna('')

            created_count = 0
            updated_count = 0

            for _, row in df.iterrows():
                # Chave primária de negócio: CNPJ/CPF
                cnpj = str(row['CNPJ_CPF']).strip()
                
                # O update_or_create é o porto seguro do dev Django
                obj, created = Partner.objects.update_or_create(
                    cnpj_cpf=cnpj,
                    defaults={
                        'razao_social': row['RAZAO_SOCIAL'],
                        'nome_fantasia': row.get('NOME_FANTASIA', ''),
                        'contato_nome': row.get('CONTATO_NOME', 'A definir'),
                        'email': row.get('EMAIL', 'import@ageis.com'),
                        'telefone': str(row.get('TELEFONE', '')),
                        'status': 'inativo' # Garante que entre fora da base ativa
                    }
                )
                
                if created: created_count += 1
                else: updated_count += 1

            messages.success(request, f'Processamento concluído: {created_count} novos e {updated_count} atualizados.')
            return redirect('partner_list')

        except Exception as e:
            messages.error(request, f'Erro crítico na planilha: {str(e)}')
            
    return render(request, 'core_admin/import_form.html')
