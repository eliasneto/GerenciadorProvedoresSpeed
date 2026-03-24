from django import template

register = template.Library()

@register.filter(name='has_group')
def has_group(user, group_name):
    """Verifica se o usuário pertence a um grupo específico."""
    if not user.is_authenticated:
        return False
        
    # Verifica no banco de dados se ele tem o grupo
    tem_grupo = user.groups.filter(name=group_name).exists()
    
    # DEDO-DURO: Vai imprimir a verdade no seu terminal do Docker!
    print(f"\n--- DEBUG DE MENU: {user.username} ---")
    print(f"Verificando a aba: {group_name}")
    print(f"O Django achou o grupo no banco? {tem_grupo}")
    print(f"O Django acha que ele é Superuser? {user.is_superuser}")
    print(f"Grupos reais dele: {list(user.groups.values_list('name', flat=True))}")
    print("--------------------------------------\n")
    
    # Retornamos APENAS a validação do grupo (sem a trava do superuser por enquanto)
    return tem_grupo