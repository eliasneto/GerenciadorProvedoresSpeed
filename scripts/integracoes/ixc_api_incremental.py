import os
import sys
import requests
import json
import base64
import urllib3
from datetime import datetime, timedelta
from tqdm import tqdm
import traceback

# ==========================================
# CONFIGURACAO DO AMBIENTE DJANGO
# ==========================================
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(DIRETORIO_ATUAL))

if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

APPS_DIR = os.path.join(BASE_DIR, 'apps')
if APPS_DIR not in sys.path:
    sys.path.insert(0, APPS_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from clientes.models import Cliente, Endereco, HistoricoSincronizacao, LogAlteracaoIXC
from clientes.sync_utils import descrever_rotina_em_execucao, iniciar_historico_com_trava
from django.utils import timezone

# ==========================================
# CONFIGURACOES DA API DO IXC
# ==========================================
IXC_URL = "https://megainfraestrutura.com.br/webservice/v1"
IXC_TOKEN = "76:54f35af33ea35f3b8a9a8fa14868322662d0465ebbb63fc56c3fb499ac3e1b61"

token_b64 = base64.b64encode(IXC_TOKEN.encode('utf-8')).decode('utf-8')

HEADERS = {
    'Content-Type': 'application/json',
    'Authorization': f'Basic {token_b64}',
    'ixcsoft': 'listar'
}


def extrair_campos_tecnicos_obs(obs_texto):
    campos = {
        'velocidade': '',
        'tipo_acesso': '',
        'ipv4_bloco': '',
        'dupla_abordagem': '',
        'entrega_rb': '',
    }

    if not obs_texto:
        return campos

    mapa = {
        'VELOCIDADE': 'velocidade',
        'TIPO DE ACESSO': 'tipo_acesso',
        'BLOCO IP': 'ipv4_bloco',
        'DUPLA ABORDAGEM': 'dupla_abordagem',
        'ENTREGA RB': 'entrega_rb',
    }

    for linha in str(obs_texto).splitlines():
        linha_limpa = linha.strip()
        if ':' not in linha_limpa:
            continue
        chave_bruta, valor_bruto = linha_limpa.split(':', 1)
        chave = chave_bruta.strip().upper()
        destino = mapa.get(chave)
        if destino:
            campos[destino] = valor_bruto.strip()

    return campos


def resolver_cidade_ixc(valor_cidade, mapa_cidades):
    cidade_bruta = str(valor_cidade or '').strip()
    if not cidade_bruta:
        return '', ''

    if cidade_bruta.isdigit():
        cidade_nome = mapa_cidades.get(cidade_bruta, '').strip()
        if cidade_nome:
            return cidade_nome, cidade_bruta

        cidade_detalhe = consultar_ixc(f"cidade/{cidade_bruta}", {})
        if cidade_detalhe:
            cidade_nome = (
                cidade_detalhe.get('cidade')
                or cidade_detalhe.get('nome')
                or cidade_detalhe.get('municipio')
                or cidade_detalhe.get('descricao')
                or ''
            )
            cidade_nome = str(cidade_nome).strip()
            if cidade_nome:
                mapa_cidades[cidade_bruta] = cidade_nome
                return cidade_nome, cidade_bruta

        return '', cidade_bruta

    return cidade_bruta, ''


def resolver_endereco_login(login_data, contrato_data, mapa_cidades):
    endereco_login = str(login_data.get('endereco') or '').strip()
    numero_login = str(login_data.get('numero') or '').strip()
    bairro_login = str(login_data.get('bairro') or '').strip()
    cidade_login = str(login_data.get('cidade') or '').strip()
    estado_login = str(login_data.get('uf') or login_data.get('estado') or '').strip()
    cep_login = str(login_data.get('cep') or '').strip()

    usa_endereco_login = any(
        [endereco_login, numero_login, bairro_login, cidade_login, estado_login, cep_login]
    )

    if usa_endereco_login:
        cidade_nome, cidade_id_ixc = resolver_cidade_ixc(cidade_login, mapa_cidades)
        return {
            'cep': cep_login,
            'logradouro': endereco_login or 'Nao informado',
            'numero': numero_login or 'S/N',
            'bairro': bairro_login,
            'cidade': cidade_nome,
            'cidade_id_ixc': cidade_id_ixc,
            'estado': (estado_login[:2].upper() if estado_login else 'CE'),
        }

    cidade_nome_contrato, cidade_id_ixc_contrato = resolver_cidade_ixc(contrato_data.get('cidade', ''), mapa_cidades)
    return {
        'cep': str(contrato_data.get('cep') or '').strip(),
        'logradouro': contrato_data.get('endereco') or 'Nao informado',
        'numero': contrato_data.get('numero') or 'S/N',
        'bairro': contrato_data.get('bairro', ''),
        'cidade': cidade_nome_contrato,
        'cidade_id_ixc': cidade_id_ixc_contrato,
        'estado': str(contrato_data.get('uf', 'CE'))[:2].upper(),
    }


def consultar_ixc(tabela, payload):
    url = f"{IXC_URL}/{tabela}"
    try:
        response = requests.post(url, headers=HEADERS, data=json.dumps(payload), verify=False)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def buscar_mapa_filiais():
    print("Mapeando nomes das filiais no IXC...")
    payload = {"qtype": "id", "query": "0", "oper": ">", "page": "1", "rp": "100"}
    res = consultar_ixc("filial", payload)
    mapa = {}
    if res and 'registros' in res:
        for f in res['registros']:
            mapa[str(f['id'])] = f.get('razao') or f.get('filial') or f"Filial {f['id']}"
    return mapa


def buscar_mapa_cidades():
    print("Mapeando nomes das cidades no IXC...")
    payload = {"qtype": "id", "query": "0", "oper": ">", "page": "1", "rp": "10000"}
    res = consultar_ixc("cidade", payload)
    mapa = {}
    if res and 'registros' in res:
        for cidade in res['registros']:
            cidade_id = str(cidade.get('id') or '').strip()
            cidade_nome = (
                cidade.get('cidade')
                or cidade.get('nome')
                or cidade.get('municipio')
                or cidade.get('descricao')
                or ''
            )
            if cidade_id:
                mapa[cidade_id] = str(cidade_nome).strip()
    return mapa


def extrair_clientes_recentes(historico, dias_retroativos=0):
    data_limite = (datetime.now() - timedelta(days=dias_retroativos)).strftime('%Y-%m-%d 00:00:00')
    ids_para_processar = set()

    print(f"Buscando novidades desde {data_limite}...")

    payload_cli = {
        "qtype": "data_atualizacao", "query": data_limite, "oper": ">=",
        "rp": "200", "sortname": "data_atualizacao", "sortorder": "desc"
    }
    res_cli = consultar_ixc("cliente", payload_cli)
    if res_cli and 'registros' in res_cli:
        for c in res_cli['registros']:
            ids_para_processar.add(str(c['id']))

    payload_logins = {
        "qtype": "id", "query": "0", "oper": ">",
        "rp": "100", "sortname": "id", "sortorder": "desc"
    }
    res_logins_recentes = consultar_ixc("radusuarios", payload_logins)
    if res_logins_recentes and 'registros' in res_logins_recentes:
        for l in res_logins_recentes['registros']:
            ids_para_processar.add(str(l['id_cliente']))

    if not ids_para_processar:
        print("Nada de novo encontrado no IXC.")
        return []

    print(f"Sincronizando detalhes de {len(ids_para_processar)} clientes...")

    base_de_dados_local = []
    pbar = tqdm(total=len(ids_para_processar), desc="Processando IXC", unit="cli")

    for id_cli in ids_para_processar:
        historico.refresh_from_db()
        if historico.detalhes == "STOP":
            raise KeyboardInterrupt("Parada solicitada via Admin")

        cliente = consultar_ixc(f"cliente/{id_cli}", {})
        if not cliente or 'id' not in cliente:
            pbar.update(1)
            continue

        res_logins = consultar_ixc("radusuarios", {"qtype": "id_cliente", "query": id_cli, "oper": "=", "rp": "50"})
        logins_encontrados = []
        if res_logins and 'registros' in res_logins:
            for l in res_logins['registros']:
                logins_encontrados.append({
                    "id_login": str(l.get('id') or '').strip(),
                    "id_contrato": l.get('id_contrato', ''),
                    "login": l['login'],
                    "ativo": l.get('ativo', 'S'),
                    "agent_circuit_id": l.get('agent_circuit_id', ''),
                    "obs": l.get('obs') or l.get('observacao') or '',
                    "endereco": l.get('endereco') or '',
                    "numero": l.get('numero') or '',
                    "bairro": l.get('bairro') or '',
                    "cidade": l.get('cidade') or '',
                    "uf": l.get('uf') or l.get('estado') or '',
                    "cep": l.get('cep') or '',
                })

        res_con = consultar_ixc("cliente_contrato", {"qtype": "id_cliente", "query": id_cli, "oper": "=", "rp": "50"})
        contratos_encontrados = res_con.get('registros', []) if res_con else []

        base_de_dados_local.append({
            "id_ixc": id_cli,
            "nome_com_id": f"{id_cli} - {cliente['razao']}",
            "fantasia": cliente.get('fantasia') or '',
            "cpf_cnpj": cliente.get('cnpj_cpf') or '',
            "contratos": contratos_encontrados,
            "logins": logins_encontrados,
        })
        pbar.update(1)

    pbar.close()
    return base_de_dados_local


def salvar_clientes_no_django(dados_ixc, mapa_filiais, mapa_cidades, historico):
    if not dados_ixc:
        return

    print("\nGravando e auditando alteracoes no banco...")
    pbar_save = tqdm(total=len(dados_ixc), desc="Gravando no Banco", unit="cli")

    for dado in dados_ixc:
        historico.refresh_from_db()
        if historico.detalhes == "STOP":
            raise KeyboardInterrupt("Parada solicitada via Admin")

        id_ixc = dado['id_ixc']
        cnpj_novo = str(dado.get('cpf_cnpj') or '').strip()
        razao_nova = dado['nome_com_id']

        cliente_obj = Cliente.objects.filter(id_ixc=id_ixc).first()
        if cliente_obj:
            if cliente_obj.cnpj_cpf != cnpj_novo:
                LogAlteracaoIXC.objects.create(cliente=cliente_obj, campo_alterado="cnpj_cpf", valor_antigo=cliente_obj.cnpj_cpf, valor_novo=cnpj_novo)
            if cliente_obj.razao_social != razao_nova:
                LogAlteracaoIXC.objects.create(cliente=cliente_obj, campo_alterado="razao_social", valor_antigo=cliente_obj.razao_social, valor_novo=razao_nova)

        cliente_obj, _ = Cliente.objects.update_or_create(
            id_ixc=id_ixc,
            defaults={
                'cnpj_cpf': cnpj_novo,
                'razao_social': razao_nova,
                'nome_fantasia': dado['fantasia'],
            }
        )

        for lg in dado.get('logins', []):
            login_nome = lg['login']
            circuit_id_novo = lg.get('agent_circuit_id', '')
            con_pai = next((c for c in dado['contratos'] if str(c['id_contrato']) == str(lg['id_contrato'])), {})
            campos_tecnicos = extrair_campos_tecnicos_obs(lg.get('obs'))
            endereco_resolvido = resolver_endereco_login(lg, con_pai, mapa_cidades)

            status_login_ixc = str(lg.get('ativo', 'S')).strip().upper()
            status_con_ixc = str(con_pai.get('status', 'A')).strip().upper()
            status_novo = 'cancelado' if status_con_ixc in ['C', 'D', 'CM', 'CANCELADO'] else ('inativo' if status_login_ixc == 'N' else 'ativo')
            filial_nova = mapa_filiais.get(str(con_pai.get('id_filial')), "Filial Nao Informada")

            end_atual = Endereco.objects.filter(cliente=cliente_obj, login_ixc=login_nome).first()
            if end_atual:
                if end_atual.status != status_novo:
                    LogAlteracaoIXC.objects.create(cliente=cliente_obj, login_ixc=login_nome, campo_alterado="status", valor_antigo=end_atual.status, valor_novo=status_novo)
                if end_atual.filial_ixc != filial_nova:
                    LogAlteracaoIXC.objects.create(cliente=cliente_obj, login_ixc=login_nome, campo_alterado="filial", valor_antigo=end_atual.filial_ixc, valor_novo=filial_nova)
                if str(end_atual.agent_circuit_id) != str(circuit_id_novo):
                    LogAlteracaoIXC.objects.create(cliente=cliente_obj, login_ixc=login_nome, campo_alterado="agent_circuit_id", valor_antigo=end_atual.agent_circuit_id, valor_novo=circuit_id_novo)

            Endereco.objects.update_or_create(
                cliente=cliente_obj,
                login_ixc=login_nome,
                defaults={
                    'cep': endereco_resolvido['cep'],
                    'logradouro': endereco_resolvido['logradouro'],
                    'numero': endereco_resolvido['numero'],
                    'bairro': endereco_resolvido['bairro'],
                    'cidade': endereco_resolvido['cidade'],
                    'cidade_id_ixc': endereco_resolvido['cidade_id_ixc'],
                    'estado': endereco_resolvido['estado'],
                    'login_id_ixc': str(lg.get('id_login') or '').strip() or None,
                    'contrato_id_ixc': str(lg.get('id_contrato') or '').strip() or None,
                    'filial_ixc': filial_nova,
                    'agent_circuit_id': circuit_id_novo,
                    'status': status_novo,
                    'velocidade': campos_tecnicos.get('velocidade') or None,
                    'tipo_acesso': campos_tecnicos.get('tipo_acesso') or None,
                    'ipv4_bloco': campos_tecnicos.get('ipv4_bloco') or None,
                    'dupla_abordagem': campos_tecnicos.get('dupla_abordagem') or None,
                    'entrega_rb': campos_tecnicos.get('entrega_rb') or None,
                }
            )
        pbar_save.update(1)

    pbar_save.close()


if __name__ == "__main__":
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    eh_manual = 'manual' in sys.argv
    origem_detectada = 'manual' if eh_manual else 'automatica'

    usuario_executor = None
    if eh_manual:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        usuario_executor = User.objects.filter(is_superuser=True).first()

    print(f"Incremental detectado como: {origem_detectada.upper()}")

    historico, rotina_ativa = iniciar_historico_com_trava(
        tipo='incremental',
        origem=origem_detectada,
        executado_por=usuario_executor,
    )
    if rotina_ativa:
        print(descrever_rotina_em_execucao('incremental', rotina_ativa))
        raise SystemExit(0)

    try:
        mapa_f = buscar_mapa_filiais()
        mapa_c = buscar_mapa_cidades()
        dias = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 0
        meus_dados = extrair_clientes_recentes(historico, dias_retroativos=dias)

        if meus_dados:
            salvar_clientes_no_django(meus_dados, mapa_f, mapa_c, historico)
            historico.registros_processados = len(meus_dados)
            historico.detalhes = f"Sincronizacao {origem_detectada} concluida. {len(meus_dados)} clientes atualizados."
        else:
            historico.registros_processados = 0
            historico.detalhes = "Nenhuma alteracao detectada no IXC para o periodo informado."

        historico.status = 'sucesso'

    except KeyboardInterrupt as e:
        historico.status = 'erro'
        msg = str(e) if "Parada" in str(e) else "Sincronizacao interrompida manualmente (Ctrl+C)."
        historico.detalhes = msg
        print(f"\n{msg}")

    except Exception:
        historico.status = 'erro'
        historico.detalhes = traceback.format_exc()
        print("Erro fatal registrado no banco.")

    finally:
        historico.data_fim = timezone.now()
        historico.save()
        print(f"Fim da rotina {historico.tipo} ({origem_detectada}).")
