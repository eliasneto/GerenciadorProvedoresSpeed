from django.db import migrations


AUTOMACOES_INICIAIS = [
    {
        "slug": "import_prospects",
        "nome_exibicao": "Importador de Provedores",
        "url_name": "import_prospects",
        "icone": "database",
        "ordem": 1,
    },
    {
        "slug": "desativar_atendimentos_ixc",
        "nome_exibicao": "Desativacao de Atendimento IXC",
        "url_name": "desativar_atendimentos_ixc",
        "icone": "power",
        "ordem": 2,
    },
    {
        "slug": "resolver_os_atendimento_ixc",
        "nome_exibicao": "Resolucao de O.S. do Atendimento",
        "url_name": "resolver_os_atendimento_ixc",
        "icone": "file-check-2",
        "ordem": 3,
    },
    {
        "slug": "editar_atendimentos_ixc",
        "nome_exibicao": "Edicao de Atendimento IXC",
        "url_name": "editar_atendimentos_ixc",
        "icone": "clipboard-pen-line",
        "ordem": 4,
    },
    {
        "slug": "editar_logins_ixc",
        "nome_exibicao": "Edicao de Login IXC",
        "url_name": "editar_logins_ixc",
        "icone": "pencil-line",
        "ordem": 5,
    },
    {
        "slug": "testar_api_ixc",
        "nome_exibicao": "Teste de Conexao IXC",
        "url_name": "testar_api_ixc",
        "icone": "activity",
        "ordem": 6,
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
        ("core_admin", "0004_automacaomenu"),
    ]

    operations = [
        migrations.RunPython(seed_automacoes, remove_automacoes),
    ]
