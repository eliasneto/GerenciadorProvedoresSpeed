from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from io import BytesIO
import pandas as pd

# 🚀 IMPORTAÇÃO DO SEU SCRIPT DE INTEGRAÇÃO
from scripts.integracoes.backoffice.cria_login_atendimento import executar_cadastro_ixc

@login_required
def cotacao_import(request):
    if request.method == 'POST' and request.FILES.get('arquivo_cotacao'):
        arquivo = request.FILES['arquivo_cotacao']
        
        try:
            # 1. Lê a planilha original que o usuário enviou
            df = pd.read_excel(arquivo)
            
            # 🚀 NOVIDADE: Criamos duas colunas em branco no final da planilha
            df['Status_Importacao'] = ''
            df['Mensagem_Importacao'] = ''
            
            sucessos = 0
            falhas = 0

            # 2. Varre as linhas e chama a integração
            # Usamos df.iterrows() pegando o 'index' para poder escrever na linha certa
            for index, linha in df.iterrows():
                if pd.notna(linha.get('Login_Login')):
                    # CHAMA A FUNÇÃO QUE ESTÁ NO SCRIPT EXTERNO (Ele continua intacto!)
                    status, mensagem = executar_cadastro_ixc(linha)
                    
                    # 🚀 NOVIDADE: Salva o resultado direto na linha da planilha
                    if status:
                        sucessos += 1
                        df.at[index, 'Status_Importacao'] = 'SUCESSO'
                    else:
                        falhas += 1
                        df.at[index, 'Status_Importacao'] = 'ERRO'
                        
                    # Escreve o detalhe do erro ou ID gerado na última coluna
                    df.at[index, 'Mensagem_Importacao'] = mensagem

            # 3. Adiciona uma mensagem na tela avisando do resultado geral
            messages.info(request, f"Processamento concluído! {sucessos} Sucessos | {falhas} Erros. O relatório foi baixado automaticamente.")

            # 🚀 NOVIDADE: Transforma o DataFrame de volta em Excel para o usuário baixar
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Resultado_Processamento')
                
                # Ajusta a largura das colunas para ficar bonito de ler
                worksheet = writer.sheets['Resultado_Processamento']
                for col_num, value in enumerate(df.columns.values):
                    worksheet.set_column(col_num, col_num, 22)

            output.seek(0)
            
            # Configura a resposta do servidor para forçar o download do arquivo
            response = HttpResponse(
                output.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename=Relatorio_Importacao_IXC.xlsx'
            
            # Ao invés de redirecionar a página, ele devolve o ARQUIVO para download!
            return response

        except Exception as e:
            messages.error(request, f"Erro ao processar planilha: {str(e)}")
            return redirect('backoffice:cotacao_import')

    # Se não for POST, apenas renderiza a tela normalmente
    return render(request, 'backoffice/cotacao_import.html')


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
            'O nome de usuário PPPoE (Ex: joao_silva)',
            'A senha do login (Ex: 123456)',
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
    
    # Criando o arquivo com duas abas
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_modelo.to_excel(writer, index=False, sheet_name='Preencher_Aqui')
        df_ajuda.to_excel(writer, index=False, sheet_name='Instrucoes_Ajuda')
        
        # Ajuste de largura das colunas para ficar bonito
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