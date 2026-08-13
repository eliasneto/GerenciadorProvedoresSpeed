from django.db import migrations

# RN-044/ADR-026: "Cotacao" precisa existir como SetorStatus do Setor
# "Lastmile", nos Processos de RE e de RI (RN-025) — sem essa semeadura a
# tela nunca entra nesse Status (falha silenciosa de configuracao, nao de
# codigo; risco ja registrado na ADR-026). Diferente das semeaduras de teste
# das migrations 0006/0014 ("A fazer"/"Em andamento"/"Concluido"), "Cotacao"
# e valor de catalogo pedido pela regra de negocio — nao e dado de teste.
# get_or_create em cada nivel (Processo/Setor/Status) para nao duplicar caso
# o ambiente ja tenha os Processos/Setor "Lastmile" criados manualmente pela
# tela de Administracao (PO-050) antes desta migration rodar.
PROCESSOS = ["Rede Externa (RE)", "Rede Interna (RI)"]
SETOR_LASTMILE = "Lastmile"
STATUS_COTACAO = "Cotacao"


def semear_status_cotacao(apps, schema_editor):
    Processo = apps.get_model("escolas", "Processo")
    Setor = apps.get_model("escolas", "Setor")
    SetorStatus = apps.get_model("escolas", "SetorStatus")

    for nome_processo in PROCESSOS:
        processo, _ = Processo.objects.get_or_create(nome=nome_processo)
        setor, _ = Setor.objects.get_or_create(processo=processo, nome=SETOR_LASTMILE)
        SetorStatus.objects.get_or_create(setor=setor, nome=STATUS_COTACAO)


def remover_status_cotacao(apps, schema_editor):
    SetorStatus = apps.get_model("escolas", "SetorStatus")
    SetorStatus.objects.filter(
        nome=STATUS_COTACAO,
        setor__nome=SETOR_LASTMILE,
        setor__processo__nome__in=PROCESSOS,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('escolas', '0015_cotacaoparceiro'),
    ]

    operations = [
        migrations.RunPython(semear_status_cotacao, remover_status_cotacao),
    ]
