# apps/partners/apps.py
from django.apps import AppConfig

class PartnersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'partners'

    def ready(self):
        # Deixe vazio ou remova a linha de import leads.signals
        pass