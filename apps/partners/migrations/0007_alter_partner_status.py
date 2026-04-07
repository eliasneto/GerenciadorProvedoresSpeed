from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0006_alter_proposal_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='partner',
            name='status',
            field=models.CharField(
                choices=[
                    ('ativo', 'Ativo'),
                    ('aguardando_ativacao', 'Aguardando Ativação'),
                    ('inativo', 'Inativo / Novo'),
                    ('negociacao', 'Em Negociação'),
                    ('andamento', 'Em Andamento (Reativar)'),
                    ('inviavel', 'Inviável / Não Avançou'),
                ],
                default='ativo',
                max_length=20,
                verbose_name='Status',
            ),
        ),
    ]
