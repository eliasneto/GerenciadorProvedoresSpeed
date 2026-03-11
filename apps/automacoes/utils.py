import os
from django.conf import settings
from .models import Automacao
from django.utils.text import slugify

def sincronizar_automacoes():
    """
    Varre a pasta scripts/automacoes e cadastra no banco as pastas encontradas.
    """
    caminho_base = os.path.join(settings.BASE_DIR, 'scripts', 'automacoes')
    
    if not os.path.exists(caminho_base):
        os.makedirs(caminho_base)
        return

    pastas = [d for d in os.listdir(caminho_base) if os.path.isdir(os.path.join(caminho_base, d))]

    for nome_pasta in pastas:
        slug = slugify(nome_pasta)
        # Se não existe no banco, cria com o status PARADO
        Automacao.objects.get_or_create(
            slug=slug,
            defaults={
                'nome': nome_pasta.replace('_', ' ').title(),
                'pasta_script': nome_pasta,
                'status': 'PARADO',
                'descricao': f'Automação localizada na pasta {nome_pasta}'
            }
        )