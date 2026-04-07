from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0017_partner_status_fluxo_contratacao'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proposal',
            name='status',
            field=models.CharField(
                choices=[
                    ('analise', 'Em Negociação'),
                    ('ativa', 'Viavel'),
                    ('aguardando_contratacao', 'Aguardando Contratação'),
                    ('contratado', 'Contratado'),
                    ('declinado', 'Declinado'),
                    ('encerrada', 'Inviavel'),
                ],
                default='analise',
                max_length=30,
                verbose_name='Status da Proposta',
            ),
        ),
    ]
