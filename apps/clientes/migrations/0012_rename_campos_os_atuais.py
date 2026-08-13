from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0011_remove_endereco_campos_os_redudantes'),
    ]

    operations = [
        migrations.RenameField(
            model_name='endereco',
            old_name='primeiro_ticket_ixc',
            new_name='ticket_os_atual_ixc',
        ),
        migrations.RenameField(
            model_name='endereco',
            old_name='primeira_os_setor_id_ixc',
            new_name='setor_os_atual_id_ixc',
        ),
        migrations.RenameField(
            model_name='endereco',
            old_name='primeira_os_setor_nome',
            new_name='setor_os_atual_nome',
        ),
        migrations.RenameField(
            model_name='endereco',
            old_name='os_comercial_lastmile',
            new_name='em_os_comercial_lastmile',
        ),
    ]
