# PO-036 (ADR-007 item 8): move o model AutomacaoMenu de core_admin para core,
# preservando a tabela fisica existente (state move, sem tocar o banco).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_alter_integrationaudit_integration'),
        ('core_admin', '0007_fix_menu_automacoes_backoffice'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='AutomacaoMenu',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('slug', models.SlugField(max_length=64, unique=True, verbose_name='Identificador')),
                        ('nome_exibicao', models.CharField(max_length=120, verbose_name='Nome de exibicao')),
                        ('menu', models.CharField(choices=[('administrador', 'Administrador'), ('backoffice', 'Backoffice'), ('lastmile', 'LastMile'), ('parceiro', 'Parceiro')], default='administrador', max_length=20, verbose_name='Menu de exibicao')),
                        ('url_name', models.CharField(max_length=80, verbose_name='Nome da rota')),
                        ('icone', models.CharField(default='sparkles', max_length=40, verbose_name='Icone (lucide)')),
                        ('ativo', models.BooleanField(default=True, verbose_name='Ativo')),
                        ('ordem', models.PositiveIntegerField(default=0, verbose_name='Ordem')),
                    ],
                    options={
                        'verbose_name': 'Menu de Automacao',
                        'verbose_name_plural': 'Menus de Automacao',
                        'ordering': ['ordem', 'nome_exibicao'],
                        'db_table': 'core_admin_automacaomenu',
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
