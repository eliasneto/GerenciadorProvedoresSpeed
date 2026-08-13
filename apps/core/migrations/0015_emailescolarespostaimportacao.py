import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("core", "0014_registrohistorico_campos_de_para"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailEscolaRespostaImportacao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nivel", models.CharField(choices=[("re", "Rede Externa (RE)"), ("ri", "Rede Interna (RI)"), ("global", "Escola (Global)")], max_length=10, verbose_name="Nivel")),
                ("object_id", models.PositiveIntegerField()),
                ("codigo_rastreio", models.CharField(db_index=True, max_length=64, verbose_name="Codigo de rastreio")),
                ("graph_message_id", models.CharField(max_length=255, unique=True, verbose_name="ID da mensagem no Graph")),
                ("internet_message_id", models.CharField(blank=True, max_length=500, null=True, verbose_name="Message-ID da internet")),
                ("assunto", models.CharField(max_length=998, verbose_name="Assunto")),
                ("remetente", models.EmailField(blank=True, max_length=254, null=True, verbose_name="Remetente")),
                ("recebido_em", models.DateTimeField(blank=True, null=True, verbose_name="Recebido em")),
                ("importado_em", models.DateTimeField(auto_now_add=True, verbose_name="Importado em")),
                ("content_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="contenttypes.contenttype")),
                ("historico", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="respostas_email_escola_importadas", to="core.registrohistorico", verbose_name="Historico gerado")),
            ],
            options={
                "verbose_name": "Resposta de e-mail de Escola/RE/RI importada",
                "verbose_name_plural": "Respostas de e-mail de Escola/RE/RI importadas",
                "ordering": ["-importado_em"],
            },
        ),
    ]
