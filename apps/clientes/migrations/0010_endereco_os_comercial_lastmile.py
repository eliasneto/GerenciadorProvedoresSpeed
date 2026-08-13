from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0009_endereco_primeira_os_status_ixc'),
    ]

    operations = [
        migrations.AddField(
            model_name='endereco',
            name='os_comercial_lastmile',
            field=models.BooleanField(db_index=True, default=False, verbose_name='OS Comercial | Lastmile?'),
        ),
    ]
