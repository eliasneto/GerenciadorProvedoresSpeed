from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.http import HttpResponse
from io import BytesIO
import pandas as pd

# 🚀 IMPORTAÇÕES DOS SCRIPTS DE INTEGRAÇÃO
from scripts.integracoes.backoffice.cria_login_atendimento import executar_cadastro_ixc
from scripts.integracoes.backoffice.cria_atendimento_ixc import executar_abertura_atendimento

# 1. Cria a regra de verificação
def grupo_backoffice_required(user):
    if not user.is_authenticated:
        return False
    # O Superuser (você) sempre passa. Os outros precisam estar no grupo.
    if user.groups.filter(name='Backoffice').exists() or user.is_superuser:
        return True
    # Se não for do grupo, joga um Erro 403 (Acesso Negado)
    raise PermissionDenied

@user_passes_test(grupo_backoffice_required)
@login_required
def cotacao_import(request):
    if request.method == 'POST' and request.FILES.get('arquivo_cotacao'):
        arquivo = request.FILES['arquivo_cotacao']
        
        try:
            # 1. Lê a folha de cálculo original que o utilizador enviou
            df = pd.read_excel(arquivo)
            
            # 🚀 NOVIDADE: Criamos duas colunas em branco no final da folha
            df['Status_Importacao'] = ''
            df['Mensagem_Importacao'] = ''
            
            sucessos = 0
            falhas = 0

            # 2. Varre as linhas e chama a integração
            for index, linha in df.iterrows():
                if pd.notna(linha.get('Login_Login')):
                    # CHAMA A FUNÇÃO DE LOGINS
                    status, mensagem = executar_cadastro_ixc(linha)
                    
                    if status:
                        sucessos += 1
                        df.at[index, 'Status_Importacao'] = 'SUCESSO'
                    else:
                        falhas += 1
                        df.at[index, 'Status_Importacao'] = 'ERRO'
                        
                    df.at[index, 'Mensagem_Importacao'] = mensagem

            # 3. Adiciona uma mensagem no ecrã avisando do resultado geral
            messages.info(request, f"Processamento concluído! {sucessos} Sucessos | {falhas} Erros. O relatório foi transferido automaticamente.")

            # Transforma o DataFrame de volta em Excel para o utilizador transferir
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Resultado_Processamento')
                
                # Ajusta a largura das colunas
                worksheet = writer.sheets['Resultado_Processamento']
                for col_num, value in enumerate(df.columns.values):
                    worksheet.set_column(col_num, col_num, 22)

            output.seek(0)
            
            response = HttpResponse(
                output.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename=Relatorio_Importacao_IXC.xlsx'
            
            return response

        except Exception as e:
            messages.error(request, f"Erro ao processar ficheiro: {str(e)}")
            return redirect('backoffice:cotacao_import')

    return render(request, 'backoffice/cotacao_import.html')

@user_passes_test(grupo_backoffice_required)
@login_required
def download_modelo_cotacao(request):
    # 1. Colunas para preenchimento (Aba Principal)
    colunas = [
        'Cliente_ID', 'Login_Contrato_ID', 'Plano_ID', 'Login_Login', 
        'Login_Senha_Cliente', 'End_CEP', 'End_Bairro', 'End_Cidade', 
        'End_Logradouro', 'End_Numero', 'End_Referencia', 'Obs_Cliente'
    ]
    
    # 2. Dados de Exemplo/Instruções (Aba de Ajuda)
    instrucoes = {
        'Campo': colunas,
        'O que colocar?': [
            'ID do Cliente no IXC (Ex: 55)',
            'ID do Contrato do Cliente (Ex: 1151)',
            'ID do Plano de Velocidade (Ex: 4)',
            'O nome de utilizador PPPoE (Ex: joao_silva)',
            'A palavra-passe do login (Ex: 123456)',
            'CEP sem traço (Ex: 60346165)',
            'Nome do Bairro',
            'Código da Cidade no IXC (Ex: 948)',
            'Rua/Avenida',
            'Número da residência',
            'Ponto de referência',
            'Alguma observação importante'
        ],
        'Obrigatório?': ['Sim', 'Sim', 'Sim', 'Sim', 'Sim', 'Sim', 'Sim', 'Sim', 'Sim', 'Sim', 'Não', 'Não']
    }

    df_modelo = pd.DataFrame(columns=colunas)
    df_ajuda = pd.DataFrame(instrucoes)
    
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_modelo.to_excel(writer, index=False, sheet_name='Preencher_Aqui')
        df_ajuda.to_excel(writer, index=False, sheet_name='Instrucoes_Ajuda')
        
        workbook = writer.book
        worksheet_modelo = writer.sheets['Preencher_Aqui']
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
        
        for col_num, value in enumerate(df_modelo.columns.values):
            worksheet_modelo.write(0, col_num, value, header_format)
            worksheet_modelo.set_column(col_num, col_num, 20)

    output.seek(0)
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=modelo_importacao_ixc.xlsx'
    return response


# ==========================================
# NOVA AUTOMAÇÃO: IMPORTAÇÃO DE ATENDIMENTOS (OS)
# ==========================================
@user_passes_test(grupo_backoffice_required)
@login_required
def download_modelo_atendimento(request):
    colunas = [
        'Cliente_ID', 'Login_ID','Contrato_ID', 'Filial_ID', 'Assunto_ID', 
        'Departamento_ID', 'Assunto_Descricao', 'Descricao'
    ]
    df = pd.DataFrame(columns=colunas)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Modelo_OS')
        
    output.seek(0)
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=Modelo_Importacao_OS_IXC.xlsx'
    return response

@user_passes_test(grupo_backoffice_required)
@login_required
def atendimento_import(request):
    if request.method == 'POST' and request.FILES.get('arquivo_atendimento'):
        arquivo = request.FILES['arquivo_atendimento']
        
        try:
            # 🚀 BLINDAGEM CONTRA ACENTOS E ARQUIVOS FALSOS
            if arquivo.name.lower().endswith('.csv'):
                try:
                    # Tenta ler normal (UTF-8)
                    df = pd.read_csv(arquivo, sep=None, engine='python', encoding='utf-8')
                except UnicodeDecodeError:
                    # Se engasgar com acento, lê no formato do Excel do Windows (Latin1)
                    arquivo.seek(0)
                    df = pd.read_csv(arquivo, sep=None, engine='python', encoding='latin1')
            else:
                try:
                    # Tenta ler como Excel
                    df = pd.read_excel(arquivo)
                except ValueError:
                    # Se o Excel for um CSV disfarçado
                    arquivo.seek(0)
                    try:
                        df = pd.read_csv(arquivo, sep=None, engine='python', encoding='utf-8')
                    except UnicodeDecodeError:
                        arquivo.seek(0)
                        df = pd.read_csv(arquivo, sep=None, engine='python', encoding='latin1')
                    
            df['Status_Importacao'] = ''
            df['Mensagem_Importacao'] = ''
            
            for index, linha in df.iterrows():
                if pd.notna(linha.get('Cliente_ID')):
                    # CHAMA A FUNÇÃO DE ABERTURA DE OS
                    status, mensagem = executar_abertura_atendimento(linha)
                    
                    if status:
                        df.at[index, 'Status_Importacao'] = 'SUCESSO'
                    else:
                        df.at[index, 'Status_Importacao'] = 'ERRO'
                        
                    df.at[index, 'Mensagem_Importacao'] = mensagem

            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Resultado_OS')
                worksheet = writer.sheets['Resultado_OS']
                for col_num, value in enumerate(df.columns.values):
                    worksheet.set_column(col_num, col_num, 22)

            output.seek(0)
            response = HttpResponse(
                output.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename=Relatorio_OS_IXC.xlsx'
            return response

        except Exception as e:
            # 🚀 RAIO-X DO ERRO INTERNO:
            print(f"\n--- 🔴 ERRO GRAVE NO VIEWS.PY (OS) ---")
            print(f"Motivo: {str(e)}")
            print("--------------------------------------\n")
            return HttpResponse(status=400)
            
    return redirect('backoffice:cotacao_import')

