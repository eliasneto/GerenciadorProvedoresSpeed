from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='TabelaAcessoBanco',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome_tabela', models.CharField(max_length=128, unique=True, verbose_name='Nome da tabela')),
                ('descricao', models.CharField(blank=True, max_length=255, verbose_name='Descrição')),
                ('status', models.CharField(choices=[('ativo', 'Ativo'), ('inativo', 'Inativo')], default='ativo', max_length=10, verbose_name='Status')),
            ],
            options={
                'verbose_name': 'Tabela de Acesso ao Banco',
                'verbose_name_plural': 'Tabelas de Acesso ao Banco',
                'ordering': ['nome_tabela'],
            },
        ),
        migrations.CreateModel(
            name='AcessoBancoDados',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=120, verbose_name='Nome do acesso')),
                ('usuario_banco', models.CharField(max_length=64, unique=True, verbose_name='Usuário do banco')),
                ('senha_banco', models.CharField(max_length=128, verbose_name='Senha do banco')),
                ('host_acesso', models.CharField(default='%', max_length=100, verbose_name='Host de acesso')),
                ('status', models.CharField(choices=[('ativo', 'Ativo'), ('inativo', 'Inativo')], default='ativo', max_length=10, verbose_name='Status')),
                ('ultimo_aplicado_em', models.DateTimeField(blank=True, null=True, verbose_name='Última aplicação')),
                ('ultimo_erro', models.TextField(blank=True, verbose_name='Último erro')),
                ('observacao', models.TextField(blank=True, verbose_name='Observação')),
                ('tabelas_permitidas', models.ManyToManyField(blank=True, related_name='acessos_banco', to='core_admin.tabelaacessobanco', verbose_name='Tabelas permitidas')),
            ],
            options={
                'verbose_name': 'Acesso Banco de Dados',
                'verbose_name_plural': 'Acessos Banco de Dados',
                'ordering': ['nome'],
            },
        ),
    ]
