from django.db import migrations, models
from datetime import date


def popular_codigo_proposta(apps, schema_editor):
    Proposal = apps.get_model('partners', 'Proposal')
    referencia = date.today().strftime('%d%m%Y')

    for proposal in Proposal.objects.all().iterator():
        sequencial = proposal.grupo_proposta_id or proposal.id
        if not proposal.codigo_proposta and sequencial:
            proposal.codigo_proposta = f"{sequencial}{referencia}"
            proposal.save(update_fields=['codigo_proposta'])


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0003_proposal_grupo_proposta_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposal',
            name='codigo_proposta',
            field=models.CharField(blank=True, db_index=True, max_length=30, null=True, verbose_name='Código da Proposta'),
        ),
        migrations.RunPython(popular_codigo_proposta, migrations.RunPython.noop),
    ]
