import traceback

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from tqdm import tqdm

from apps.clientes.models import Cliente, ClienteExcluido, Endereco, EnderecoExcluido
from apps.clientes.sync_utils import descrever_rotina_em_execucao, iniciar_historico_com_trava
from apps.integracoes.ixc.client import IXCClient

# Toda leitura do IXC passa pelo IXCClient (ADR-005, PO-025).
# Antes scripts/integracoes/ixc_faxina.py (PO-034).


def consultar_ixc(tabela, payload):
    status_code, body = IXCClient().listar(tabela, payload)
    if status_code is None or not (200 <= status_code < 300):
        return None
    if not isinstance(body, dict) or 'raw' in body:
        return None
    return body


def executar_faxina(historico):
    print("🧹 Iniciando busca por clientes e logins removidos no IXC...")

    payload_cli = {"qtype": "id", "query": "0", "oper": ">", "rp": "20000"}
    resposta_cli = consultar_ixc("cliente", payload_cli)

    if not resposta_cli or 'registros' not in resposta_cli:
        raise Exception("❌ Erro ao conectar com IXC. Faxina abortada.")

    ids_clientes_ixc = {str(r['id']) for r in resposta_cli['registros']}

    payload_logins = {"qtype": "id", "query": "0", "oper": ">", "rp": "50000"}
    resposta_logins = consultar_ixc("radusuarios", payload_logins)
    logins_ixc = {str(r['login']).strip() for r in resposta_logins.get('registros', [])} if resposta_logins else set()

    clientes_locais = Cliente.objects.all()
    clientes_removidos = 0
    logins_removidos = 0

    print(f"🔍 Comparando {clientes_locais.count()} clientes locais com o IXC...")

    # --- FASE 1: CLIENTES ---
    for cli in tqdm(clientes_locais, desc="Auditando Clientes", unit="cli"):
        # 🛑 CHECK DE PARADA
        historico.refresh_from_db()
        if historico.detalhes == "STOP":
            raise KeyboardInterrupt("Faxina interrompida via Admin")

        if str(cli.id_ixc) not in ids_clientes_ixc:
            lixo_cli = ClienteExcluido.objects.create(
                id_ixc=cli.id_ixc,
                razao_social=cli.razao_social,
                cnpj_cpf=cli.cnpj_cpf,
                dados_completos_json={
                    "fantasia": getattr(cli, 'nome_fantasia', ''),
                    "email": getattr(cli, 'email', ''),
                    "telefone": getattr(cli, 'telefone', ''),
                    "contato": getattr(cli, 'contato_nome', '')
                },
                data_exclusao=timezone.now()
            )

            for end in cli.enderecos.all():
                EnderecoExcluido.objects.create(
                    cliente_excluido=lixo_cli,
                    login_ixc=end.login_ixc,
                    agent_circuit_id=end.agent_circuit_id,
                    detalhes_json={
                        "filial": end.filial_ixc,
                        "cidade": end.cidade,
                        "logradouro": end.logradouro,
                        "numero": end.numero,
                        "status_na_epoca": end.status
                    }
                )

            cli.delete()
            clientes_removidos += 1

    # --- FASE 2: LOGINS ---
    enderecos_locais = Endereco.objects.all()
    print(f"\n🔍 Verificando {enderecos_locais.count()} logins locais...")

    for end in tqdm(enderecos_locais, desc="Auditando Logins", unit="login"):
        # 🛑 CHECK DE PARADA
        historico.refresh_from_db()
        if historico.detalhes == "STOP":
            raise KeyboardInterrupt("Faxina interrompida via Admin")

        login_atual = str(end.login_ixc).strip()
        if not login_atual or login_atual == "MANUAL / SEM LOGIN":
            continue

        if login_atual not in logins_ixc:
            end.delete()
            logins_removidos += 1

    return clientes_removidos + logins_removidos


class Command(BaseCommand):
    help = "Remove do Django os clientes/logins que nao existem mais no IXC."

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

        print(f"🤖 Faxina detectada como: {origem_detectada.upper()}")

        historico, rotina_ativa = iniciar_historico_com_trava(
            tipo='faxina',
            origem=origem_detectada,
            executado_por=usuario_executor,
        )
        if rotina_ativa:
            print(descrever_rotina_em_execucao('faxina', rotina_ativa))
            return

        try:
            total_removidos = executar_faxina(historico)

            historico.status = 'sucesso'
            historico.registros_processados = total_removidos
            historico.detalhes = f"Faxina concluída via {origem_detectada}. {total_removidos} registros movidos para o lixo."

        except KeyboardInterrupt as exc:
            historico.status = 'erro'
            msg_erro = str(exc) if "Parada" in str(exc) else "Faxina interrompida manualmente (Ctrl+C)."
            historico.detalhes = msg_erro
            print(f"\n⚠️ {msg_erro}")

        except Exception as exc:
            historico.status = 'erro'
            historico.detalhes = traceback.format_exc()
            print(f"❌ Erro fatal registrado no banco: {str(exc)}")

        finally:
            historico.data_fim = timezone.now()
            historico.save()
            print(f"✅ Fim da rotina {historico.tipo} ({origem_detectada}).")
