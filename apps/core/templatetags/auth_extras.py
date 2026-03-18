from django import template
from django.contrib.auth.models import Group

register = template.Library()

@register.filter(name='has_group')
def has_group(user, group_name):
    """
    Filtro para verificar se o usuário pertence a um grupo específico.
    Uso no HTML: {% if user|has_group:"NomeDoGrupo" %}
    """
    return user.groups.filter(name=group_name).exists()