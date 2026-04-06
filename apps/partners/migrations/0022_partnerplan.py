from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0021_proposal_campos_tecnicos_faltantes'),
    ]

    operations = [
        migrations.CreateModel(
            name='PartnerPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome_plano', models.CharField(max_length=120, verbose_name='Nome do Plano')),
                ('velocidade', models.CharField(blank=True, max_length=50, null=True, verbose_name='Velocidade (Mbps)')),
                ('tecnologia', models.CharField(blank=True, max_length=50, null=True, verbose_name='Tecnologia de Acesso')),
                ('disponibilidade', models.CharField(blank=True, max_length=10, null=True, verbose_name='Disponibilidade (%)')),
                ('mttr', models.IntegerField(blank=True, null=True, verbose_name='MTTR (hs)')),
                ('perda_pacote', models.CharField(blank=True, max_length=10, null=True, verbose_name='Perda de Pacote')),
                ('latencia', models.IntegerField(blank=True, null=True, verbose_name='Latência (ms)')),
                ('interfaces', models.CharField(blank=True, max_length=100, null=True, verbose_name='Interfaces')),
                ('tipo_acesso', models.CharField(blank=True, max_length=100, null=True, verbose_name='Tipo de Acesso')),
                ('ipv4_bloco', models.CharField(blank=True, max_length=50, null=True, verbose_name='Bloco IP')),
                ('dupla_abordagem', models.CharField(blank=True, choices=[('', 'Selecione'), ('Sim', 'Sim'), ('Não', 'Não')], max_length=3, null=True, verbose_name='Dupla Abordagem')),
                ('entrega_rb', models.CharField(blank=True, choices=[('', 'Selecione'), ('Sim', 'Sim'), ('Não', 'Não')], max_length=3, null=True, verbose_name='Entrega RB')),
                ('designador', models.CharField(blank=True, max_length=100, null=True, verbose_name='Designador')),
                ('trunk', models.CharField(blank=True, choices=[('', 'Selecione'), ('Sim', 'Sim'), ('Não', 'Não')], max_length=3, null=True, verbose_name='Interface em Trunk?')),
                ('dhcp', models.CharField(blank=True, choices=[('', 'Selecione'), ('Sim', 'Sim'), ('Não', 'Não')], max_length=3, null=True, verbose_name='DHCP habilitado?')),
                ('prazo_ativacao', models.IntegerField(blank=True, null=True, verbose_name='Prazo de Ativação (dias)')),
                ('contato_suporte', models.CharField(blank=True, max_length=100, null=True, verbose_name='Contato para Suporte')),
                ('telefone_suporte', models.CharField(blank=True, max_length=25, null=True, verbose_name='Número do Telefone')),
                ('data_cadastro', models.DateTimeField(auto_now_add=True)),
                ('partner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='planos', to='partners.partner')),
            ],
            options={
                'verbose_name': 'Plano do Parceiro',
                'verbose_name_plural': 'Planos dos Parceiros',
                'ordering': ['nome_plano', '-id'],
            },
        ),
    ]
