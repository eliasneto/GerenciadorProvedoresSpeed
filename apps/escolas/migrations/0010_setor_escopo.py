from django.db import migrations, models


def semear_escopo_padrao(apps, schema_editor):
    """PO-062/RN-037/ADR-022: todo nome de Setor ja usado por um Campo
    (RN-031) recebe escopo "Sub-atividades: RE e RI", preservando o
    comportamento atual sem exigir configuracao manual antes do deploy."""
    Campo = apps.get_model("escolas", "Campo")
    SetorEscopo = apps.get_model("escolas", "SetorEscopo")

    nomes_setor = Campo.objects.order_by().values_list("setor_nome", flat=True).distinct()
    for nome in nomes_setor:
        SetorEscopo.objects.get_or_create(
            setor_nome=nome,
            defaults={"atividade": "sub_atividades", "aplica_re": True, "aplica_ri": True},
        )


def remover_escopo_padrao(apps, schema_editor):
    # Reversao intencionalmente vazia: apagar SetorEscopo ao reverter a
    # migration removeria configuracao que o usuario pode ja ter editado
    # pela tela "Setor" depois do deploy.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('escolas', '0009_campo_valor'),
    ]

    operations = [
        migrations.CreateModel(
            name='SetorEscopo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('setor_nome', models.CharField(max_length=120, unique=True, verbose_name='Setor')),
                ('atividade', models.CharField(choices=[('escola', 'Atividade principal (Escola)'), ('sub_atividades', 'Sub-atividades (RE/RI)')], max_length=20, verbose_name='Onde aparece')),
                ('aplica_re', models.BooleanField(default=True, verbose_name='Rede Externa (RE)')),
                ('aplica_ri', models.BooleanField(default=True, verbose_name='Rede Interna (RI)')),
                ('criado_em', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('atualizado_em', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
            ],
            options={
                'verbose_name': 'Escopo do Setor',
                'verbose_name_plural': 'Escopos dos Setores',
                'ordering': ['setor_nome'],
            },
        ),
        migrations.RunPython(semear_escopo_padrao, remover_escopo_padrao),
    ]
