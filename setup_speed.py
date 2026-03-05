import os
import sys
import django
from django.core.management import call_command

# 1. Garante que o Python reconheça a pasta atual como raiz do projeto
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 2. CONFIGURAÇÃO CORRETA DA SPEED
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

def inicializar_sistema():
    print("🚀 Iniciando o Motor da Speed...")
    
    try:
        django.setup()
    except Exception as e:
        print(f"❌ Erro ao carregar o Django. Erro: {e}")
        return

    from django.contrib.auth import get_user_model
    User = get_user_model()

    print("🔍 Procurando novas alterações no banco de dados...")
    call_command('makemigrations')

    print("📦 Aplicando migrações e criando tabelas...")
    call_command('migrate')
    
    print("👤 Verificando acesso administrativo...")
    
    # Credenciais padrão (Focadas em EMAIL agora)
    admin_email = 'admin@speed.com.br'
    admin_pass = 'speed@admin2026'

    # Busca pelo EMAIL, já que o username não existe no seu model
    if not User.objects.filter(email=admin_email).exists():
        print(f"⚙️ Criando superusuário com e-mail '{admin_email}'...")
        # Cria passando o email como identificador principal
        User.objects.create_superuser(email=admin_email, password=admin_pass)
        print(f"✅ Administrador criado com sucesso!")
        print(f"🔑 Login: {admin_email}")
        print(f"🔑 Senha: {admin_pass}")
    else:
        print(f"⚠️ O administrador '{admin_email}' já existe no banco. Pulando criação.")

    print("✨ Sistema Speed 100% inicializado e pronto para uso!")

if __name__ == '__main__':
    inicializar_sistema()