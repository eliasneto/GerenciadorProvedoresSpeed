from django.db import migrations


SLUGS_BACKOFFICE = ["cotacao_import", "atendimento_import"]


def corrigir_menu_backoffice(apps, schema_editor):
    AutomacaoMenu = apps.get_model("core_admin", "AutomacaoMenu")
    AutomacaoMenu.objects.filter(slug__in=SLUGS_BACKOFFICE).update(menu="backoffice")


def reverter_menu_administrador(apps, schema_editor):
    AutomacaoMenu = apps.get_model("core_admin", "AutomacaoMenu")
    AutomacaoMenu.objects.filter(slug__in=SLUGS_BACKOFFICE).update(menu="administrador")


class Migration(migrations.Migration):

    dependencies = [
        ("core_admin", "0006_seed_automacoes_backoffice"),
    ]

    operations = [
        migrations.RunPython(corrigir_menu_backoffice, reverter_menu_administrador),
    ]
