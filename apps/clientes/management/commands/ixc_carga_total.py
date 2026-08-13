import traceback

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.clientes.sync_utils import descrever_rotina_em_execucao, iniciar_historico_com_trava
from scripts.integracoes.ixc_sync_clientes import (
    buscar_mapa_cidades,
    buscar_mapa_estados,
    buscar_mapa_filiais,
    extrair_todos_os_clientes,
    salvar_clientes_no_django,
)

# Carga total de clientes IXC -> Django. Toda logica de normalizacao e
# acesso ao IXC vive em scripts/integracoes/ixc_sync_clientes.py (PO-022).
# Antes scripts/integracoes/ixc_api.py (PO-034).


class Command(BaseCommand):
    help = "Carga total de clientes/login do IXC para o Django."

    def add_arguments(self, parser):
        parser.add_argument(
            "--manual",
            action="store_true",
            help="Marca a execucao como disparada manualmente (usada pelos botoes do Admin).",
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

        self.stdout.write(f"Carga Total detectada como: {origem_detectada.upper()}")

        historico, rotina_ativa = iniciar_historico_com_trava(
            tipo="total",
            origem=origem_detectada,
            executado_por=usuario_executor,
        )
        if rotina_ativa:
            self.stdout.write(descrever_rotina_em_execucao("total", rotina_ativa))
            return

        meus_dados = None
        try:
            mapa_f = buscar_mapa_filiais()
            mapa_e = buscar_mapa_estados()
            mapa_c = buscar_mapa_cidades(mapa_e)
            meus_dados = extrair_todos_os_clientes(historico)
            if meus_dados:
                salvar_clientes_no_django(meus_dados, mapa_f, mapa_c, historico, mapa_estados=mapa_e)

            historico.status = "sucesso"
            historico.registros_processados = len(meus_dados) if meus_dados else 0
            historico.detalhes = f"Carga total concluida via {origem_detectada.upper()}."

        except KeyboardInterrupt as exc:
            historico.status = "erro"
            msg_erro = str(exc) if "Parada" in str(exc) else "Interrompido manualmente (Ctrl+C)."
            historico.detalhes = msg_erro
            self.stdout.write(f"\n{msg_erro}")

        except Exception:
            historico.status = "erro"
            historico.detalhes = traceback.format_exc()
            self.stdout.write("Erro fatal registrado no banco.")

        finally:
            historico.data_fim = timezone.now()
            historico.save()
            self.stdout.write(f"Fim da rotina ({origem_detectada}).")
