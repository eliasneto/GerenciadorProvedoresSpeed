from decimal import Decimal, InvalidOperation

from django.db import migrations


def _para_decimal(valor):
    if valor in (None, ""):
        return None
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return None


def backfill_velocidade_minima_kit_inicial(apps, schema_editor):
    """RN-057/PO-076: backfill unico das Escolas ja existentes, a partir do
    que ja estiver salvo em dados_api (mesmo padrao da migracao 0003).
    Sincronizacoes futuras (sincronizar_escolas) passam a preencher os dois
    campos diretamente."""
    Escola = apps.get_model("escolas", "Escola")
    for escola in Escola.objects.all().iterator():
        dados = escola.dados_api or {}
        atualizado = False

        if escola.velocidade_dl_minima is None:
            valor = _para_decimal(dados.get("velocidade_dl_minima"))
            if valor is not None:
                escola.velocidade_dl_minima = valor
                atualizado = True
        if escola.kit_inicial is None:
            valor = _para_decimal(dados.get("kit_wifi"))
            if valor is not None:
                escola.kit_inicial = valor
                atualizado = True

        if atualizado:
            escola.save(update_fields=["velocidade_dl_minima", "kit_inicial"])


def reverter_backfill(apps, schema_editor):
    # Irreversivel de forma segura (mesmo motivo da migracao 0003): os
    # campos continuam existindo, sem valores originais para restaurar. Noop
    # deliberado.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('escolas', '0020_target_rede_externa_e_dados_tecnicos_eace'),
    ]

    operations = [
        migrations.RunPython(backfill_velocidade_minima_kit_inicial, reverter_backfill),
    ]
