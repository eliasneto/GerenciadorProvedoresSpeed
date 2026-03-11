import subprocess
import os
import sys # <--- Adicione este import
from django.conf import settings

def disparar_robo(automacao):
    caminho_script = os.path.join(settings.BASE_DIR, 'scripts', 'automacoes', automacao.pasta_script, 'main.py')
    
    if not os.path.exists(caminho_script):
        return False, "Arquivo main.py não encontrado."

    try:
        arquivo_path = automacao.arquivo_entrada.path if automacao.arquivo_entrada else ""
        
        # sys.executable garante que usaremos o Python da sua .venv
        python_executavel = sys.executable 

        subprocess.Popen([
            python_executavel, 
            caminho_script, 
            '--input', arquivo_path,
            '--id', str(automacao.id)
        ])
        
        return True, "Execução iniciada."
    except Exception as e:
        return False, str(e)