from django.db import migrations, models


FIELD_DEFINITIONS = [
    ('velocidade', models.CharField(blank=True, max_length=50, null=True, verbose_name='Velocidade Contratada')),
    ('tecnologia', models.CharField(blank=True, max_length=50, null=True, verbose_name='Tecnologia de Acesso')),
    ('disponibilidade', models.CharField(blank=True, max_length=10, null=True, verbose_name='Disponibilidade (%)')),
    ('mttr', models.IntegerField(blank=True, null=True, verbose_name='MTTR (hs)')),
    ('perda_pacote', models.CharField(blank=True, max_length=10, null=True, verbose_name='Perda de Pacote')),
    ('latencia', models.IntegerField(blank=True, null=True, verbose_name='Latência (ms)')),
    ('interfaces', models.CharField(blank=True, max_length=100, null=True, verbose_name='Interfaces')),
    ('ipv4_bloco', models.CharField(blank=True, max_length=50, null=True, verbose_name='IPs (bloco)')),
    ('designador', models.CharField(blank=True, max_length=100, null=True, verbose_name='Designador')),
    ('trunk', models.CharField(blank=True, max_length=3, null=True, verbose_name='Interface em Trunk?')),
    ('dhcp', models.CharField(blank=True, max_length=3, null=True, verbose_name='DHCP habilitado?')),
    ('prazo_ativacao', models.IntegerField(blank=True, null=True, verbose_name='Prazo de Ativação (dias)')),
    ('contato_suporte', models.CharField(blank=True, max_length=100, null=True, verbose_name='Contato para Suporte')),
    ('telefone_suporte', models.CharField(blank=True, max_length=25, null=True, verbose_name='Número do Telefone')),
]


def _existing_columns(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        return {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }


def add_missing_endereco_fields(apps, schema_editor):
    Endereco = apps.get_model('clientes', 'Endereco')
    table_name = Endereco._meta.db_table
    existing_columns = _existing_columns(schema_editor, table_name)

    for field_name, field in FIELD_DEFINITIONS:
        if field_name in existing_columns:
            continue
        field.set_attributes_from_name(field_name)
        schema_editor.add_field(Endereco, field)


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0003_clienteexcluido_endereco_agent_circuit_id_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_missing_endereco_fields, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='endereco',
                    name='velocidade',
                    field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Velocidade Contratada'),
                ),
                migrations.AddField(
                    model_name='endereco',
                    name='tecnologia',
                    field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Tecnologia de Acesso'),
                ),
                migrations.AddField(
                    model_name='endereco',
                    name='disponibilidade',
                    field=models.CharField(blank=True, max_length=10, null=True, verbose_name='Disponibilidade (%)'),
                ),
                migrations.AddField(
                    model_name='endereco',
                    name='mttr',
                    field=models.IntegerField(blank=True, null=True, verbose_name='MTTR (hs)'),
                ),
                migrations.AddField(
                    model_name='endereco',
                    name='perda_pacote',
                    field=models.CharField(blank=True, max_length=10, null=True, verbose_name='Perda de Pacote'),
                ),
                migrations.AddField(
                    model_name='endereco',
                    name='latencia',
                    field=models.IntegerField(blank=True, null=True, verbose_name='Latência (ms)'),
                ),
                migrations.AddField(
                    model_name='endereco',
                    name='interfaces',
                    field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Interfaces'),
                ),
                migrations.AddField(
                    model_name='endereco',
                    name='ipv4_bloco',
                    field=models.CharField(blank=True, max_length=50, null=True, verbose_name='IPs (bloco)'),
                ),
                migrations.AddField(
                    model_name='endereco',
                    name='designador',
                    field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Designador'),
                ),
                migrations.AddField(
                    model_name='endereco',
                    name='trunk',
                    field=models.CharField(blank=True, max_length=3, null=True, verbose_name='Interface em Trunk?'),
                ),
                migrations.AddField(
                    model_name='endereco',
                    name='dhcp',
                    field=models.CharField(blank=True, max_length=3, null=True, verbose_name='DHCP habilitado?'),
                ),
                migrations.AddField(
                    model_name='endereco',
                    name='prazo_ativacao',
                    field=models.IntegerField(blank=True, null=True, verbose_name='Prazo de Ativação (dias)'),
                ),
                migrations.AddField(
                    model_name='endereco',
                    name='contato_suporte',
                    field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Contato para Suporte'),
                ),
                migrations.AddField(
                    model_name='endereco',
                    name='telefone_suporte',
                    field=models.CharField(blank=True, max_length=25, null=True, verbose_name='Número do Telefone'),
                ),
            ],
        ),
    ]
