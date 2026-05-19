import os
import sys
import json
import base64
import re
import traceback
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta

import requests
import urllib3
from tqdm import tqdm


# Rotina enxuta para separar rapidamente os logins ativos cujo ticket/OS atual
# pertence ao setor "Comercial | Lastmile".
# Ela existe em paralelo a ixc_primeira_os.py, que continua sendo a rotina
# mais completa de enriquecimento operacional.
#
# Regra importante:
# - a reconciliacao diaria padrao e completa, sem janela de dias
# - recorte por data so deve ser usado em execucoes incrementais explicitas
# - O.S. sem login atrelado continuam fora do escopo desta rotina

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

from clientes.models import Cliente, Endereco, HistoricoSincronizacao
from clientes.sync_utils import descrever_rotina_em_execucao, iniciar_historico_com_trava


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
EXECUTION_LOGGER = None


class ExecutionLogger:
    def __init__(self, historico, tipo):
        self.historico = historico
        self.tipo = tipo
        self.stop_requested = False
        self.max_chars = 14000
        self.flush_interval = 2.0
        self.last_flush_monotonic = 0.0
        self.lines = []

        timestamp = formatar_datetime_local(timezone.now(), "%Y%m%d_%H%M%S")
        nome_arquivo = f"{timestamp}_historico_{historico.id}.log"
        self.relative_path = f"media/integration_logs/{tipo}/{nome_arquivo}"
        self.absolute_path = os.path.join(
            BASE_DIR,
            "media",
            "integration_logs",
            tipo,
            nome_arquivo,
        )
        os.makedirs(os.path.dirname(self.absolute_path), exist_ok=True)

    def append(self, mensagem, force_flush=False):
        self.lines.append(mensagem)
        self._trim_lines()
        with open(self.absolute_path, "a", encoding="utf-8") as arquivo_log:
            arquivo_log.write(mensagem + "\n")
        self.sync_to_historico(force=force_flush)

    def _trim_lines(self):
        while self.lines and len("\n".join(self.lines)) > self.max_chars:
            self.lines.pop(0)

    def build_details(self, cabecalho):
        atualizado_em = formatar_datetime_local(timezone.now(), "%d/%m/%Y %H:%M:%S")
        partes = [
            cabecalho,
            f"Arquivo de log: {self.relative_path}",
            f"Atualizado em: {atualizado_em}",
        ]
        if self.lines:
            partes.extend([
                "",
                "Ultimas mensagens:",
                *self.lines,
            ])
        return "\n".join(partes)

    def sync_to_historico(self, force=False, cabecalho="Execucao em andamento."):
        if not force and (time.monotonic() - self.last_flush_monotonic) < self.flush_interval:
            return

        detalhes_atuais = (
            type(self.historico).objects
            .filter(pk=self.historico.pk)
            .values_list("detalhes", flat=True)
            .first()
        )
        if detalhes_atuais == "STOP":
            self.stop_requested = True
            return

        self.historico.detalhes = self.build_details(cabecalho)
        self.historico.save(update_fields=["detalhes"])
        self.last_flush_monotonic = time.monotonic()

    def finalize(self, cabecalho):
        self.sync_to_historico(force=True, cabecalho=cabecalho)


def log_etapa(inicio, mensagem):
    decorrido = time.perf_counter() - inicio
    mensagem_formatada = f"[{decorrido:8.1f}s] {mensagem}"
    print(mensagem_formatada, flush=True)
    if EXECUTION_LOGGER:
        EXECUTION_LOGGER.append(mensagem_formatada)


def formatar_datetime_local(valor, formato):
    if timezone.is_naive(valor):
        return valor.strftime(formato)
    return timezone.localtime(valor).strftime(formato)


def progresso_visual_habilitado():
    valor = os.getenv("LASTMILE_TQDM", "").strip().lower()
    if valor in {"1", "true", "sim", "yes", "on"}:
        return True
    if valor in {"0", "false", "nao", "não", "no", "off"}:
        return False
    return bool(getattr(sys.stdout, "isatty", lambda: False)())


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


def normalizar_texto_busca(valor):
    texto = normalizar_texto(valor)
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^A-Z0-9]+", " ", texto.upper())
    return re.sub(r"\s+", " ", texto).strip()


def extrair_cep_texto(valor):
    texto = normalizar_texto(valor)
    if not texto:
        return ""
    match = re.search(r"\b(\d{5})-?(\d{3})\b", texto)
    if not match:
        return ""
    return f"{match.group(1)}-{match.group(2)}"


def extrair_endereco_referencia_registro(registro):
    if not registro:
        return ""

    campos_textuais = [
        normalizar_texto(registro.get("menssagem")),
        normalizar_texto(registro.get("mensagem")),
        normalizar_texto(registro.get("endereco")),
    ]

    padrao_local = re.compile(
        r"local\s*:\s*(.+?)(?=\s*\*\s*[A-Z0-9_ /-]+\s*:|$)",
        re.IGNORECASE | re.DOTALL,
    )
    for campo in campos_textuais:
        if not campo:
            continue
        match = padrao_local.search(campo)
        if match:
            return normalizar_texto(match.group(1))

    for campo in campos_textuais:
        if campo:
            return campo
    return ""


def construir_indice_enderecos_cliente(cliente_ixc_id, logins_permitidos=None):
    queryset = (
        Endereco.objects
        .filter(cliente__id_ixc=cliente_ixc_id)
        .exclude(login_id_ixc__isnull=True)
        .exclude(login_id_ixc="")
        .values("id", "login_id_ixc", "logradouro", "cep", "cidade", "estado", "numero", "bairro")
    )
    if logins_permitidos:
        queryset = queryset.filter(login_id_ixc__in=list(logins_permitidos))

    indice_por_texto = {}
    indice_por_cep = defaultdict(list)
    enderecos = []

    for endereco in queryset:
        login_id = normalizar_texto(endereco.get("login_id_ixc"))
        if not login_id:
            continue
        endereco_info = {
            "id": endereco.get("id"),
            "login_id": login_id,
            "logradouro": normalizar_texto(endereco.get("logradouro")),
            "logradouro_norm": normalizar_texto_busca(endereco.get("logradouro")),
            "cep": extrair_cep_texto(endereco.get("cep")),
            "cidade_norm": normalizar_texto_busca(endereco.get("cidade")),
            "estado_norm": normalizar_texto_busca(endereco.get("estado")),
            "numero_norm": normalizar_texto_busca(endereco.get("numero")),
            "bairro_norm": normalizar_texto_busca(endereco.get("bairro")),
        }
        enderecos.append(endereco_info)
        if endereco_info["logradouro_norm"]:
            indice_por_texto.setdefault(endereco_info["logradouro_norm"], []).append(endereco_info)
        if endereco_info["cep"]:
            indice_por_cep[endereco_info["cep"]].append(endereco_info)

    return {
        "enderecos": enderecos,
        "por_texto": indice_por_texto,
        "por_cep": indice_por_cep,
    }


def resolver_login_local_por_endereco(ticket, os_atual, indice_enderecos):
    if not indice_enderecos:
        return None, None

    referencias = [
        ("ticket", extrair_endereco_referencia_registro(ticket)),
        ("os", extrair_endereco_referencia_registro(os_atual)),
    ]

    for origem, referencia in referencias:
        referencia_norm = normalizar_texto_busca(referencia)
        if not referencia_norm:
            continue

        candidatos_texto = indice_enderecos["por_texto"].get(referencia_norm, [])
        if len(candidatos_texto) == 1:
            return candidatos_texto[0]["login_id"], f"{origem}:texto_exato"
        if len(candidatos_texto) > 1:
            return None, f"{origem}:texto_duplicado"

        cep = extrair_cep_texto(referencia)
        if not cep:
            continue

        candidatos_cep = indice_enderecos["por_cep"].get(cep, [])
        if len(candidatos_cep) == 1:
            return candidatos_cep[0]["login_id"], f"{origem}:cep_unico"

        if len(candidatos_cep) > 1:
            candidatos_filtrados = []
            for candidato in candidatos_cep:
                numero_ok = not candidato["numero_norm"] or candidato["numero_norm"] in referencia_norm
                cidade_ok = not candidato["cidade_norm"] or candidato["cidade_norm"] in referencia_norm
                bairro_ok = not candidato["bairro_norm"] or candidato["bairro_norm"] in referencia_norm
                if numero_ok and cidade_ok and bairro_ok:
                    candidatos_filtrados.append(candidato)
            if len(candidatos_filtrados) == 1:
                return candidatos_filtrados[0]["login_id"], f"{origem}:cep_refinado"

    return None, None


def construir_snapshot_os(registro, ticket_id, setor_id, setor_nome):
    return {
        "ticket_os_atual_ixc": normalizar_texto(registro.get('id')) or ticket_id,
        "setor_os_atual_id_ixc": setor_id,
        "setor_os_atual_nome": setor_nome,
        "status_os_atual_nome": extrair_status_registro(registro) or None,
        "os_atual_aberta": status_indica_os_ativa(registro),
        "em_os_comercial_lastmile": True,
    }


def buscar_os_lastmile_por_cliente_direto(cliente_ixc_id, mapa_setores, alterado_desde=None, logins_permitidos=None, cliente_idx=None, total_clientes=None):
    inicio = time.perf_counter()
    prefixo_cliente = f"[cliente {cliente_idx}/{total_clientes}] " if cliente_idx and total_clientes else ""
    resposta_os = consultar_todos_registros("su_oss_chamado", {
        "qtype": "id_cliente",
        "query": str(cliente_ixc_id),
        "oper": "=",
        "rp": "1000",
        "sortname": "id",
        "sortorder": "desc",
    })
    if not resposta_os:
        log_etapa(inicio, f"{prefixo_cliente}Busca direta por O.S. nao retornou registros para o cliente IXC {cliente_ixc_id}.")
        return None

    log_etapa(inicio, f"{prefixo_cliente}Busca direta carregou {len(resposta_os)} O.S. do cliente {cliente_ixc_id}.")
    snapshots = {}
    logins_processados = set()
    metricas = {
        "os_sem_login": 0,
        "os_fora_escopo_local": 0,
        "os_endereco_resolvido": 0,
        "os_endereco_nao_resolvido": 0,
        "os_login_repetido": 0,
        "os_fora_data": 0,
        "os_setor_diferente": 0,
    }

    for os_atual in resposta_os:
        if alterado_desde:
            data_registro = extrair_data_referencia_registro(os_atual)
            if data_registro and data_registro < alterado_desde:
                metricas["os_fora_data"] += 1
                continue

        setor_id, setor_nome = extrair_setor_registro(os_atual, mapa_setores)
        if normalizar_texto(setor_nome).lower() != ALVO_SETOR_NOME:
            metricas["os_setor_diferente"] += 1
            continue

        login_id = normalizar_texto(os_atual.get("id_login"))
        if login_id == "0":
            login_id = ""

        login_em_escopo = bool(login_id and (not logins_permitidos or login_id in logins_permitidos))
        if not login_em_escopo:
            if login_id:
                metricas["os_fora_escopo_local"] += 1
            else:
                metricas["os_sem_login"] += 1
            metricas["os_endereco_nao_resolvido"] += 1
            continue

        if login_id in logins_processados:
            metricas["os_login_repetido"] += 1
            continue

        ticket_id = (
            normalizar_texto(os_atual.get("id_ticket"))
            or normalizar_texto(os_atual.get("id_atendimento"))
            or None
        )
        snapshots[login_id] = construir_snapshot_os(os_atual, ticket_id, setor_id, setor_nome)
        logins_processados.add(login_id)

    log_etapa(
        inicio,
        (
            f"{prefixo_cliente}Busca direta do cliente IXC {cliente_ixc_id} concluida | "
            f"os_total={len(resposta_os)} | logins_lastmile={len(snapshots)} | "
            f"sem_login={metricas['os_sem_login']} | "
            f"fora_escopo_local={metricas['os_fora_escopo_local']} | "
            f"endereco_resolvido={metricas['os_endereco_resolvido']} | "
            f"endereco_nao_resolvido={metricas['os_endereco_nao_resolvido']} | "
            f"login_repetido={metricas['os_login_repetido']} | "
            f"fora_data={metricas['os_fora_data']} | "
            f"setor_diferente={metricas['os_setor_diferente']}"
        ),
    )
    return snapshots


def obter_data_corte_env():
    valor = normalizar_texto(os.getenv("OS_LASTMILE_LOOKBACK_DAYS"))
    if not valor:
        return None
    try:
        dias = int(valor)
    except ValueError:
        print(
            f"Valor invalido em OS_LASTMILE_LOOKBACK_DAYS={valor!r}. Use um inteiro, por exemplo 10."
        )
        raise SystemExit(1)
    if dias < 0:
        print("Valor invalido em OS_LASTMILE_LOOKBACK_DAYS. A quantidade de dias nao pode ser negativa.")
        raise SystemExit(1)
    return datetime.now() - timedelta(days=dias)


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


def obter_data_corte_incremental_padrao():
    return obter_data_corte_env()


def execucao_incremental_explicita():
    argumentos = sys.argv[1:]
    if any(
        arg.startswith(prefixo)
        for arg in argumentos
        for prefixo in (
            "--os-alterada-desde=",
            "--alterado-desde=",
            "--os-alterada-nos-ultimos-dias=",
            "--alterado-nos-ultimos-dias=",
        )
    ):
        return True
    return any(arg in {"--incremental", "incremental"} for arg in argumentos)


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


def resolver_filtros_cliente(cliente_local_id, cliente_ixc_id):
    cliente_local_id = normalizar_texto(cliente_local_id) or None
    cliente_ixc_id = normalizar_texto(cliente_ixc_id) or None
    avisos = []

    cliente_local = None
    if cliente_local_id:
        cliente_local = Cliente.objects.filter(pk=cliente_local_id).only("id", "id_ixc").first()
        if cliente_local:
            id_ixc_cliente_local = normalizar_texto(cliente_local.id_ixc)
            if id_ixc_cliente_local and not cliente_ixc_id:
                cliente_ixc_id = id_ixc_cliente_local
        elif not cliente_ixc_id:
            cliente_por_ixc = Cliente.objects.filter(id_ixc=cliente_local_id).only("id", "id_ixc").first()
            if cliente_por_ixc:
                cliente_ixc_id = normalizar_texto(cliente_por_ixc.id_ixc) or cliente_ixc_id
                cliente_local_id = str(cliente_por_ixc.id)
                avisos.append(
                    "O filtro informado em cliente_local_id nao correspondeu a um ID interno. "
                    f"O valor '{cliente_por_ixc.id_ixc}' foi interpretado automaticamente como ID IXC "
                    f"do cliente local {cliente_por_ixc.id}."
                )

    if cliente_ixc_id and not cliente_local_id:
        cliente_por_ixc = Cliente.objects.filter(id_ixc=cliente_ixc_id).only("id").first()
        if cliente_por_ixc:
            cliente_local_id = str(cliente_por_ixc.id)

    return cliente_local_id, cliente_ixc_id, avisos


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


def extrair_data_referencia_registro(registro):
    if not registro:
        return None

    campos_candidatos = [
        'data_ultima_alteracao',
        'ultima_atualizacao',
        'data_abertura',
        'data_criacao',
        'data',
        'data_cadastro',
        'data_emissao',
        'data_agendamento',
        'abertura',
    ]

    for campo in campos_candidatos:
        data_encontrada = parse_data_ixc(registro.get(campo))
        if data_encontrada:
            return data_encontrada
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

    # Em producao, o IXC costuma expor a O.S. do fluxo comercial pela
    # tabela `su_oss_chamado`, entao priorizamos esse lookup para evitar
    # dezenas de consultas negativas antes de chegar no endpoint certo.
    candidatos = [
        ("su_oss_chamado", ["id_ticket", "id_atendimento", "id_su_ticket", "id_chamado"]),
        ("su_oss", ["id_ticket", "id_atendimento", "id_su_ticket", "id_chamado"]),
        ("su_os", ["id_ticket", "id_atendimento", "id_su_ticket", "id_chamado"]),
        ("su_ordem_servico", ["id_ticket", "id_atendimento", "id_su_ticket", "id_chamado"]),
        ("ordem_servico", ["id_ticket", "id_atendimento", "id_su_ticket", "id_chamado"]),
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


def buscar_ids_setor_alvo(mapa_setores):
    ids = []
    for setor_id, setor_nome in mapa_setores.items():
        if normalizar_texto(setor_nome).lower() == ALVO_SETOR_NOME:
            ids.append(setor_id)
    return ids


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
    setor_alvo_ids = buscar_ids_setor_alvo(mapa_setores)
    if not setor_alvo_ids:
        log_etapa(inicio, "Setor alvo Comercial | Lastmile nao encontrado no mapa de setores.")
        return {}
    log_etapa(inicio, f"Setor alvo encontrado no IXC: ids={', '.join(setor_alvo_ids)}.")

    candidatos = [
        ("su_os", ["id_setor", "setor_id", "id_ticket_setor", "departamento_id"]),
        ("su_ordem_servico", ["id_setor", "setor_id", "id_ticket_setor", "departamento_id"]),
        ("ordem_servico", ["id_setor", "setor_id", "id_ticket_setor", "departamento_id"]),
        ("su_oss_chamado", ["id_setor", "setor_id", "id_ticket_setor", "departamento_id"]),
        ("su_oss", ["id_setor", "setor_id", "id_ticket_setor", "departamento_id"]),
    ]

    snapshots_consolidados = {}

    for tabela, qtypes in candidatos:
        for qtype in qtypes:
            for setor_alvo_id in setor_alvo_ids:
                log_etapa(
                    inicio,
                    f"Buscando O.S. em lote pela tabela '{tabela}', qtype '{qtype}' e setor '{setor_alvo_id}'..."
                )
                registros = consultar_todos_registros(tabela, {
                    "qtype": qtype,
                    "query": str(setor_alvo_id),
                    "oper": "=",
                    "rp": "1000",
                    "sortname": "id",
                    "sortorder": "desc",
                })
                if not registros:
                    log_etapa(
                        inicio,
                        f"Nenhum registro encontrado em '{tabela}' com qtype '{qtype}' para setor '{setor_alvo_id}'."
                    )
                    continue

                agrupado_por_login = {}
                pendentes_por_ticket = defaultdict(list)

                for registro in registros:
                    if alterado_desde:
                        data_registro = extrair_data_referencia_registro(registro)
                        if data_registro and data_registro < alterado_desde:
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

                novos_logins = 0
                for login_id, snapshot in agrupado_por_login.items():
                    if login_id not in snapshots_consolidados:
                        novos_logins += 1
                    snapshots_consolidados[login_id] = snapshot

                if novos_logins:
                    log_etapa(
                        inicio,
                        f"Acumulado consolidado: {len(snapshots_consolidados)} login(s) apos '{tabela}'/'{qtype}' no setor '{setor_alvo_id}'."
                    )

    log_etapa(inicio, f"Busca em lote finalizada com {len(snapshots_consolidados)} login(s) encontrados.")
    return snapshots_consolidados


def buscar_os_lastmile_por_cliente(cliente_ixc_id, mapa_setores, alterado_desde=None, logins_permitidos=None, cliente_idx=None, total_clientes=None):
    inicio = time.perf_counter()
    prefixo_cliente = f"[cliente {cliente_idx}/{total_clientes}] " if cliente_idx and total_clientes else ""
    log_etapa(inicio, f"{prefixo_cliente}Iniciando busca por cliente IXC {cliente_ixc_id}...")
    if not cliente_ixc_id:
        return {}

    snapshots_diretos = buscar_os_lastmile_por_cliente_direto(
        cliente_ixc_id,
        mapa_setores,
        alterado_desde=alterado_desde,
        logins_permitidos=logins_permitidos,
        cliente_idx=cliente_idx,
        total_clientes=total_clientes,
    )
    if snapshots_diretos is not None:
        return snapshots_diretos

    resposta_tickets = consultar_todos_registros("su_ticket", {
        "qtype": "id_cliente",
        "query": str(cliente_ixc_id),
        "oper": "=",
        "rp": "1000",
        "sortname": "id",
        "sortorder": "desc",
    })
    log_etapa(inicio, f"{prefixo_cliente}Foram carregados {len(resposta_tickets)} ticket(s) do cliente {cliente_ixc_id}.")

    snapshots = {}
    logins_processados = set()
    metricas = {
        "tickets_sem_login": 0,
        "tickets_fora_escopo_local": 0,
        "tickets_endereco_resolvido": 0,
        "tickets_endereco_nao_resolvido": 0,
        "tickets_login_repetido": 0,
        "tickets_sem_id": 0,
        "tickets_sem_os": 0,
        "tickets_fora_data": 0,
        "tickets_setor_diferente": 0,
    }
    total_tickets = len(resposta_tickets)
    pbar_tickets = tqdm(
        total=total_tickets,
        desc=f"Cliente IXC {cliente_ixc_id}",
        unit="ticket",
        disable=not progresso_visual_habilitado(),
        leave=False,
    )

    for ticket in resposta_tickets:
        login_id = normalizar_texto(ticket.get("id_login"))
        if login_id == "0":
            login_id = ""

        ticket_id = normalizar_texto(ticket.get("id"))
        if not ticket_id:
            metricas["tickets_sem_id"] += 1
            pbar_tickets.update(1)
            continue

        os_atual = buscar_os_atual_por_ticket(ticket_id)
        if not os_atual:
            metricas["tickets_sem_os"] += 1
            pbar_tickets.update(1)
            continue
        if alterado_desde:
            data_registro = extrair_data_referencia_registro(os_atual)
            if data_registro and data_registro < alterado_desde:
                metricas["tickets_fora_data"] += 1
                pbar_tickets.update(1)
                continue

        setor_id, setor_nome = extrair_setor_registro(os_atual, mapa_setores)
        if normalizar_texto(setor_nome).lower() != ALVO_SETOR_NOME:
            metricas["tickets_setor_diferente"] += 1
            pbar_tickets.update(1)
            continue

        login_em_escopo = bool(login_id and (not logins_permitidos or login_id in logins_permitidos))
        if not login_em_escopo:
            if login_id:
                metricas["tickets_fora_escopo_local"] += 1
            else:
                metricas["tickets_sem_login"] += 1
            metricas["tickets_endereco_nao_resolvido"] += 1
            pbar_tickets.update(1)
            continue

        if login_id in logins_processados:
            metricas["tickets_login_repetido"] += 1
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
        logins_processados.add(login_id)
        pbar_tickets.update(1)

    pbar_tickets.close()
    log_etapa(
        inicio,
        (
            f"{prefixo_cliente}Cliente IXC {cliente_ixc_id} concluido | "
            f"tickets={total_tickets} | logins_lastmile={len(snapshots)} | "
            f"sem_login={metricas['tickets_sem_login']} | "
            f"fora_escopo_local={metricas['tickets_fora_escopo_local']} | "
            f"endereco_resolvido={metricas['tickets_endereco_resolvido']} | "
            f"endereco_nao_resolvido={metricas['tickets_endereco_nao_resolvido']} | "
            f"login_repetido={metricas['tickets_login_repetido']} | "
            f"sem_id={metricas['tickets_sem_id']} | "
            f"sem_os={metricas['tickets_sem_os']} | "
            f"fora_data={metricas['tickets_fora_data']} | "
            f"setor_diferente={metricas['tickets_setor_diferente']}"
        ),
    )
    return snapshots


def buscar_os_lastmile_por_varios_clientes(cliente_ixc_ids, mapa_setores, alterado_desde=None, logins_por_cliente=None):
    inicio = time.perf_counter()
    clientes_validos = [normalizar_texto(cliente_id) for cliente_id in cliente_ixc_ids if normalizar_texto(cliente_id)]
    log_etapa(inicio, f"Iniciando busca otimizada por {len(clientes_validos)} cliente(s) IXC...")

    snapshots = {}
    pbar_clientes = tqdm(
        total=len(clientes_validos),
        desc="Clientes IXC",
        unit="cliente",
        disable=not progresso_visual_habilitado(),
        leave=False,
    )

    for idx, cliente_ixc_id in enumerate(clientes_validos, start=1):
        logins_permitidos = None
        if logins_por_cliente:
            logins_permitidos = logins_por_cliente.get(cliente_ixc_id) or None
        quantidade_logins_local = len(logins_permitidos or [])
        log_etapa(
            inicio,
            f"[cliente {idx}/{len(clientes_validos)}] Cliente IXC {cliente_ixc_id} | logins locais no escopo={quantidade_logins_local}",
        )

        snapshots_cliente = buscar_os_lastmile_por_cliente(
            cliente_ixc_id,
            mapa_setores,
            alterado_desde=alterado_desde,
            logins_permitidos=logins_permitidos,
            cliente_idx=idx,
            total_clientes=len(clientes_validos),
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
    cliente_local_id, cliente_ixc_id_arg, avisos_filtro = resolver_filtros_cliente(
        cliente_local_id,
        cliente_ixc_id_arg,
    )
    mapa_setores = buscar_mapa_setores()

    for aviso in avisos_filtro:
        log_etapa(inicio, aviso)

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
    if total == 0:
        detalhe = "Nenhum endereco elegivel com login_id_ixc foi encontrado para os filtros informados."
        if avisos_filtro:
            detalhe = f"{detalhe} {' '.join(avisos_filtro)}"
        log_etapa(inicio, detalhe)
        return 0, detalhe

    logins_por_cliente = defaultdict(set)
    for cliente_id_ixc, login_id_ixc in queryset.values_list('cliente__id_ixc', 'login_id_ixc'):
        cliente_id_ixc = normalizar_texto(cliente_id_ixc)
        login_id_ixc = normalizar_texto(login_id_ixc)
        if cliente_id_ixc and login_id_ixc:
            logins_por_cliente[cliente_id_ixc].add(login_id_ixc)
    log_etapa(
        inicio,
        f"Clientes IXC no escopo local com login mapeado: {len(logins_por_cliente)}."
    )

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
            if historico.detalhes == "STOP" or (EXECUTION_LOGGER and EXECUTION_LOGGER.stop_requested):
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
        detalhe = "Marcacao de OS atual Comercial | Lastmile concluida com sucesso."
        if avisos_filtro:
            detalhe = f"{detalhe} {' '.join(avisos_filtro)}"
        return total, detalhe

    log_etapa(inicio, "Nenhum cliente IXC valido encontrado. Caindo para o caminho de fallback por endereco.")
    pbar = tqdm(total=total, desc="Marcando OS Comercial Lastmile", unit="end")

    for endereco in queryset.iterator():
        historico.refresh_from_db()
        if historico.detalhes == "STOP" or (EXECUTION_LOGGER and EXECUTION_LOGGER.stop_requested):
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
    detalhe = "Marcacao de OS atual Comercial | Lastmile concluida com sucesso."
    if avisos_filtro:
        detalhe = f"{detalhe} {' '.join(avisos_filtro)}"
    return total, detalhe


if __name__ == "__main__":
    eh_manual = 'manual' in sys.argv
    origem_detectada = 'manual' if eh_manual else 'automatica'
    data_corte_args = obter_data_corte_args()
    incremental_explicito = execucao_incremental_explicita()
    if incremental_explicito and not data_corte_args:
        data_corte_args = obter_data_corte_incremental_padrao()
    cliente_local_id, cliente_ixc_id = obter_filtro_cliente_args()
    cliente_local_id, cliente_ixc_id, avisos_filtro = resolver_filtros_cliente(
        cliente_local_id,
        cliente_ixc_id,
    )

    usuario_executor = None
    if eh_manual:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        usuario_executor = User.objects.filter(is_superuser=True).first()

    historico, rotina_ativa = iniciar_historico_com_trava(
        tipo='os_comercial_lastmile',
        origem=origem_detectada,
        executado_por=usuario_executor,
        detalhes=(
            'Marcacao rapida dos logins ativos com OS atual em Comercial | Lastmile.'
            + (
                ' Modo incremental com recorte de ultima alteracao.'
                if incremental_explicito else
                ' Modo de reconciliacao completa sem recorte de ultima alteracao.'
            )
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
            + (
                f" {' '.join(avisos_filtro)}"
                if avisos_filtro else ''
            )
        ),
    )
    if rotina_ativa:
        print(descrever_rotina_em_execucao('os_comercial_lastmile', rotina_ativa))
        raise SystemExit(0)

    EXECUTION_LOGGER = ExecutionLogger(historico, "os_comercial_lastmile")
    EXECUTION_LOGGER.append(
        f"[     0.0s] Historico #{historico.id} iniciado para OS Comercial | Lastmile.",
        force_flush=True,
    )

    try:
        total_processado, detalhes_finais = sincronizar_os_comercial_lastmile(historico)
        historico.status = 'sucesso'
        historico.registros_processados = total_processado
        historico.detalhes = detalhes_finais
        if EXECUTION_LOGGER:
            EXECUTION_LOGGER.finalize(detalhes_finais)
    except KeyboardInterrupt as exc:
        historico.status = 'erro'
        historico.detalhes = str(exc)
        print(str(exc))
        if EXECUTION_LOGGER:
            EXECUTION_LOGGER.append(f"[erro] {exc}", force_flush=True)
            EXECUTION_LOGGER.finalize(f"Execucao interrompida. {exc}")
    except Exception:
        historico.status = 'erro'
        erro_detalhado = traceback.format_exc()
        historico.detalhes = erro_detalhado
        print("Erro fatal ao marcar OS Comercial | Lastmile.")
        if EXECUTION_LOGGER:
            for linha in erro_detalhado.rstrip().splitlines():
                EXECUTION_LOGGER.append(linha, force_flush=True)
            EXECUTION_LOGGER.finalize("Execucao finalizada com erro.")
    finally:
        historico.data_fim = timezone.now()
        historico.save()
