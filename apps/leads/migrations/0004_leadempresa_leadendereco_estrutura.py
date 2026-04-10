from django.db import migrations, models
import django.db.models.deletion


def _normalizar(valor):
    return (str(valor or '').strip()).lower()


def popular_estrutura_leads(apps, schema_editor):
    Lead = apps.get_model('leads', 'Lead')
    LeadEmpresa = apps.get_model('leads', 'LeadEmpresa')
    LeadEndereco = apps.get_model('leads', 'LeadEndereco')

    cache_empresas = {}

    for lead in Lead.objects.all().order_by('id').iterator():
        documento = (lead.cnpj_cpf or '').strip()
        email = (lead.email or '').strip()
        telefone = (lead.telefone or '').strip()
        razao_social = (lead.razao_social or '').strip()

        if documento:
            chave_empresa = f"doc::{documento}"
        else:
            chave_empresa = "nome::{nome}::email::{email}::tel::{telefone}".format(
                nome=_normalizar(razao_social),
                email=_normalizar(email),
                telefone=_normalizar(telefone),
            )

        empresa = cache_empresas.get(chave_empresa)
        if empresa is None:
            empresa = LeadEmpresa.objects.create(
                razao_social=lead.razao_social,
                cnpj_cpf=lead.cnpj_cpf,
                nome_fantasia=lead.nome_fantasia,
                site=lead.site,
                contato_nome=lead.contato_nome,
                email=lead.email,
                telefone=lead.telefone,
                fonte=lead.fonte,
                confianca=lead.confianca,
                instagram_username=lead.instagram_username,
                instagram_url=lead.instagram_url,
                bio_instagram=lead.bio_instagram,
                observacao_ia=lead.observacao_ia,
                status=lead.status,
            )
            cache_empresas[chave_empresa] = empresa

        endereco = LeadEndereco.objects.create(
            empresa=empresa,
            cep=lead.cep,
            endereco=lead.endereco,
            numero=lead.numero,
            bairro=lead.bairro,
            cidade=lead.cidade,
            estado=lead.estado,
        )

        lead.empresa_estruturada_id = empresa.id
        lead.endereco_estruturado_id = endereco.id
        lead.save(update_fields=['empresa_estruturada', 'endereco_estruturado'])


def reverter_estrutura_leads(apps, schema_editor):
    Lead = apps.get_model('leads', 'Lead')
    Lead.objects.all().update(empresa_estruturada=None, endereco_estruturado=None)


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0003_lead_campos_ia'),
    ]

    operations = [
        migrations.CreateModel(
            name='LeadEmpresa',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('razao_social', models.CharField(blank=True, max_length=200, null=True, verbose_name='Razao Social / Nome')),
                ('cnpj_cpf', models.CharField(blank=True, max_length=20, null=True, verbose_name='CNPJ/CPF')),
                ('nome_fantasia', models.CharField(blank=True, max_length=200, null=True, verbose_name='Nome Fantasia')),
                ('site', models.URLField(blank=True, max_length=200, null=True, verbose_name='Site')),
                ('contato_nome', models.CharField(blank=True, max_length=100, null=True, verbose_name='Pessoa de Contato')),
                ('email', models.EmailField(blank=True, max_length=254, null=True, verbose_name='E-mail')),
                ('telefone', models.CharField(blank=True, max_length=20, null=True, verbose_name='Telefone/WhatsApp')),
                ('fonte', models.CharField(blank=True, max_length=100, null=True, verbose_name='Fonte de Captacao')),
                ('confianca', models.CharField(blank=True, max_length=50, null=True, verbose_name='Confianca dos Dados')),
                ('instagram_username', models.CharField(blank=True, max_length=100, null=True, verbose_name='Usuario Instagram')),
                ('instagram_url', models.URLField(blank=True, max_length=255, null=True, verbose_name='Link Instagram')),
                ('bio_instagram', models.TextField(blank=True, null=True, verbose_name='Bio do Instagram')),
                ('observacao_ia', models.TextField(blank=True, null=True, verbose_name='Observacao da IA')),
                ('status', models.CharField(choices=[('novo', 'Novo'), ('negociacao', 'Em Negociacao'), ('andamento', 'Em Andamento'), ('ativo', 'Ativo'), ('inviavel', 'Inviavel / Nao Avancou')], default='novo', max_length=20)),
                ('data_criacao', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Empresa de Lead',
                'verbose_name_plural': 'Empresas de Leads',
                'ordering': ['-data_criacao'],
            },
        ),
        migrations.CreateModel(
            name='LeadEndereco',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cep', models.CharField(blank=True, max_length=20, null=True, verbose_name='CEP')),
                ('endereco', models.CharField(blank=True, max_length=255, null=True, verbose_name='Logradouro / Endereco')),
                ('numero', models.CharField(blank=True, max_length=20, null=True, verbose_name='Numero')),
                ('bairro', models.CharField(blank=True, max_length=100, null=True, verbose_name='Bairro')),
                ('cidade', models.CharField(blank=True, max_length=100, null=True, verbose_name='Cidade')),
                ('estado', models.CharField(blank=True, max_length=2, null=True, verbose_name='Estado')),
                ('data_criacao', models.DateTimeField(auto_now_add=True)),
                ('empresa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enderecos', to='leads.leadempresa', verbose_name='Empresa')),
            ],
            options={
                'verbose_name': 'Endereco de Lead',
                'verbose_name_plural': 'Enderecos de Leads',
                'ordering': ['empresa__razao_social', 'cidade', 'bairro', 'endereco', 'id'],
            },
        ),
        migrations.AddField(
            model_name='lead',
            name='empresa_estruturada',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='leads_legados', to='leads.leadempresa', verbose_name='Empresa Estruturada'),
        ),
        migrations.AddField(
            model_name='lead',
            name='endereco_estruturado',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='leads_legados', to='leads.leadendereco', verbose_name='Endereco Estruturado'),
        ),
        migrations.RunPython(popular_estrutura_leads, reverter_estrutura_leads),
    ]
