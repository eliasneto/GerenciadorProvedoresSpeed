from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0006_endereco_campos_tecnicos_faltantes'),
    ]

    operations = [
        migrations.AddField(
            model_name='endereco',
            name='cidade_id_ixc',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Cidade ID IXC'),
        ),
    ]
