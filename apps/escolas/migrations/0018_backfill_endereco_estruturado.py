from django.db import migrations

from apps.escolas.services import extrair_endereco_estruturado


def backfill_endereco_estruturado(apps, schema_editor):
    """RN-051/PO-072: preenche Logradouro/Numero/Bairro/CEP nas Escolas ja
    existentes, extraindo do texto livre de `endereco_descricao` (melhor
    esforco — `extrair_endereco_estruturado` e uma funcao pura de texto,
    sem dependencia do estado historico do model)."""
    Escola = apps.get_model("escolas", "Escola")
    for escola in Escola.objects.exclude(endereco_descricao="").iterator():
        estruturado = extrair_endereco_estruturado(escola.endereco_descricao)
        if any(estruturado.values()):
            for campo, valor in estruturado.items():
                setattr(escola, campo, valor)
            escola.save(update_fields=["logradouro", "numero", "bairro", "cep"])


def reverter_backfill(apps, schema_editor):
    # Irreversivel de forma segura (mesmo precedente da 0003): os campos
    # continuam existindo, so voltam a ficar em branco.
    Escola = apps.get_model("escolas", "Escola")
    Escola.objects.update(logradouro="", numero="", bairro="", cep="")


class Migration(migrations.Migration):

    dependencies = [
        ('escolas', '0017_campos_estruturados_endereco'),
    ]

    operations = [
        migrations.RunPython(backfill_endereco_estruturado, reverter_backfill),
    ]
