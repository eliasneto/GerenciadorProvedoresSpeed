from django.db import migrations

PROCESSOS = ["Rede Externa (RE)", "Rede Interna (RI)"]
SETORES = ["Lastmile", "Suprimentos", "Implantacao", "Pos venda", "Suporte"]
STATUS = ["A fazer", "Em andamento", "Concluido"]


def semear_dados_teste(apps, schema_editor):
    Processo = apps.get_model("escolas", "Processo")
    Setor = apps.get_model("escolas", "Setor")
    SetorStatus = apps.get_model("escolas", "SetorStatus")

    for nome_processo in PROCESSOS:
        processo, _ = Processo.objects.get_or_create(nome=nome_processo)
        for nome_setor in SETORES:
            setor, _ = Setor.objects.get_or_create(processo=processo, nome=nome_setor)
            for nome_status in STATUS:
                SetorStatus.objects.get_or_create(setor=setor, nome=nome_status)


def remover_dados_teste(apps, schema_editor):
    Processo = apps.get_model("escolas", "Processo")
    Processo.objects.filter(nome__in=PROCESSOS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('escolas', '0005_processo_redeexterna_processo_redeinterna_processo_and_more'),
    ]

    operations = [
        migrations.RunPython(semear_dados_teste, remover_dados_teste),
    ]
