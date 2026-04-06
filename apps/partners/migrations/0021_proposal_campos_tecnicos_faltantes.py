from django.db import migrations, models


FIELD_DEFINITIONS = [
    ('tipo_acesso', models.CharField(blank=True, max_length=100, null=True, verbose_name='Tipo de Acesso')),
    ('dupla_abordagem', models.CharField(blank=True, max_length=3, null=True, verbose_name='Dupla Abordagem')),
    ('entrega_rb', models.CharField(blank=True, max_length=3, null=True, verbose_name='Entrega RB')),
]


def _existing_columns(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        return {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }


def add_missing_proposal_fields(apps, schema_editor):
    Proposal = apps.get_model('partners', 'Proposal')
    table_name = Proposal._meta.db_table
    existing_columns = _existing_columns(schema_editor, table_name)

    for field_name, field in FIELD_DEFINITIONS:
        if field_name in existing_columns:
            continue
        field.set_attributes_from_name(field_name)
        schema_editor.add_field(Proposal, field)


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('partners', '0020_alter_proposal_options_and_more'),
    ]

    operations = [
        migrations.RunPython(add_missing_proposal_fields, migrations.RunPython.noop),
    ]
