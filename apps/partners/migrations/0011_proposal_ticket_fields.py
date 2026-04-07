from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0010_alter_proposal_commercial_labels'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposal',
            name='ticket_cliente',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Ticket Cliente'),
        ),
        migrations.AddField(
            model_name='proposal',
            name='ticket_empresa',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Ticket Empresa'),
        ),
    ]
