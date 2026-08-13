from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0013_alter_endereco_em_os_comercial_lastmile_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicosincronizacao',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('incremental', 'Incremental'),
                    ('total', 'Carga Total'),
                    ('faxina', 'Faxina/Lixo'),
                    ('os_comercial_lastmile', 'OS Comercial | Lastmile'),
                ],
                default='incremental',
                max_length=30,
                verbose_name='Tipo de Sync',
            ),
        ),
    ]
