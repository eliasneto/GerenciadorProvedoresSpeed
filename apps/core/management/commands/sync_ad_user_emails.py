from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q

from core.ad_sync import ADDirectoryClient, sincronizar_email_usuario


class Command(BaseCommand):
    help = "Sincroniza o e-mail dos usuarios locais com o AD."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            dest="username",
            help="Sincroniza apenas um usuario especifico.",
        )
        parser.add_argument(
            "--only-empty",
            action="store_true",
            help="Sincroniza apenas usuarios sem e-mail salvo.",
        )
        parser.add_argument(
            "--debug-username",
            dest="debug_username",
            help="Exibe os atributos LDAP encontrados para um usuario especifico.",
        )

    def handle(self, *args, **options):
        username = (options.get("username") or "").strip()
        debug_username = (options.get("debug_username") or "").strip()
        only_empty = options.get("only_empty", False)

        client = ADDirectoryClient()
        if not client.ready():
            self.stderr.write(
                self.style.ERROR(
                    "LDAP/AD nao esta disponivel neste ambiente ou faltam variaveis AD_SERVER_URI, AD_BIND_DN ou AD_USER_SEARCH_BASE."
                )
            )
            return

        if debug_username:
            dn, attrs = client.buscar_usuario(debug_username)
            try:
                if not dn:
                    self.stdout.write(self.style.WARNING(f"{debug_username}: usuario_nao_encontrado_no_ldap"))
                    return

                self.stdout.write(self.style.SUCCESS(f"DN: {dn}"))
                for chave in sorted(attrs.keys(), key=lambda item: str(item).lower()):
                    valores = attrs.get(chave) or []
                    valores_texto = []
                    for valor in valores:
                        if isinstance(valor, bytes):
                            try:
                                valores_texto.append(valor.decode("utf-8"))
                            except Exception:
                                valores_texto.append(valor.decode("latin1", errors="ignore"))
                        else:
                            valores_texto.append(str(valor))
                    self.stdout.write(f"{chave}: {valores_texto}")
                return
            finally:
                client.close()

        User = get_user_model()
        queryset = User.objects.all().order_by("username")

        if username:
            queryset = queryset.filter(username__iexact=username)
        if only_empty:
            queryset = queryset.filter(Q(email__isnull=True) | Q(email=""))

        total = 0
        atualizados = 0
        ignorados = 0

        try:
            for user in queryset:
                total += 1
                atualizado, resultado = sincronizar_email_usuario(user, client=client)
                if atualizado:
                    atualizados += 1
                    self.stdout.write(self.style.SUCCESS(f"{user.username}: e-mail atualizado para {resultado}"))
                else:
                    ignorados += 1
                    self.stdout.write(f"{user.username}: {resultado}")
        finally:
            client.close()

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Sincronizacao concluida. Total: {total} | Atualizados: {atualizados} | Ignorados: {ignorados}"
            )
        )
