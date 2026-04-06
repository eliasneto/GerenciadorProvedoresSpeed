from django.db import migrations, models


FIELD_DEFINITIONS = [
    (
        'fonte',
        models.CharField(blank=True, max_length=100, null=True, verbose_name='Fonte de Captação'),
    ),
    (
        'confianca',
        models.CharField(blank=True, max_length=50, null=True, verbose_name='Confiança dos Dados'),
    ),
    (
        'instagram_username',
        models.CharField(blank=True, max_length=100, null=True, verbose_name='Usuário Instagram'),
    ),
    (
        'instagram_url',
        models.URLField(blank=True, max_length=255, null=True, verbose_name='Link Instagram'),
    ),
    (
        'bio_instagram',
        models.TextField(blank=True, null=True, verbose_name='Bio do Instagram'),
    ),
    (
        'observacao_ia',
        models.TextField(blank=True, null=True, verbose_name='Observação da IA'),
    ),
]


def _existing_columns(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        return {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }


def add_missing_lead_ai_fields(apps, schema_editor):
    Lead = apps.get_model('leads', 'Lead')
    table_name = Lead._meta.db_table
    existing_columns = _existing_columns(schema_editor, table_name)

    for field_name, field in FIELD_DEFINITIONS:
        if field_name in existing_columns:
            continue
        field.set_attributes_from_name(field_name)
        schema_editor.add_field(Lead, field)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('leads', '0002_lead_cep_lead_bairro_lead_numero'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_missing_lead_ai_fields, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='lead',
                    name='fonte',
                    field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Fonte de Captação'),
                ),
                migrations.AddField(
                    model_name='lead',
                    name='confianca',
                    field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Confiança dos Dados'),
                ),
                migrations.AddField(
                    model_name='lead',
                    name='instagram_username',
                    field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Usuário Instagram'),
                ),
                migrations.AddField(
                    model_name='lead',
                    name='instagram_url',
                    field=models.URLField(blank=True, max_length=255, null=True, verbose_name='Link Instagram'),
                ),
                migrations.AddField(
                    model_name='lead',
                    name='bio_instagram',
                    field=models.TextField(blank=True, null=True, verbose_name='Bio do Instagram'),
                ),
                migrations.AddField(
                    model_name='lead',
                    name='observacao_ia',
                    field=models.TextField(blank=True, null=True, verbose_name='Observação da IA'),
                ),
            ],
        ),
    ]
