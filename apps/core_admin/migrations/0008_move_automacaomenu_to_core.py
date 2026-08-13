# PO-036 (ADR-007 item 8): remove o AutomacaoMenu do estado de core_admin. A
# tabela fisica (core_admin_automacaomenu) permanece intocada; o dono passa a
# ser apps.core (ver apps/core/migrations/0011_move_automacaomenu_from_core_admin.py).
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core_admin', '0007_fix_menu_automacoes_backoffice'),
        ('core', '0011_move_automacaomenu_from_core_admin'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='AutomacaoMenu'),
            ],
            database_operations=[],
        ),
    ]
