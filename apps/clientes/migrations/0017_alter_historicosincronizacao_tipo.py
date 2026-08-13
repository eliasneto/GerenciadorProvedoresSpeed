from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clientes", "0016_alter_historicosincronizacao_tipo"),
    ]

    operations = [
        migrations.AlterField(
            model_name="historicosincronizacao",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("incremental", "Incremental"),
                    ("total", "Carga Total"),
                    ("faxina", "Faxina/Lixo"),
                    ("os_comercial_lastmile", "OS Comercial | Lastmile"),
                    ("email_respostas_cotacao", "Respostas de E-mail da Cotacao"),
                    ("backup", "Backup"),
                ],
                default="incremental",
                max_length=30,
                verbose_name="Tipo de Sync",
            ),
        ),
    ]
