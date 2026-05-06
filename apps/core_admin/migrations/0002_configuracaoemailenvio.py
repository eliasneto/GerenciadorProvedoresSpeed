from django.db import migrations, models


def criar_configuracao_padrao(apps, schema_editor):
    ConfiguracaoEmailEnvio = apps.get_model('core_admin', 'ConfiguracaoEmailEnvio')
    if not ConfiguracaoEmailEnvio.objects.exists():
        ConfiguracaoEmailEnvio.objects.create()


class Migration(migrations.Migration):

    dependencies = [
        ('core_admin', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfiguracaoEmailEnvio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(default='Padrao do Sistema', max_length=80, verbose_name='Identificacao')),
                ('email_remetente_padrao', models.EmailField(blank=True, help_text='Este e-mail aparece como remetente padrao na composicao das mensagens do sistema.', max_length=254, null=True, verbose_name='E-mail remetente padrao')),
                ('atualizado_em', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
            ],
            options={
                'verbose_name': 'Configuracao de E-mail',
                'verbose_name_plural': 'Configuracoes de E-mail',
            },
        ),
        migrations.RunPython(criar_configuracao_padrao, migrations.RunPython.noop),
    ]
