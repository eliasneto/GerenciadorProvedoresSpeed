# arquivo setup_speed.py
import os
import sys
import time

import django
from django.core.management import call_command
from django.db import connections
from django.db.utils import OperationalError


# 1. Garante que o Python reconheca a pasta atual como raiz do projeto
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 2. Configuracao correta da Speed
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def inicializar_sistema():
    print("Iniciando o Motor da Speed...")

    try:
        django.setup()
    except Exception as e:
        print(f"Erro ao carregar o Django. Erro: {e}")
        return

    # Espera o MySQL responder antes de seguir com migrations e collectstatic.
    print("Aguardando o banco de dados MySQL ficar pronto...")
    db_conn = connections["default"]
    tempo_limite = int(os.getenv("DB_STARTUP_TIMEOUT", "180"))
    while tempo_limite > 0:
        try:
            db_conn.cursor()
            print("Banco de dados online e aceitando conexoes!")
            break
        except OperationalError:
            print("Banco de dados ainda iniciando. Tentando novamente em 2 segundos...")
            time.sleep(2)
            tempo_limite -= 2
    else:
        print("Falha critica: O banco de dados nao respondeu a tempo.")
        sys.exit(1)

    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group

    User = get_user_model()

    print("Aplicando migracoes e criando tabelas...")
    call_command("migrate")

    print("Empacotando arquivos visuais (CSS/JS)...")
    call_command("collectstatic", interactive=False)

    print("Garantindo grupos padrao da aplicacao...")
    grupos_padrao = [
        "Administrador",
        "LastMile",
        "Parceiro",
        "Backoffice",
        "Gestao",
    ]
    for nome_grupo in grupos_padrao:
        _, criado = Group.objects.get_or_create(name=nome_grupo)
        if criado:
            print(f"Grupo criado: {nome_grupo}")
        else:
            print(f"Grupo ja existe: {nome_grupo}")

    print("Verificando acesso administrativo...")

    admin_username = "admin"
    admin_email = "admin@speed.com.br"
    admin_pass = "speed@admin2026"

    if not User.objects.filter(username=admin_username).exists():
        print(f"Criando superusuario '{admin_username}'...")
        User.objects.create_superuser(
            username=admin_username,
            email=admin_email,
            password=admin_pass,
        )
        print("Administrador criado com sucesso!")
        print(f"Login: {admin_username}")
        print(f"Senha: {admin_pass}")
    else:
        print(f"O administrador '{admin_username}' ja existe no banco. Pulando criacao.")

    print("Sistema Speed 100% inicializado e pronto para uso no MySQL!")


if __name__ == "__main__":
    inicializar_sistema()
