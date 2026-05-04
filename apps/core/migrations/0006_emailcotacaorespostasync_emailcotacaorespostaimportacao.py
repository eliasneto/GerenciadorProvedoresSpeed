from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("partners", "0024_proposal_lead_proposal_lead_endereco"),
        ("core", "0005_alter_integrationaudit_integration"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailCotacaoRespostaSync",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("mailbox_email", models.EmailField(max_length=254, unique=True, verbose_name="Caixa monitorada")),
                ("inbox_delta_link", models.TextField(blank=True, null=True, verbose_name="DeltaLink da Inbox")),
                ("ultima_sincronizacao_em", models.DateTimeField(blank=True, null=True, verbose_name="Ultima sincronizacao")),
                ("ultimo_erro", models.TextField(blank=True, verbose_name="Ultimo erro")),
                ("ativo", models.BooleanField(default=True, verbose_name="Ativo")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
            ],
            options={
                "verbose_name": "Sync de respostas por e-mail da cotacao",
                "verbose_name_plural": "Syncs de respostas por e-mail da cotacao",
            },
        ),
        migrations.CreateModel(
            name="EmailCotacaoRespostaImportacao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("graph_message_id", models.CharField(max_length=255, unique=True, verbose_name="ID da mensagem no Graph")),
                ("internet_message_id", models.CharField(blank=True, max_length=500, null=True, verbose_name="Message-ID da internet")),
                ("assunto", models.CharField(max_length=998, verbose_name="Assunto")),
                ("remetente", models.EmailField(blank=True, max_length=254, null=True, verbose_name="Remetente")),
                ("recebido_em", models.DateTimeField(blank=True, null=True, verbose_name="Recebido em")),
                ("importado_em", models.DateTimeField(auto_now_add=True, verbose_name="Importado em")),
                ("historico", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="respostas_email_importadas", to="core.registrohistorico", verbose_name="Historico gerado")),
                ("proposal", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="respostas_email_importadas", to="partners.proposal", verbose_name="Cotacao")),
            ],
            options={
                "verbose_name": "Resposta de e-mail importada",
                "verbose_name_plural": "Respostas de e-mail importadas",
                "ordering": ["-importado_em"],
            },
        ),
    ]
