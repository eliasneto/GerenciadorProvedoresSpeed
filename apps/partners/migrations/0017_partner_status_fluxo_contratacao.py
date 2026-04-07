from django.db import migrations, models


def migrar_status_aguardando(apps, schema_editor):
    Partner = apps.get_model('partners', 'Partner')
    Partner.objects.filter(status='aguardando_ativacao').update(status='aguardando_contratacao')


def reverter_status_aguardando(apps, schema_editor):
    Partner = apps.get_model('partners', 'Partner')
    Partner.objects.filter(status='aguardando_contratacao').update(status='aguardando_ativacao')


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0016_alter_proposal_status_label_viavel'),
    ]

    operations = [
        migrations.AlterField(
            model_name='partner',
            name='status',
            field=models.CharField(
                choices=[
                    ('ativo', 'Ativo'),
                    ('aguardando_contratacao', 'Aguardando Contratação'),
                    ('contratado', 'Contratado'),
                    ('declinado', 'Declinado'),
                    ('inativo', 'Inativo / Novo'),
                    ('negociacao', 'Em Negociação'),
                    ('andamento', 'Em Andamento (Reativar)'),
                    ('inviavel', 'Inviável / Não Avançou'),
                ],
                default='ativo',
                max_length=30,
                verbose_name='Status',
            ),
        ),
        migrations.RunPython(migrar_status_aguardando, reverter_status_aguardando),
    ]
