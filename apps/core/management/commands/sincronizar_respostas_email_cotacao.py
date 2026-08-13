from django.core.management.base import BaseCommand

from apps.integracoes.email.sincronizar_respostas_email_cotacao import main

# Antes scripts/integracoes/sincronizar_respostas_email_cotacao.py (PO-033/034).


class Command(BaseCommand):
    help = "Sincroniza respostas de e-mail das cotacoes (Microsoft Graph)."

    def handle(self, *args, **options):
        main()
