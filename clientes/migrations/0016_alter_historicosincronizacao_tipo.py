from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0015_endereco_os_atual_aberta_and_more'),
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
                    ('backup', 'Backup'),
                ],
                default='incremental',
                max_length=30,
                verbose_name='Tipo de Sync',
            ),
        ),
    ]
