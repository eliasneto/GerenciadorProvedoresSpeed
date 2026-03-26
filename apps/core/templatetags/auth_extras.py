from django import template

register = template.Library()

@register.filter(name='has_group')
def has_group(user, group_name):
    """Verifica se o usuário pertence a um grupo ou se é o dono do sistema."""
    if not user.is_authenticated:
        return False
        
    # SE FOR SUPERUSER (Admin) OU SE TIVER O GRUPO, RETORNA TRUE!
    return user.groups.filter(name=group_name).exists() or user.is_superuser