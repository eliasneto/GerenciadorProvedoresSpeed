from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0013_proposal_resultados_financeiros'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proposal',
            name='ticket_cliente',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Valor Mensal Cliente'),
        ),
        migrations.AlterField(
            model_name='proposal',
            name='ticket_empresa',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Target Empresa'),
        ),
    ]
