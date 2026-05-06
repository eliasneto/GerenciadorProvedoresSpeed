import os
import sys
import json
import base64
import traceback

import requests
import urllib3
from tqdm import tqdm


# Esta integracao e separada da carga principal de clientes/logins de proposito:
# 1. Cliente e endereco mudam em um ritmo.
# 2. Ticket/primeira OS muda em outro ritmo e pode exigir consultas extras.
# 3. Assim conseguimos enriquecer apenas os logins ja sincronizados, sem deixar
#    a rotina principal do IXC pesada demais.

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

from django.utils import timezone

from clientes.models import Endereco, HistoricoSincronizacao


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

IXC_URL = "https://megainfraestrutura.com.br/webservice/v1"
IXC_TOKEN = "76:54f35af33ea35f3b8a9a8fa14868322662d0465ebbb63fc56c3fb499ac3e1b61"

TOKEN_B64 = base64.b64encode(IXC_TOKEN.encode('utf-8')).decode('utf-8')
HEADERS = {
    'Content-Type': 'application/json',
    'Authorization': f'Basic {TOKEN_B64}',
    'ixcsoft': 'listar',
}


def consultar_ixc(tabela, payload):
    url = f"{IXC_URL}/{tabela}"
    try:
        response = requests.post(url, headers=HEADERS, data=json.dumps(payload), verify=False, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def buscar_mapa_setores():
    candidatos = ["ticket_setor", "su_ticket_setor", "setor"]
    mapa = {}

    for tabela in candidatos:
        resposta = consultar_ixc(tabela, {
            "qtype": "id",
            "query": "0",
            "oper": ">",
            "page": "1",
            "rp": "1000",
            "sortname": "id",
            "sortorder": "asc",
        })
        registros = resposta.get('registros', []) if resposta else []
        if not registros:
            continue

        for registro in registros:
            setor_id = normalizar_texto(registro.get('id'))
            setor_nome = primeiro_preenchido(registro, ['setor', 'nome', 'descricao', 'titulo'])
            if setor_id and setor_nome:
                mapa[setor_id] = setor_nome

        if mapa:
            break

    return mapa


def normalizar_texto(valor):
    texto = str(valor or '').strip()
    return texto or ''


def primeiro_preenchido(registro, chaves):
    for chave in chaves:
        valor = normalizar_texto(registro.get(chave))
        if valor:
            return valor
    return ''


def buscar_ticket_atual_por_endereco(endereco):
    # Prioriza o ticket/OS atual do proprio login.
    # Isso reduz drasticamente o custo comparado ao historico inteiro por contrato.
    if endereco.login_id_ixc:
        resposta = consultar_ixc("su_ticket", {
            "qtype": "id_login",
            "query": endereco.login_id_ixc,
            "oper": "=",
            "page": "1",
            "rp": "1",
            "sortname": "id",
            "sortorder": "desc",
        })
        registros = resposta.get('registros', []) if resposta else []
        if registros:
            return registros[0]

    # Fallback apenas para casos sem login_id_ixc.
    if endereco.contrato_id_ixc:
        resposta = consultar_ixc("su_ticket", {
            "qtype": "id_contrato",
            "query": endereco.contrato_id_ixc,
            "oper": "=",
            "page": "1",
            "rp": "1",
            "sortname": "id",
            "sortorder": "desc",
        })
        registros = resposta.get('registros', []) if resposta else []
        if registros:
            return registros[0]

    return None


def selecionar_os_mais_relevante(registros):
    if not registros:
        return None

    status_aberto = {
        'aberta', 'aberto', 'em aberto', 'ab', 'a', 'osab', 'andamento', 'em andamento'
    }

    def chave_ordenacao(registro):
        status = (
            normalizar_texto(registro.get('status'))
            or normalizar_texto(registro.get('status_os'))
            or normalizar_texto(registro.get('situacao'))
            or normalizar_texto(registro.get('status_texto'))
        ).lower()
        registro_id = normalizar_texto(registro.get('id'))
        try:
            registro_id_int = int(registro_id)
        except Exception:
            registro_id_int = 0
        return (1 if status in status_aberto else 0, registro_id_int)

    return sorted(registros, key=chave_ordenacao, reverse=True)[0]


def buscar_os_atual_por_ticket(ticket_id):
    if not ticket_id:
        return None

    candidatos = [
        ("su_os", ["id_ticket", "id_atendimento", "id_su_ticket", "id_chamado"]),
        ("su_ordem_servico", ["id_ticket", "id_atendimento", "id_su_ticket", "id_chamado"]),
        ("ordem_servico", ["id_ticket", "id_atendimento", "id_su_ticket", "id_chamado"]),
        ("su_oss_chamado", ["id_ticket", "id_atendimento", "id_su_ticket", "id_chamado"]),
        ("su_oss", ["id_ticket", "id_atendimento", "id_su_ticket", "id_chamado"]),
    ]

    for tabela, qtypes in candidatos:
        for qtype in qtypes:
            resposta = consultar_ixc(tabela, {
                "qtype": qtype,
                "query": str(ticket_id),
                "oper": "=",
                "page": "1",
                "rp": "20",
                "sortname": "id",
                "sortorder": "desc",
            })
            registros = resposta.get('registros', []) if resposta else []
            if registros:
                registro = selecionar_os_mais_relevante(registros)
                if registro:
                    return registro

    return None


def extrair_setor_registro(registro, mapa_setores):
    if not registro:
        return None, None

    setor_id = primeiro_preenchido(
        registro,
        ['id_setor', 'id_ticket_setor', 'ticket_setor_id', 'setor_id', 'departamento_id']
    )
    setor_nome = primeiro_preenchido(
        registro,
        ['setor', 'ticket_setor', 'departamento', 'nome_setor', 'setor_nome']
    )
    if not setor_nome and setor_id and mapa_setores:
        setor_nome = mapa_setores.get(setor_id, '')
    return setor_id or None, setor_nome or None


def extrair_snapshot_primeira_os(registro_ticket, mapa_setores=None):
    if not registro_ticket:
        return {
            'ticket_os_atual_ixc': None,
            'setor_os_atual_id_ixc': None,
            'setor_os_atual_nome': None,
        }

    ticket_id = primeiro_preenchido(registro_ticket, ['id', 'id_ticket'])
    os_atual = buscar_os_atual_por_ticket(ticket_id)
    os_id = primeiro_preenchido(os_atual or {}, ['id', 'id_os', 'id_ordem_servico'])

    setor_id, setor_nome = extrair_setor_registro(os_atual, mapa_setores)
    if not setor_id and not setor_nome:
        setor_id, setor_nome = extrair_setor_registro(registro_ticket, mapa_setores)

    return {
        'ticket_os_atual_ixc': os_id or ticket_id or None,
        'setor_os_atual_id_ixc': setor_id or None,
        'setor_os_atual_nome': setor_nome or None,
    }


def sincronizar_primeira_os(historico):
    queryset = Endereco.objects.exclude(login_ixc__isnull=True).exclude(login_ixc='').order_by('id')
    total = queryset.count()
    mapa_setores = buscar_mapa_setores()
    pbar = tqdm(total=total, desc="Enriquecendo primeira OS", unit="end")

    for endereco in queryset.iterator():
        historico.refresh_from_db()
        if historico.detalhes == "STOP":
            raise KeyboardInterrupt("Parada solicitada via Admin")

        registro_ticket = buscar_ticket_atual_por_endereco(endereco)
        snapshot = extrair_snapshot_primeira_os(registro_ticket, mapa_setores)

        update_fields = []
        for campo, valor in snapshot.items():
            if getattr(endereco, campo) != valor:
                setattr(endereco, campo, valor)
                update_fields.append(campo)

        if update_fields:
            endereco.save(update_fields=update_fields)

        pbar.update(1)

    pbar.close()
    return total


if __name__ == "__main__":
    eh_manual = 'manual' in sys.argv
    origem_detectada = 'manual' if eh_manual else 'automatica'

    usuario_executor = None
    if eh_manual:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        usuario_executor = User.objects.filter(is_superuser=True).first()

    historico = HistoricoSincronizacao.objects.create(
        tipo='incremental',
        status='rodando',
        origem=origem_detectada,
        executado_por=usuario_executor,
        detalhes='Enriquecimento da primeira OS por login/contrato IXC.',
    )

    try:
        total_processado = sincronizar_primeira_os(historico)
        historico.status = 'sucesso'
        historico.registros_processados = total_processado
        historico.detalhes = 'Enriquecimento da primeira OS concluido com sucesso.'
    except KeyboardInterrupt as exc:
        historico.status = 'erro'
        historico.detalhes = str(exc)
        print(str(exc))
    except Exception:
        historico.status = 'erro'
        historico.detalhes = traceback.format_exc()
        print("Erro fatal ao enriquecer primeira OS.")
    finally:
        historico.data_fim = timezone.now()
        historico.save()
