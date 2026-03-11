# apps/leads/apps.py
from django.apps import AppConfig

class LeadsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'leads'
    verbose_name = 'Prospecção'

    def ready(self):
        # Import relativo: busca o signals.py NA MESMA PASTA deste apps.py
        from . import signals