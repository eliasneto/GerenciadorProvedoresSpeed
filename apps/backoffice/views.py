from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import pandas as pd
from django.http import HttpResponse
from io import BytesIO

@login_required
def cotacao_import(request):
    if request.method == 'POST' and request.FILES.get('arquivo_cotacao'):
        arquivo = request.FILES['arquivo_cotacao']
        
        try:
            df = pd.read_excel(arquivo)
            sucessos = 0
            erros = 0

            for _, linha in df.iterrows():
                # Aqui você chama a sua função de integração (cadastrar_login)
                # Dica: Passe o TOKEN e URL_BASE das suas variáveis de ambiente ou settings
                resultado = cadastrar_login_no_ixc(linha) 
                if resultado: sucessos += 1
                else: erros += 1

            messages.success(request, f"Processamento concluído! {sucessos} logins criados, {erros} falhas.")
        except Exception as e:
            messages.error(request, f"Erro ao processar planilha: {str(e)}")
            
        return redirect('backoffice:cotacao_import')

    return render(request, 'backoffice/cotacao_import.html')

@login_required
def download_modelo_cotacao(request):
    # Colunas que o seu script de integração já espera
    colunas = [
        'Cliente_ID', 'Login_Contrato_ID', 'Plano_ID', 'Login_Login', 
        'Login_Senha_Cliente', 'End_CEP', 'End_Bairro', 'End_Cidade', 
        'End_Logradouro', 'End_Numero', 'End_Referencia', 'Obs_Cliente'
    ]
    
    # Cria um DataFrame vazio apenas com os cabeçalhos
    df = pd.DataFrame(columns=colunas)
    
    # Prepara o arquivo Excel em memória
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Modelo_Importacao')
    
    output.seek(0)
    
    # Monta a resposta do navegador para download
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=modelo_importacao_ixc.xlsx'
    
    return response