import os
import sys
import json
import base64
import traceback
import time
from collections import defaultdict
from datetime import datetime, timedelta

import requests
import urllib3
from tqdm import tqdm


# Rotina enxuta para separar rapidamente os logins ativos cujo ticket/OS atual
# pertence ao setor "Comercial | Lastmile".
# Ela existe em paralelo a ixc_primeira_os.py, que continua sendo a rotina
# mais completa de enriquecimento operacional.

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
from django.db.models import Count

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

ALVO_SETOR_NOME = "comercial | lastmile"


def log_etapa(inicio, mensagem):
    decorrido = time.perf_counter() - inicio
    print(f"[{decorrido:8.1f}s] {mensagem}", flush=True)


def consultar_ixc(tabela, payload):
    url = f"{IXC_URL}/{tabela}"
    try:
        response = requests.post(url, headers=HEADERS, data=json.dumps(payload), verify=False, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def normalizar_texto(valor):
    return str(valor or '').strip()


def obter_data_corte_args():
    prefixos_data = ["--os-alterada-desde=", "--alterado-desde="]
    prefixos_dias = ["--os-alterada-nos-ultimos-dias=", "--alterado-nos-ultimos-dias="]
    data_corte = None

    for arg in sys.argv[1:]:
        for prefixo in prefixos_data:
            if arg.startswith(prefixo):
                valor = arg.split("=", 1)[1].strip()
                if not valor:
                    return None
                try:
                    data_corte = datetime.strptime(valor, "%Y-%m-%d")
                except ValueError:
                    print(
                        f"Data invalida em {arg!r}. Use o formato YYYY-MM-DD, por exemplo 2026-03-08."
                    )
                    raise SystemExit(1)
                break
        else:
            for prefixo_dias in prefixos_dias:
                if arg.startswith(prefixo_dias):
                    valor = arg.split("=", 1)[1].strip()
                    if not valor:
                        return None
                    try:
                        dias = int(valor)
                    except ValueError:
                        print(
                            f"Valor invalido em {arg!r}. Use um inteiro, por exemplo --os-alterada-nos-ultimos-dias=10."
                        )
                        raise SystemExit(1)
                    if dias < 0:
                        print(
                            f"Valor invalido em {arg!r}. A quantidade de dias nao pode ser negativa."
                        )
                        raise SystemExit(1)
                    data_corte = datetime.now() - timedelta(days=dias)
                    break

    return data_corte


def obter_filtro_cliente_args():
    prefixo_local = "--cliente-local-id="
    prefixo_ixc = "--cliente-ixc-id="
    cliente_local_id = None
    cliente_ixc_id = None

    for arg in sys.argv[1:]:
        if arg.startswith(prefixo_local):
            cliente_local_id = arg.split("=", 1)[1].strip() or None
        elif arg.startswith(prefixo_ixc):
            cliente_ixc_id = arg.split("=", 1)[1].strip() or None

    return cliente_local_id, cliente_ixc_id


def parse_data_ixc(valor):
    texto = normalizar_texto(valor)
    if not texto:
        return None

    formatos = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
    ]
    for formato in formatos:
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            continue
    return None


def buscar_mapa_setores():
    inicio = time.perf_counter()
    log_etapa(inicio, "Carregando mapa de setores do IXC...")
    candidatos = ["ticket_setor", "su_ticket_setor", "setor"]
    mapa = {}

    for tabela in candidatos:
        log_etapa(inicio, f"Tentando carregar setores pela tabela '{tabela}'...")
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
            setor_nome = (
                normalizar_texto(registro.get('setor'))
                or normalizar_texto(registro.get('nome'))
                or normalizar_texto(registro.get('descricao'))
                or normalizar_texto(registro.get('titulo'))
            )
            if setor_id and setor_nome:
                mapa[setor_id] = setor_nome

        if mapa:
            log_etapa(inicio, f"Mapa de setores carregado pela tabela '{tabela}' com {len(mapa)} setor(es).")
            break

    if not mapa:
        log_etapa(inicio, "Nenhum mapa de setores foi retornado pelo IXC.")

    return mapa


def buscar_ticket_atual_por_login(endereco):
    if not endereco.login_id_ixc:
        return None

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
    return registros[0] if registros else None


def status_indica_os_ativa(registro):
    status = extrair_status_registro(registro).lower()
    return status in {
        'aberta', 'aberto', 'em aberto', 'ab', 'a', 'osab',
        'andamento', 'em andamento', 'aguardando', 'pendente',
        'em progresso', 'progress', 'progresso'
    }


def extrair_status_registro(registro):
    if not registro:
        return ''
    return (
        normalizar_texto(registro.get('status'))
        or normalizar_texto(registro.get('status_os'))
        or normalizar_texto(registro.get('situacao'))
        or normalizar_texto(registro.get('status_texto'))
        or normalizar_texto(registro.get('status_label'))
    )


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
                    registro["_origem_tabela_ixc"] = tabela
                    registro["_origem_qtype_ixc"] = qtype
                    return registro

    return None


def buscar_id_setor_alvo(mapa_setores):
    for setor_id, setor_nome in mapa_setores.items():
        if normalizar_texto(setor_nome).lower() == ALVO_SETOR_NOME:
            return setor_id
    return None


def consultar_todos_registros(tabela, payload_base, limite_paginas=100):
    inicio = time.perf_counter()
    print(
        f"[     0.0s] Consultando IXC em lote: tabela='{tabela}', "
        f"qtype='{payload_base.get('qtype')}', query='{payload_base.get('query')}'",
        flush=True
    )
    todos = []
    for pagina in range(1, limite_paginas + 1):
        payload = dict(payload_base)
        payload["page"] = str(pagina)
        resposta = consultar_ixc(tabela, payload)
        registros = resposta.get('registros', []) if resposta else []
        if not registros:
            log_etapa(inicio, f"Sem registros na pagina {pagina}. Encerrando consulta em lote.")
            break
        todos.extend(registros)

        total = int(normalizar_texto(resposta.get('total')) or 0)
        log_etapa(inicio, f"Pagina {pagina} recebida com {len(registros)} registro(s). Acumulado: {len(todos)}.")
        if total and len(todos) >= total:
            log_etapa(inicio, f"Total informado pelo IXC atingido: {total}.")
            break
    return todos


def extrair_ids_vinculo_os(registro):
    return {
        "os_id": (
            normalizar_texto(registro.get('id'))
            or normalizar_texto(registro.get('id_os'))
            or normalizar_texto(registro.get('id_ordem_servico'))
            or None
        ),
        "ticket_id": (
            normalizar_texto(registro.get('id_ticket'))
            or normalizar_texto(registro.get('id_atendimento'))
            or normalizar_texto(registro.get('id_su_ticket'))
            or normalizar_texto(registro.get('id_chamado'))
            or None
        ),
        "login_id": (
            normalizar_texto(registro.get('id_login'))
            or normalizar_texto(registro.get('login_id'))
            or None
        ),
    }


def buscar_os_lastmile_em_lote(mapa_setores, alterado_desde=None):
    inicio = time.perf_counter()
    log_etapa(inicio, "Iniciando busca em lote das O.S. de Comercial | Lastmile...")
    setor_alvo_id = buscar_id_setor_alvo(mapa_setores)
    if not setor_alvo_id:
        log_etapa(inicio, "Setor alvo Comercial | Lastmile nao encontrado no mapa de setores.")
        return {}
    log_etapa(inicio, f"Setor alvo encontrado no IXC: id={setor_alvo_id}.")

    candidatos = [
        ("su_os", ["id_setor", "setor_id", "id_ticket_setor", "departamento_id"]),
        ("su_ordem_servico", ["id_setor", "setor_id", "id_ticket_setor", "departamento_id"]),
        ("ordem_servico", ["id_setor", "setor_id", "id_ticket_setor", "departamento_id"]),
        ("su_oss_chamado", ["id_setor", "setor_id", "id_ticket_setor", "departamento_id"]),
        ("su_oss", ["id_setor", "setor_id", "id_ticket_setor", "departamento_id"]),
    ]

    melhor_mapa = {}

    for tabela, qtypes in candidatos:
        for qtype in qtypes:
            log_etapa(inicio, f"Buscando O.S. em lote pela tabela '{tabela}' e qtype '{qtype}'...")
            registros = consultar_todos_registros(tabela, {
                "qtype": qtype,
                "query": str(setor_alvo_id),
                "oper": "=",
                "rp": "1000",
                "sortname": "id",
                "sortorder": "desc",
            })
            if not registros:
                log_etapa(inicio, f"Nenhum registro encontrado em '{tabela}' com qtype '{qtype}'.")
                continue

            agrupado_por_login = {}
            pendentes_por_ticket = defaultdict(list)

            for registro in registros:
                if alterado_desde:
                    data_registro = (
                        parse_data_ixc(registro.get('data_ultima_alteracao'))
                        or parse_data_ixc(registro.get('ultima_atualizacao'))
                        or parse_data_ixc(registro.get('data_abertura'))
                        or parse_data_ixc(registro.get('data_criacao'))
                    )
                    if not data_registro or data_registro < alterado_desde:
                        continue

                ids = extrair_ids_vinculo_os(registro)
                setor_id, setor_nome = extrair_setor_registro(registro, mapa_setores)
                snapshot = {
                    "ticket_os_atual_ixc": ids["os_id"] or ids["ticket_id"],
                    "setor_os_atual_id_ixc": setor_id,
                    "setor_os_atual_nome": setor_nome,
                    "status_os_atual_nome": extrair_status_registro(registro) or None,
                    "os_atual_aberta": status_indica_os_ativa(registro),
                    "em_os_comercial_lastmile": (
                        normalizar_texto(setor_nome).lower() == ALVO_SETOR_NOME
                    ),
                }

                if ids["login_id"]:
                    agrupado_por_login[ids["login_id"]] = snapshot
                elif ids["ticket_id"]:
                    pendentes_por_ticket[ids["ticket_id"]].append(snapshot)

            if pendentes_por_ticket:
                for ticket_id, snapshots in pendentes_por_ticket.items():
                    resposta_ticket = consultar_ixc("su_ticket", {
                        "qtype": "id",
                        "query": str(ticket_id),
                        "oper": "=",
                        "page": "1",
                        "rp": "1",
                        "sortname": "id",
                        "sortorder": "desc",
                    })
                    registros_ticket = resposta_ticket.get('registros', []) if resposta_ticket else []
                    login_id = normalizar_texto(registros_ticket[0].get("id_login")) if registros_ticket else ''
                    if not login_id:
                        continue
                    agrupado_por_login[login_id] = snapshots[0]

            if len(agrupado_por_login) > len(melhor_mapa):
                melhor_mapa = agrupado_por_login
                log_etapa(
                    inicio,
                    f"Melhor retorno ate agora: {len(melhor_mapa)} login(s) mapeado(s) via '{tabela}'/'{qtype}'."
                )

    log_etapa(inicio, f"Busca em lote finalizada com {len(melhor_mapa)} login(s) encontrados.")
    return melhor_mapa


def buscar_os_lastmile_por_cliente(cliente_ixc_id, mapa_setores, alterado_desde=None, logins_permitidos=None):
    inicio = time.perf_counter()
    log_etapa(inicio, f"Iniciando busca por cliente IXC {cliente_ixc_id}...")
    if not cliente_ixc_id:
        return {}

    resposta_tickets = consultar_todos_registros("su_ticket", {
        "qtype": "id_cliente",
        "query": str(cliente_ixc_id),
        "oper": "=",
        "rp": "1000",
        "sortname": "id",
        "sortorder": "desc",
    })
    log_etapa(inicio, f"Foram carregados {len(resposta_tickets)} ticket(s) do cliente {cliente_ixc_id}.")

    snapshots = {}
    total_tickets = len(resposta_tickets)
    pbar_tickets = tqdm(total=total_tickets, desc="Resolvendo tickets do cliente", unit="ticket")

    for ticket in resposta_tickets:
        login_id = normalizar_texto(ticket.get("id_login"))
        if not login_id:
            pbar_tickets.update(1)
            continue
        if logins_permitidos and login_id not in logins_permitidos:
            pbar_tickets.update(1)
            continue

        ticket_id = normalizar_texto(ticket.get("id"))
        if not ticket_id:
            pbar_tickets.update(1)
            continue

        os_atual = buscar_os_atual_por_ticket(ticket_id)
        if not os_atual:
            pbar_tickets.update(1)
            continue
        if alterado_desde:
            data_registro = (
                parse_data_ixc(os_atual.get('data_ultima_alteracao'))
                or parse_data_ixc(os_atual.get('ultima_atualizacao'))
                or parse_data_ixc(os_atual.get('data_abertura'))
                or parse_data_ixc(os_atual.get('data_criacao'))
            )
            if not data_registro or data_registro < alterado_desde:
                pbar_tickets.update(1)
                continue

        setor_id, setor_nome = extrair_setor_registro(os_atual, mapa_setores)
        if normalizar_texto(setor_nome).lower() != ALVO_SETOR_NOME:
            pbar_tickets.update(1)
            continue

        os_aberta = status_indica_os_ativa(os_atual)
        snapshots[login_id] = {
            "ticket_os_atual_ixc": normalizar_texto(os_atual.get('id')) or ticket_id,
            "setor_os_atual_id_ixc": setor_id,
            "setor_os_atual_nome": setor_nome,
            "status_os_atual_nome": extrair_status_registro(os_atual) or None,
            "os_atual_aberta": os_aberta,
            "em_os_comercial_lastmile": True,
        }
        pbar_tickets.update(1)

    pbar_tickets.close()
    log_etapa(inicio, f"Busca por cliente concluida com {len(snapshots)} login(s) em Comercial | Lastmile.")
    return snapshots


def buscar_os_lastmile_por_varios_clientes(cliente_ixc_ids, mapa_setores, alterado_desde=None, logins_por_cliente=None):
    inicio = time.perf_counter()
    clientes_validos = [normalizar_texto(cliente_id) for cliente_id in cliente_ixc_ids if normalizar_texto(cliente_id)]
    log_etapa(inicio, f"Iniciando busca otimizada por {len(clientes_validos)} cliente(s) IXC...")

    snapshots = {}
    pbar_clientes = tqdm(total=len(clientes_validos), desc="Consultando clientes IXC", unit="cliente")

    for cliente_ixc_id in clientes_validos:
        logins_permitidos = None
        if logins_por_cliente:
            logins_permitidos = logins_por_cliente.get(cliente_ixc_id) or None

        snapshots_cliente = buscar_os_lastmile_por_cliente(
            cliente_ixc_id,
            mapa_setores,
            alterado_desde=alterado_desde,
            logins_permitidos=logins_permitidos,
        )
        snapshots.update(snapshots_cliente)
        pbar_clientes.update(1)

    pbar_clientes.close()
    log_etapa(inicio, f"Busca otimizada finalizada com {len(snapshots)} login(s) mapeado(s).")
    return snapshots


def extrair_setor_registro(registro, mapa_setores):
    if not registro:
        return None, None

    setor_id = (
        normalizar_texto(registro.get('id_setor'))
        or normalizar_texto(registro.get('id_ticket_setor'))
        or normalizar_texto(registro.get('ticket_setor_id'))
        or normalizar_texto(registro.get('setor_id'))
        or normalizar_texto(registro.get('departamento_id'))
    )
    setor_nome = (
        normalizar_texto(registro.get('setor'))
        or normalizar_texto(registro.get('ticket_setor'))
        or normalizar_texto(registro.get('departamento'))
        or normalizar_texto(registro.get('nome_setor'))
        or normalizar_texto(registro.get('setor_nome'))
    )
    # Alguns endpoints do IXC devolvem o "setor" textual como o proprio ID
    # (ex.: "49", "52"). Nesses casos, convertemos para o nome real pelo mapa.
    if setor_nome.isdigit() and not setor_id:
        setor_id = setor_nome
        setor_nome = ''
    if not setor_nome and setor_id:
        setor_nome = mapa_setores.get(setor_id, '')
    return setor_id or None, setor_nome or None


def sincronizar_os_comercial_lastmile(historico):
    inicio = time.perf_counter()
    log_etapa(inicio, "Iniciando sincronizacao rapida de OS Comercial | Lastmile...")
    alterado_desde = obter_data_corte_args()
    cliente_local_id, cliente_ixc_id_arg = obter_filtro_cliente_args()
    mapa_setores = buscar_mapa_setores()

    queryset_base = (
        Endereco.objects
        .exclude(login_id_ixc__isnull=True)
        .exclude(login_id_ixc='')
        .order_by('id')
    )

    if cliente_local_id:
        queryset_base = queryset_base.filter(cliente_id=cliente_local_id)
        log_etapa(inicio, f"Filtro aplicado: cliente local id={cliente_local_id}.")

    if cliente_ixc_id_arg:
        queryset_base = queryset_base.filter(cliente__id_ixc=cliente_ixc_id_arg)
        log_etapa(inicio, f"Filtro aplicado: cliente IXC id={cliente_ixc_id_arg}.")

    diagnostico_status = list(
        queryset_base.values('status').annotate(total=Count('id')).order_by('status')
    )
    if diagnostico_status:
        resumo_status = ", ".join(
            f"{item['status'] or 'vazio'}={item['total']}" for item in diagnostico_status
        )
        log_etapa(inicio, f"Diagnostico de enderecos com login por status: {resumo_status}.")
    else:
        log_etapa(inicio, "Diagnostico de enderecos com login por status: nenhum endereco com login_id_ixc no escopo.")

    queryset = queryset_base.filter(status='ativo')
    total = queryset.count()
    log_etapa(inicio, f"Total de enderecos ativos elegiveis: {total}.")

    if total == 0:
        queryset = queryset_base.exclude(status='cancelado')
        total = queryset.count()
        log_etapa(
            inicio,
            "Nenhum endereco com status ativo foi encontrado. "
            f"Usando fallback por status e considerando {total} endereco(s) nao cancelado(s)."
        )

    logins_por_cliente = defaultdict(set)
    for cliente_id_ixc, login_id_ixc in queryset.values_list('cliente__id_ixc', 'login_id_ixc'):
        cliente_id_ixc = normalizar_texto(cliente_id_ixc)
        login_id_ixc = normalizar_texto(login_id_ixc)
        if cliente_id_ixc and login_id_ixc:
            logins_por_cliente[cliente_id_ixc].add(login_id_ixc)

    if cliente_ixc_id_arg:
        snapshots_lastmile = buscar_os_lastmile_por_cliente(
            cliente_ixc_id_arg,
            mapa_setores,
            alterado_desde=alterado_desde,
            logins_permitidos=logins_por_cliente.get(cliente_ixc_id_arg),
        )
    else:
        cliente_ixc_ids = list(logins_por_cliente.keys())
        if cliente_ixc_ids:
            snapshots_lastmile = buscar_os_lastmile_por_varios_clientes(
                cliente_ixc_ids,
                mapa_setores,
                alterado_desde=alterado_desde,
                logins_por_cliente=logins_por_cliente,
            )
        else:
            snapshots_lastmile = {}

    log_etapa(inicio, f"Snapshots recebidos do IXC: {len(snapshots_lastmile)} login(s).")

    # Caminho otimizado por cliente: limpa o estado do escopo e reaplica apenas
    # os logins que realmente vierem do IXC.
    log_etapa(inicio, "Limpando estado atual de O.S. dos enderecos filtrados...")
    queryset.update(
        ticket_os_atual_ixc=None,
        setor_os_atual_id_ixc=None,
        setor_os_atual_nome=None,
        status_os_atual_nome=None,
        os_atual_aberta=False,
        em_os_comercial_lastmile=False,
    )

    if cliente_ixc_id_arg or logins_por_cliente:
        logins_alvo = list(snapshots_lastmile.keys())
        queryset_alvo = queryset.filter(login_id_ixc__in=logins_alvo).order_by('id') if logins_alvo else queryset.none()
        log_etapa(inicio, f"Atualizando {queryset_alvo.count()} endereco(s) encontrados no IXC para este escopo.")
        pbar = tqdm(total=queryset_alvo.count(), desc="Marcando OS Comercial Lastmile", unit="end")

        for endereco in queryset_alvo.iterator():
            historico.refresh_from_db()
            if historico.detalhes == "STOP":
                raise KeyboardInterrupt("Parada solicitada via Admin")

            snapshot = snapshots_lastmile.get(str(endereco.login_id_ixc))
            if not snapshot:
                pbar.update(1)
                continue

            update_fields = []
            for campo, valor in snapshot.items():
                if getattr(endereco, campo) != valor:
                    setattr(endereco, campo, valor)
                    update_fields.append(campo)

            if update_fields:
                endereco.save(update_fields=update_fields)

            pbar.update(1)

        pbar.close()
        log_etapa(inicio, "Sincronizacao concluida pelo caminho otimizado por cliente.")
        return total

    log_etapa(inicio, "Nenhum cliente IXC valido encontrado. Caindo para o caminho de fallback por endereco.")
    pbar = tqdm(total=total, desc="Marcando OS Comercial Lastmile", unit="end")

    for endereco in queryset.iterator():
        historico.refresh_from_db()
        if historico.detalhes == "STOP":
            raise KeyboardInterrupt("Parada solicitada via Admin")

        ticket_atual = buscar_ticket_atual_por_login(endereco)
        ticket_id = normalizar_texto(ticket_atual.get('id')) if ticket_atual else ''
        os_atual = buscar_os_atual_por_ticket(ticket_id)

        # Prioriza o setor da O.S. ativa ligada ao atendimento.
        # Se nao encontrar O.S. via API, usa o setor do proprio ticket como fallback.
        setor_id, setor_nome = extrair_setor_registro(os_atual, mapa_setores)
        if not setor_id and not setor_nome:
            setor_id, setor_nome = extrair_setor_registro(ticket_atual, mapa_setores)

        novo_setor_id = setor_id or None
        novo_setor_nome = setor_nome or None
        novo_ticket_id = (
            normalizar_texto(os_atual.get('id')) if os_atual else ''
        ) or (
            normalizar_texto(ticket_atual.get('id')) if ticket_atual else ''
        ) or None
        novo_status_os = (
            extrair_status_registro(os_atual)
            or extrair_status_registro(ticket_atual)
            or None
        )
        nova_os_aberta = status_indica_os_ativa(os_atual or ticket_atual)
        eh_lastmile = (
            normalizar_texto(novo_setor_nome).lower() == ALVO_SETOR_NOME
        )

        update_fields = []
        if endereco.em_os_comercial_lastmile != eh_lastmile:
            endereco.em_os_comercial_lastmile = eh_lastmile
            update_fields.append('em_os_comercial_lastmile')

        if endereco.setor_os_atual_id_ixc != novo_setor_id:
            endereco.setor_os_atual_id_ixc = novo_setor_id
            update_fields.append('setor_os_atual_id_ixc')

        if endereco.setor_os_atual_nome != novo_setor_nome:
            endereco.setor_os_atual_nome = novo_setor_nome
            update_fields.append('setor_os_atual_nome')

        if endereco.ticket_os_atual_ixc != novo_ticket_id:
            endereco.ticket_os_atual_ixc = novo_ticket_id
            update_fields.append('ticket_os_atual_ixc')

        if endereco.status_os_atual_nome != novo_status_os:
            endereco.status_os_atual_nome = novo_status_os
            update_fields.append('status_os_atual_nome')

        if endereco.os_atual_aberta != nova_os_aberta:
            endereco.os_atual_aberta = nova_os_aberta
            update_fields.append('os_atual_aberta')

        if update_fields:
            # Nessa rotina rapida, mantemos apenas a fotografia atual do setor do login.
            # O historico/ticket detalhado continua sendo responsabilidade da rotina completa.
            endereco.save(update_fields=update_fields)

        pbar.update(1)

    pbar.close()
    log_etapa(inicio, "Sincronizacao concluida pelo caminho de fallback.")
    return total


if __name__ == "__main__":
    eh_manual = 'manual' in sys.argv
    origem_detectada = 'manual' if eh_manual else 'automatica'
    data_corte_args = obter_data_corte_args()
    cliente_local_id, cliente_ixc_id = obter_filtro_cliente_args()

    usuario_executor = None
    if eh_manual:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        usuario_executor = User.objects.filter(is_superuser=True).first()

    historico = HistoricoSincronizacao.objects.create(
        tipo='os_comercial_lastmile',
        status='rodando',
        origem=origem_detectada,
        executado_por=usuario_executor,
        detalhes=(
            'Marcacao rapida dos logins ativos com OS atual em Comercial | Lastmile.'
            + (
                f" Filtro opcional de ultima alteracao aplicado a partir de {data_corte_args.date().isoformat()}."
                if data_corte_args else ''
            )
            + (
                f" Cliente local filtrado: {cliente_local_id}."
                if cliente_local_id else ''
            )
            + (
                f" Cliente IXC filtrado: {cliente_ixc_id}."
                if cliente_ixc_id else ''
            )
        ),
    )

    try:
        total_processado = sincronizar_os_comercial_lastmile(historico)
        historico.status = 'sucesso'
        historico.registros_processados = total_processado
        historico.detalhes = 'Marcacao de OS atual Comercial | Lastmile concluida com sucesso.'
    except KeyboardInterrupt as exc:
        historico.status = 'erro'
        historico.detalhes = str(exc)
        print(str(exc))
    except Exception:
        historico.status = 'erro'
        historico.detalhes = traceback.format_exc()
        print("Erro fatal ao marcar OS Comercial | Lastmile.")
    finally:
        historico.data_fim = timezone.now()
        historico.save()
