from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0008_endereco_snapshot_primeira_os'),
    ]

    operations = [
        migrations.AddField(
            model_name='endereco',
            name='primeira_os_status_ixc',
            field=models.CharField(blank=True, max_length=30, null=True, verbose_name='Primeira OS Status IXC'),
        ),
    ]
