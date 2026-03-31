from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0005_proposal_nome_proposta'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proposal',
            name='status',
            field=models.CharField(
                choices=[
                    ('analise', 'Em Negociação'),
                    ('ativa', 'Convertida'),
                    ('encerrada', 'Encerrada'),
                ],
                default='analise',
                max_length=20,
                verbose_name='Status da Proposta',
            ),
        ),
    ]
