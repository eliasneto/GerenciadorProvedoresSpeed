from django.db import migrations, models


FIELD_DEFINITIONS = [
    ('velocidade', models.CharField(blank=True, max_length=50, null=True, verbose_name='Velocidade (Mbps)')),
    ('tecnologia', models.CharField(blank=True, max_length=50, null=True, verbose_name='Tecnologia de Acesso')),
    ('disponibilidade', models.CharField(blank=True, max_length=10, null=True, verbose_name='Disponibilidade (%)')),
    ('mttr', models.IntegerField(blank=True, null=True, verbose_name='MTTR (hs)')),
    ('perda_pacote', models.CharField(blank=True, max_length=10, null=True, verbose_name='Perda de Pacote')),
    ('latencia', models.IntegerField(blank=True, null=True, verbose_name='Latência (ms)')),
    ('interfaces', models.CharField(blank=True, max_length=100, null=True, verbose_name='Interfaces')),
    ('tipo_acesso', models.CharField(blank=True, max_length=100, null=True, verbose_name='Tipo de Acesso')),
    ('ipv4_bloco', models.CharField(blank=True, max_length=50, null=True, verbose_name='Bloco IP')),
    ('dupla_abordagem', models.CharField(blank=True, max_length=3, null=True, verbose_name='Dupla Abordagem')),
    ('entrega_rb', models.CharField(blank=True, max_length=3, null=True, verbose_name='Entrega RB')),
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
    atomic = False

    dependencies = [
        ('clientes', '0005_endereco_dupla_abordagem_endereco_entrega_rb_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_missing_endereco_fields, migrations.RunPython.noop),
            ],
            state_operations=[],
        ),
    ]
