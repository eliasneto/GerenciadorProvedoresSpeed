# arquivo setup_speed.py
import os
import sys
import time

import django
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connections
from django.db.utils import OperationalError


# 1. Garante que o Python reconheca a pasta atual como raiz do projeto
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 2. Configuracao correta da Speed
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def validar_repositorio_e_migrations():
    if os.getenv("SKIP_DEPLOY_VALIDATIONS", "").strip().lower() in {"1", "true", "yes"}:
        print("Validacoes de deploy ignoradas por SKIP_DEPLOY_VALIDATIONS.")
        return

    print("Validando integridade do codigo antes do deploy...")

    try:
        call_command("makemigrations", check=True, dry_run=True, verbosity=0)
    except (SystemExit, CommandError) as exc:
        print("Falha de validacao: existem models sem migration versionada.")
        print("Gere e versione as migrations antes de subir a aplicacao.")
        print(f"Detalhe tecnico: {exc}")
        sys.exit(1)
    except Exception as exc:
        print("Falha inesperada ao validar migrations do projeto.")
        print(f"Detalhe tecnico: {exc}")
        sys.exit(1)

    print("Validacao de migrations concluida com sucesso.")


def obter_env_int(nome_variavel, padrao):
    valor_bruto = os.getenv(nome_variavel, "")
    valor_limpo = str(valor_bruto).strip()

    if not valor_limpo:
        return padrao

    try:
        return int(valor_limpo)
    except ValueError:
        print(
            f"Valor invalido para {nome_variavel}: {valor_bruto!r}. "
            f"Usando o padrao {padrao}."
        )
        return padrao


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
    tempo_limite = obter_env_int("DB_STARTUP_TIMEOUT", 180)
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

    validar_repositorio_e_migrations()

    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group

    User = get_user_model()

    print("Aplicando migracoes e criando tabelas...")
    call_command("migrate")

    print("Executando checagens finais do Django...")
    call_command("check", verbosity=0)

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

    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_email = os.getenv("ADMIN_EMAIL", "admin@speed.com.br")
    admin_pass = os.getenv("ADMIN_PASSWORD", "SpeedAdmin!2026#Prod")

    admin_user, criado = User.objects.get_or_create(
        username=admin_username,
        defaults={
            "email": admin_email,
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        },
    )

    alteracoes = []

    if criado:
        print(f"Criando superusuario '{admin_username}'...")
    else:
        print(f"O administrador '{admin_username}' ja existe no banco. Sincronizando credenciais e permissoes...")

    if admin_email and admin_user.email != admin_email:
        admin_user.email = admin_email
        alteracoes.append("email")

    if not admin_user.is_staff:
        admin_user.is_staff = True
        alteracoes.append("is_staff")

    if not admin_user.is_superuser:
        admin_user.is_superuser = True
        alteracoes.append("is_superuser")

    if not admin_user.is_active:
        admin_user.is_active = True
        alteracoes.append("is_active")

    if admin_pass:
        admin_user.set_password(admin_pass)
        alteracoes.append("password")

    if criado or alteracoes:
        admin_user.save()
        print("Administrador sincronizado com sucesso!")
        print(f"Login: {admin_username}")
        print(f"Senha: {admin_pass}")
    else:
        print(f"O administrador '{admin_username}' ja estava alinhado com o .env.")

    print("Sistema Speed 100% inicializado e pronto para uso no MySQL!")


if __name__ == "__main__":
    inicializar_sistema()
