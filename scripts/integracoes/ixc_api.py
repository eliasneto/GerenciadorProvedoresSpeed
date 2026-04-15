import os
import sys
import requests
import json
import base64
import urllib3
from tqdm import tqdm
import traceback
from django.utils import timezone

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

from clientes.models import Cliente, Endereco, LogAlteracaoIXC, HistoricoSincronizacao
from clientes.sync_utils import descrever_rotina_em_execucao, iniciar_historico_com_trava

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


def extrair_todos_os_clientes(historico):
    pagina_atual = 1
    registros_por_pagina = 50
    base_de_dados_local = []

    res_total = consultar_ixc("cliente", {"qtype": "ativo", "query": "S", "oper": "=", "rp": "1"})
    total_no_ixc = int(res_total.get('total', 0)) if res_total else 0

    print(f"Iniciando extracao de {total_no_ixc} clientes ativos...")
    pbar = tqdm(total=total_no_ixc, desc="Extraindo da API", unit="cli")

    while True:
        historico.refresh_from_db()
        if historico.detalhes == "STOP":
            raise KeyboardInterrupt("Parada solicitada via Admin")

        payload_clientes = {
            "qtype": "ativo", "query": "S", "oper": "=",
            "page": str(pagina_atual), "rp": str(registros_por_pagina),
            "sortname": "id", "sortorder": "asc"
        }

        resposta = consultar_ixc("cliente", payload_clientes)
        if not resposta or 'registros' not in resposta:
            break
        clientes = resposta['registros']
        if not clientes:
            break

        for cliente in clientes:
            id_cli = cliente['id']
            res_logins = consultar_ixc("radusuarios", {"qtype": "id_cliente", "query": id_cli, "oper": "=", "rp": "5000"})
            logins_encontrados = res_logins.get('registros', []) if res_logins else []

            if len(logins_encontrados) > 0:
                dados_completos = {
                    "id_ixc": id_cli,
                    "nome_com_id": f"{id_cli} - {cliente['razao']}",
                    "fantasia": cliente.get('fantasia') or '',
                    "cpf_cnpj": cliente.get('cnpj_cpf') or '',
                    "contratos": [],
                    "logins": [
                        {
                            "id_login": str(l.get('id') or '').strip(),
                            "id_contrato": l.get('id_contrato', ''),
                            "login": l['login'],
                            "ativo": l.get('ativo', 'S'),
                            "circuit_id": str(l.get('agent_circuit_id') or '').strip(),
                            "obs": l.get('obs') or l.get('observacao') or '',
                            "endereco": l.get('endereco') or '',
                            "numero": l.get('numero') or '',
                            "bairro": l.get('bairro') or '',
                            "cidade": l.get('cidade') or '',
                            "uf": l.get('uf') or l.get('estado') or '',
                            "cep": l.get('cep') or '',
                        } for l in logins_encontrados]
                }

                res_con = consultar_ixc("cliente_contrato", {"qtype": "id_cliente", "query": id_cli, "oper": "=", "rp": "5000"})
                if res_con and 'registros' in res_con:
                    for c in res_con['registros']:
                        dados_completos["contratos"].append({
                            "id_contrato": c['id'],
                            "status": c['status'],
                            "endereco": c.get('endereco', ''),
                            "numero": c.get('numero', 'S/N'),
                            "bairro": c.get('bairro', ''),
                            "cidade": c.get('cidade', ''),
                            "uf": c.get('uf', 'CE'),
                            "filial_id": str(c.get('id_filial', '')),
                            "agente_id": c.get('vendedor', ''),
                        })
                base_de_dados_local.append(dados_completos)
            pbar.update(1)
        pagina_atual += 1

    pbar.close()
    return base_de_dados_local


def salvar_clientes_no_django(dados_ixc, mapa_filiais, mapa_cidades, historico):
    print("\nGravando no banco de dados com auditoria...")
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
            con_pai = next((c for c in dado['contratos'] if str(c['id_contrato']) == str(lg['id_contrato'])), {})
            campos_tecnicos = extrair_campos_tecnicos_obs(lg.get('obs'))
            endereco_resolvido = resolver_endereco_login(lg, con_pai, mapa_cidades)

            status_login_ixc = str(lg.get('ativo', 'S')).strip().upper()
            status_contrato_ixc = str(con_pai.get('status', 'A')).strip().upper()

            if status_contrato_ixc in ['C', 'D', 'CM', 'CANCELADO']:
                status_django = 'cancelado'
            elif status_login_ixc == 'N':
                status_django = 'inativo'
            else:
                status_django = 'ativo'

            filial_nova = mapa_filiais.get(con_pai.get('filial_id'), f"Filial {con_pai.get('filial_id')}")
            circuit_id_novo = lg['circuit_id']

            end_atual = Endereco.objects.filter(cliente=cliente_obj, login_ixc=lg['login']).first()
            if end_atual:
                if end_atual.status != status_django:
                    LogAlteracaoIXC.objects.create(cliente=cliente_obj, login_ixc=lg['login'], campo_alterado="status", valor_antigo=end_atual.status, valor_novo=status_django)
                if str(end_atual.agent_circuit_id or '').strip() != circuit_id_novo:
                    LogAlteracaoIXC.objects.create(cliente=cliente_obj, login_ixc=lg['login'], campo_alterado="agent_circuit_id", valor_antigo=end_atual.agent_circuit_id, valor_novo=circuit_id_novo)

            Endereco.objects.update_or_create(
                cliente=cliente_obj,
                login_ixc=lg['login'],
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
                    'status': status_django,
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

    print(f"Carga Total detectada como: {origem_detectada.upper()}")

    historico, rotina_ativa = iniciar_historico_com_trava(
        tipo='total',
        origem=origem_detectada,
        executado_por=usuario_executor,
    )
    if rotina_ativa:
        print(descrever_rotina_em_execucao('total', rotina_ativa))
        raise SystemExit(0)

    try:
        mapa_f = buscar_mapa_filiais()
        mapa_c = buscar_mapa_cidades()
        meus_dados = extrair_todos_os_clientes(historico)
        if meus_dados:
            salvar_clientes_no_django(meus_dados, mapa_f, mapa_c, historico)

        historico.status = 'sucesso'
        historico.registros_processados = len(meus_dados) if meus_dados else 0
        historico.detalhes = f"Carga total concluida via {origem_detectada.upper()}."

    except KeyboardInterrupt as e:
        historico.status = 'erro'
        msg_erro = str(e) if "Parada" in str(e) else "Interrompido manualmente (Ctrl+C)."
        historico.detalhes = msg_erro
        print(f"\n{msg_erro}")

    except Exception:
        historico.status = 'erro'
        historico.detalhes = traceback.format_exc()
        print("Erro fatal registrado no banco.")

    finally:
        historico.data_fim = timezone.now()
        historico.save()
        print(f"Fim da rotina ({origem_detectada}).")
