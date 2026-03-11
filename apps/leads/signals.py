# apps/leads/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from leads.models import Lead 
from partners.models import Partner

@receiver(post_save, sender=Lead)
def move_lead_to_partner(sender, instance, created, **kwargs):
    # Agora o gatilho é 'pendente' (Em Andamento)
    if instance.status == 'andamento':
        
        # Cria o registro na tabela de Parceiros
        Partner.objects.get_or_create(
            cnpj_cpf=instance.cnpj_cpf,
            defaults={
                'razao_social': instance.razao_social,
                'nome_fantasia': instance.nome_fantasia,
                'contato_nome': instance.contato_nome,
                'email': instance.email,
                'telefone': instance.telefone,
            }
        )
        
        # Remove da Prospecção imediatamente
        instance.delete()