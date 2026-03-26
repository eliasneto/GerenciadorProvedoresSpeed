# arquivo setup_speed.py
import os
import sys
import time
import django
from django.core.management import call_command
from django.db import connections
from django.db.utils import OperationalError

# 1. Garante que o Python reconheça a pasta atual como raiz do projeto
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 2. CONFIGURAÇÃO CORRETA DA SPEED
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

def inicializar_sistema():
    print("Iniciando o Motor da Speed...")
    
    try:
        django.setup()
    except Exception as e:
        print(f"Erro ao carregar o Django. Erro: {e}")
        return

    # =========================================================
    # PAUSA ESTRATÉGICA: Espera o MySQL acordar (Impede o loop)
    # =========================================================
    print("Aguardando o banco de dados MySQL ficar pronto...")
    db_conn = connections['default']
    tempo_limite = 30  # Espera até 30 segundos
    while tempo_limite > 0:
        try:
            db_conn.cursor()
            print("Banco de dados online e aceitando conexões!")
            break
        except OperationalError:
            print("Banco de dados ainda iniciando. Tentando novamente em 2 segundos...")
            time.sleep(2)
            tempo_limite -= 2
    else:
        print("Falha crítica: O banco de dados não respondeu a tempo.")
        sys.exit(1)
    # =========================================================

    from django.contrib.auth import get_user_model
    User = get_user_model()

    print("Procurando novas alterações no banco de dados...")
    call_command('makemigrations')

    print("Aplicando migrações e criando tabelas...")
    call_command('migrate')
    
    print("Empacotando arquivos visuais (CSS/JS)...")
    call_command('collectstatic', interactive=False)
    
    print("Verificando acesso administrativo...")

    # Credenciais padrão atualizadas para aceitar USERNAME
    admin_username = 'admin'
    admin_email = 'admin@speed.com.br'
    admin_pass = 'speed@admin2026'

    # Busca pelo USERNAME
    if not User.objects.filter(username=admin_username).exists():
        print(f"Criando superusuário '{admin_username}'...")
        User.objects.create_superuser(username=admin_username, email=admin_email, password=admin_pass)
        print(f"Administrador criado com sucesso!")
        print(f"Login: {admin_username}")
        print(f"Senha: {admin_pass}")
    else:
        print(f"O administrador '{admin_username}' já existe no banco. Pulando criação.")

    print("✨ Sistema Speed 100% inicializado e pronto para uso no MySQL!")

if __name__ == '__main__':
    inicializar_sistema()