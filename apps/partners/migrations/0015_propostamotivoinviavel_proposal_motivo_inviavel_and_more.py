from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0014_alter_proposal_ticket_labels'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProposalMotivoInviavel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=120, unique=True, verbose_name='Nome do Motivo')),
                ('status', models.CharField(choices=[('ativo', 'Ativo'), ('inativo', 'Inativo')], default='ativo', max_length=10, verbose_name='Status')),
                ('data_cadastro', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Motivo de Proposta Inviável',
                'verbose_name_plural': 'Motivos de Proposta Inviável',
                'ordering': ['nome'],
            },
        ),
        migrations.AddField(
            model_name='proposal',
            name='motivo_inviavel',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='propostas', to='partners.proposalmotivoinviavel', verbose_name='Motivo da Proposta Inviável'),
        ),
        migrations.AddField(
            model_name='proposal',
            name='observacao_inviavel',
            field=models.CharField(blank=True, max_length=150, null=True, verbose_name='Observação da Proposta Inviável'),
        ),
        migrations.AlterField(
            model_name='proposal',
            name='status',
            field=models.CharField(choices=[('analise', 'Em Negociação'), ('ativa', 'Convertida'), ('encerrada', 'Inviavel')], default='analise', max_length=20, verbose_name='Status da Proposta'),
        ),
    ]
