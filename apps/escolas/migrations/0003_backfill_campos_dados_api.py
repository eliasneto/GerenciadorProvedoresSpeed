from django.db import migrations


def backfill_campos_promovidos(apps, schema_editor):
    Escola = apps.get_model("escolas", "Escola")
    for escola in Escola.objects.all().iterator():
        dados = escola.dados_api or {}
        atualizado = False

        if not escola.inep and dados.get("inep"):
            escola.inep = dados["inep"]
            atualizado = True
        if not escola.nome and dados.get("nome"):
            escola.nome = dados["nome"]
            atualizado = True
        if not escola.municipio and dados.get("municipio"):
            escola.municipio = dados["municipio"]
            atualizado = True
        if not escola.endereco_descricao and dados.get("descricao"):
            escola.endereco_descricao = dados["descricao"]
            atualizado = True

        if atualizado:
            escola.save(update_fields=["inep", "nome", "municipio", "endereco_descricao"])


def reverter_backfill(apps, schema_editor):
    # Irreversivel de forma segura (nao sabemos quais valores eram None antes
    # do backfill); nao ha necessidade real de reverter, os campos continuam
    # existindo. Noop deliberado.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('escolas', '0002_escola_endereco_descricao_escola_inep_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_campos_promovidos, reverter_backfill),
    ]
