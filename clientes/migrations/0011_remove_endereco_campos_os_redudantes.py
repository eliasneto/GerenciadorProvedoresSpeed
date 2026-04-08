from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0010_endereco_os_comercial_lastmile'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='endereco',
            name='possui_primeira_os',
        ),
        migrations.RemoveField(
            model_name='endereco',
            name='primeira_os_ixc',
        ),
        migrations.RemoveField(
            model_name='endereco',
            name='primeira_os_status_ixc',
        ),
    ]
