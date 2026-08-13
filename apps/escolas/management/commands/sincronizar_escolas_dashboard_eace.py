from django.core.management.base import BaseCommand

from apps.escolas.services import sincronizar_escolas


class Command(BaseCommand):
    help = "Sincroniza Escola a partir do DashboardEACE (GET /escolas). Disparo manual (ADR-010, sem agendamento)."

    def add_arguments(self, parser):
        parser.add_argument("--uf", default=None, help="Filtra por UF (ex.: SP).")
        parser.add_argument("--status-escola", default=None, help="Filtra por status_escola (ex.: Conectado).")

    def handle(self, *args, **options):
        total, erro = sincronizar_escolas(uf=options["uf"], status_escola=options["status_escola"])

        if erro:
            self.stderr.write(self.style.ERROR(erro))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS(f"{total} escola(s) sincronizada(s) a partir do DashboardEACE."))
