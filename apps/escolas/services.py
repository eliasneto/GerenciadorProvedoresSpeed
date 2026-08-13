import re
from decimal import Decimal, InvalidOperation

from apps.escolas.models import Escola
from apps.integracoes.dashboard_eace.services.escolas import listar_escolas


_REGEX_CEP = re.compile(r"(\d{5}-\d{3})")
_REGEX_NUMERO = re.compile(r"^(\d+|S/N)\b", re.IGNORECASE)
_TIPOS_LOGRADOURO = {
    "RUA", "AVENIDA", "AV", "TRAVESSA", "ALAMEDA", "AL", "ESTRADA", "RODOVIA",
    "ROD", "PRACA", "PRAÇA", "LARGO", "VIA", "VIELA",
}


def extrair_endereco_estruturado(endereco_descricao):
    """RN-051: extrai `{logradouro, numero, bairro, cep}` do texto livre de
    `Escola.endereco_descricao` (DashboardEACE), por melhor esforco — o
    texto de origem nao segue um formato fixo (confirmado investigando
    registros reais: ha casos sem numero, sem tipo de logradouro, sem
    bairro, e ate sem CEP). O CEP e confiavel (padrao fixo `00000-000`).
    Logradouro/Numero/Bairro ficam em branco quando a heuristica nao tiver
    confianca suficiente — nunca um valor claramente errado. Nao altera
    `endereco_descricao`, que continua intacto como fonte bruta."""
    resultado = {"logradouro": "", "numero": "", "bairro": "", "cep": ""}
    if not endereco_descricao:
        return resultado

    # a 1a linha e o endereco; as demais (Municipio/Codigo INEP/UF) sao
    # redundantes com campos que a Escola ja tem separados.
    primeira_linha = endereco_descricao.split("\n", 1)[0]
    texto = re.sub(r"^Endere[cç]o:\s*", "", primeira_linha, flags=re.IGNORECASE).strip()

    match_cep = _REGEX_CEP.search(texto)
    if match_cep:
        resultado["cep"] = match_cep.group(1)
        texto_antes_do_cep = texto[: match_cep.start()]
    else:
        texto_antes_do_cep = texto

    logradouro, _virgula, resto = texto_antes_do_cep.partition(",")
    resultado["logradouro"] = logradouro.strip(" .")

    # sem CEP, nao ha fronteira confiavel entre "detalhes do endereco" e
    # "cidade - UF" no restante do texto — nao arrisca numero/bairro.
    if not match_cep or not resto.strip():
        return resultado

    segmentos = [segmento.strip() for segmento in resto.split(".") if segmento.strip()]
    if not segmentos:
        return resultado

    match_numero = _REGEX_NUMERO.match(segmentos[0])
    if match_numero:
        resultado["numero"] = match_numero.group(1)
        resto_primeiro = segmentos[0][match_numero.end():].strip()
        if resto_primeiro.upper() in _TIPOS_LOGRADOURO:
            resto_primeiro = ""
        if resto_primeiro:
            resultado["bairro"] = resto_primeiro
        elif len(segmentos) >= 2:
            resultado["bairro"] = segmentos[1]
    else:
        # sem numero identificavel: o segmento mais proximo do CEP e o
        # melhor palpite de bairro (posicao, nao o texto em si).
        resultado["bairro"] = segmentos[-1]

    return resultado


def _para_decimal(valor):
    """RN-057: converte um valor bruto vindo da API (int/float/str) para
    Decimal, sem inventar dado — devolve None quando ausente ou nao
    numerico, em vez de falhar silenciosamente ou gravar um valor errado."""
    if valor in (None, ""):
        return None
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return None


def sincronizar_escolas(uf=None, status_escola=None, client=None):
    """Busca escolas no DashboardEACE e grava/atualiza uma linha por
    `jira_key` em `Escola`, guardando o item inteiro em `dados_api`
    (ADR-010 — sem mapear para `apps.clientes.Cliente`/`Endereco`).
    RN-051: tambem preenche Logradouro/Numero/Bairro/CEP, extraidos do
    texto de `descricao` (melhor esforco). RN-057: tambem preenche
    Velocidade Minima e Kit Inicial (colunas tipadas, promovidas de
    dados_api).

    Retorna (total_sincronizadas, erro). Em caso de erro na chamada da API,
    total_sincronizadas e 0 e erro descreve o problema; nenhuma linha e
    tocada.
    """
    status_code, body = listar_escolas(uf=uf, status_escola=status_escola, client=client)

    if status_code != 200:
        detalhe = body.get("detail") if isinstance(body, dict) else body
        return 0, f"Falha ao consultar o DashboardEACE (status {status_code}): {detalhe}"

    itens = body if isinstance(body, list) else body.get("escolas") or body.get("items") or []
    if not isinstance(itens, list):
        return 0, "Formato de resposta inesperado do DashboardEACE (esperava uma lista de escolas)."

    total = 0
    for item in itens:
        # O campo que identifica a escola na resposta da API se chama "key"
        # (confirmado em 2026-08-07 contra a API real), nao "jira_key" —
        # esse ultimo e so o nome do parametro na rota (/escolas/{jira_key}).
        jira_key = item.get("key")
        if not jira_key:
            continue

        endereco_descricao = item.get("descricao") or ""
        endereco_estruturado = extrair_endereco_estruturado(endereco_descricao)

        Escola.objects.update_or_create(
            jira_key=jira_key,
            defaults={
                "uf": item.get("uf") or "",
                "status_escola": item.get("status_escola") or "",
                "inep": item.get("inep") or "",
                "nome": item.get("nome") or "",
                "municipio": item.get("municipio") or "",
                "endereco_descricao": endereco_descricao,
                **endereco_estruturado,
                # RN-057 Partes 1 e 2: promovidos de dados_api para colunas
                # tipadas (chaves iguais ao nome de coluna confirmado na
                # origem legada — mesmo padrao ja usado por inep/nome/
                # municipio/endereco_descricao, ADR-010).
                "velocidade_dl_minima": _para_decimal(item.get("velocidade_dl_minima")),
                "kit_inicial": _para_decimal(item.get("kit_wifi")),
                "dados_api": item,
            },
        )
        total += 1

    return total, None
