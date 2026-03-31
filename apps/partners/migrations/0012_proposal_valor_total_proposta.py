from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0011_proposal_ticket_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposal',
            name='valor_total_proposta',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Rentabilidade'),
        ),
    ]
