from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0004_proposal_codigo_proposta'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposal',
            name='nome_proposta',
            field=models.CharField(blank=True, max_length=150, null=True, verbose_name='Nome da Proposta'),
        ),
    ]
