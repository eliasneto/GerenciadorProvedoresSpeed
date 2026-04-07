from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0002_proposal_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposal',
            name='grupo_proposta_id',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True, verbose_name='Grupo da Proposta'),
        ),
    ]
