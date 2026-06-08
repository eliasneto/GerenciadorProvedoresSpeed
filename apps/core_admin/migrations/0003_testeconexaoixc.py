from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core_admin', '0002_configuracaoemailenvio'),
    ]

    operations = [
        migrations.CreateModel(
            name='TesteConexaoIXC',
            fields=[],
            options={
                'managed': False,
                'default_permissions': [],
                'verbose_name': 'Teste Conexao IXC',
                'verbose_name_plural': 'Teste Conexao IXC',
            },
        ),
    ]
