from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0009_proposal_designador'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proposal',
            name='taxa_instalacao',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Taxa de Instalação Parceiro'),
        ),
        migrations.AlterField(
            model_name='proposal',
            name='valor_parceiro',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Custo Parceiro'),
        ),
    ]
