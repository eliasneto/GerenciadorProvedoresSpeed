from django.db import migrations


AUTOMACOES_INICIAIS = [
    {
        "slug": "cotacao_import",
        "nome_exibicao": "Logins IXC",
        "url_name": "backoffice:cotacao_import",
        "icone": "database",
        "ordem": 7,
    },
    {
        "slug": "atendimento_import",
        "nome_exibicao": "Atendimento IXC",
        "url_name": "backoffice:atendimento_import",
        "icone": "headphones",
        "ordem": 8,
    },
    {
        "slug": "cadastrar_clientes_ixc",
        "nome_exibicao": "Clientes IXC",
        "url_name": "backoffice:cadastrar_clientes_ixc",
        "icone": "user-round-plus",
        "ordem": 9,
    },
]


def seed_automacoes(apps, schema_editor):
    AutomacaoMenu = apps.get_model("core_admin", "AutomacaoMenu")
    for dados in AUTOMACOES_INICIAIS:
        AutomacaoMenu.objects.update_or_create(
            slug=dados["slug"],
            defaults={
                "nome_exibicao": dados["nome_exibicao"],
                "url_name": dados["url_name"],
                "icone": dados["icone"],
                "ordem": dados["ordem"],
                "menu": "administrador",
                "ativo": True,
            },
        )


def remove_automacoes(apps, schema_editor):
    AutomacaoMenu = apps.get_model("core_admin", "AutomacaoMenu")
    slugs = [dados["slug"] for dados in AUTOMACOES_INICIAIS]
    AutomacaoMenu.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core_admin", "0005_seed_automacoes_menu"),
    ]

    operations = [
        migrations.RunPython(seed_automacoes, remove_automacoes),
    ]
