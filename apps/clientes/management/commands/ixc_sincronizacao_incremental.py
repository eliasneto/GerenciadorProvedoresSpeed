import traceback

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.clientes.sync_utils import descrever_rotina_em_execucao, iniciar_historico_com_trava
from scripts.integracoes.ixc_sync_clientes import (
    buscar_mapa_cidades,
    buscar_mapa_estados,
    buscar_mapa_filiais,
    extrair_clientes_recentes,
    salvar_clientes_no_django,
)

# Carga incremental de clientes IXC -> Django. Toda logica de normalizacao e
# acesso ao IXC vive em scripts/integracoes/ixc_sync_clientes.py (PO-022).
# Antes scripts/integracoes/ixc_api_incremental.py (PO-034).


class Command(BaseCommand):
    help = "Sincronizacao incremental de clientes/login do IXC para o Django."

    def add_arguments(self, parser):
        parser.add_argument(
            "--manual",
            action="store_true",
            help="Marca a execucao como disparada manualmente (usada pelos botoes do Admin).",
        )
        parser.add_argument(
            "--dias-retroativos",
            type=int,
            default=0,
            help="Quantidade de dias retroativos a considerar na busca incremental.",
        )

    def handle(self, *args, **options):
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        eh_manual = options["manual"]
        origem_detectada = "manual" if eh_manual else "automatica"

        usuario_executor = None
        if eh_manual:
            User = get_user_model()
            usuario_executor = User.objects.filter(is_superuser=True).first()

        self.stdout.write(f"Incremental detectado como: {origem_detectada.upper()}")

        historico, rotina_ativa = iniciar_historico_com_trava(
            tipo="incremental",
            origem=origem_detectada,
            executado_por=usuario_executor,
        )
        if rotina_ativa:
            self.stdout.write(descrever_rotina_em_execucao("incremental", rotina_ativa))
            return

        try:
            mapa_f = buscar_mapa_filiais()
            mapa_e = buscar_mapa_estados()
            mapa_c = buscar_mapa_cidades(mapa_e)
            dias = options["dias_retroativos"]
            meus_dados = extrair_clientes_recentes(historico, dias_retroativos=dias)

            if meus_dados:
                salvar_clientes_no_django(meus_dados, mapa_f, mapa_c, historico, mapa_estados=mapa_e)
                historico.registros_processados = len(meus_dados)
                historico.detalhes = f"Sincronizacao {origem_detectada} concluida. {len(meus_dados)} clientes atualizados."
            else:
                historico.registros_processados = 0
                historico.detalhes = "Nenhuma alteracao detectada no IXC para o periodo informado."

            historico.status = "sucesso"

        except KeyboardInterrupt as exc:
            historico.status = "erro"
            msg = str(exc) if "Parada" in str(exc) else "Sincronizacao interrompida manualmente (Ctrl+C)."
            historico.detalhes = msg
            self.stdout.write(f"\n{msg}")

        except Exception:
            historico.status = "erro"
            historico.detalhes = traceback.format_exc()
            self.stdout.write("Erro fatal registrado no banco.")

        finally:
            historico.data_fim = timezone.now()
            historico.save()
            self.stdout.write(f"Fim da rotina {historico.tipo} ({origem_detectada}).")
