from django.db import migrations

# RN-043/PO-067: Mapa Calor segue o mesmo padrao de NOME_PROCESSO_PADRAO
# de RedeExterna/RedeInterna (migration 0006) — precisa de um Processo
# proprio, com Setores e Status, cadastrado na tela de Processos
# (PO-050/RN-025). Dados de teste, explicitamente nao-definitivos, mesmo
# padrao da 0006_seed_processos_setores_status_teste.
PROCESSO = "Mapa Calor (MC)"
SETORES = ["Lastmile", "Suprimentos", "Implantacao", "Pos venda", "Suporte"]
STATUS = ["A fazer", "Em andamento", "Concluido"]


def semear_dados_teste(apps, schema_editor):
    Processo = apps.get_model("escolas", "Processo")
    Setor = apps.get_model("escolas", "Setor")
    SetorStatus = apps.get_model("escolas", "SetorStatus")

    processo, _ = Processo.objects.get_or_create(nome=PROCESSO)
    for nome_setor in SETORES:
        setor, _ = Setor.objects.get_or_create(processo=processo, nome=nome_setor)
        for nome_status in STATUS:
            SetorStatus.objects.get_or_create(setor=setor, nome=nome_status)


def remover_dados_teste(apps, schema_editor):
    Processo = apps.get_model("escolas", "Processo")
    Processo.objects.filter(nome=PROCESSO).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('escolas', '0013_alter_setorescopo_atividade'),
    ]

    operations = [
        migrations.RunPython(semear_dados_teste, remover_dados_teste),
    ]
