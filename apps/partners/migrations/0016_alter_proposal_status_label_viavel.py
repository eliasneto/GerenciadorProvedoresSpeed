from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0015_propostamotivoinviavel_proposal_motivo_inviavel_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proposal',
            name='status',
            field=models.CharField(
                choices=[('analise', 'Em Negociação'), ('ativa', 'Viavel'), ('encerrada', 'Inviavel')],
                default='analise',
                max_length=20,
                verbose_name='Status da Proposta',
            ),
        ),
    ]
