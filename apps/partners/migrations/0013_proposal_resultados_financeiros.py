from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0012_proposal_valor_total_proposta'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposal',
            name='resultado_mes_1',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Resultado Mês 1'),
        ),
        migrations.AddField(
            model_name='proposal',
            name='resultado_mensal',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Resultado Mensal'),
        ),
    ]
