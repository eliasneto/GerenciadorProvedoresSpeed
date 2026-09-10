"""Relatorio: 1 linha por login (radusuarios) do cliente com O.S. no workflow
"Processo Cotacao Parceiro" no IXC, exportado para planilha na raiz do
projeto.

HISTORICO / POR QUE O RELATORIO E MONTADO ASSIM:

A primeira versao deste script partia do atendimento (su_ticket) filtrando
por id_assunto = 133 ("Processo Cotacao Parceiro"). Isso e preciso, mas
incompleto: o IXC remove o registro do atendimento (su_ticket) depois de um
tempo e as vezes REATRIBUI a O.S. a um atendimento seguinte de assunto
diferente (ex.: "Ativacao Rede Interna EACE", Assunto ID 141) — em ambos os
casos a O.S. continua existindo e podendo estar aberta, mas o atendimento
com assunto 133 que a originou nao e mais encontravel. Levantamento no
cliente 575: soh ~1079 atendimentos ainda existem com assunto 133 no
su_ticket, mas ha quase 3000 logins com O.S. nesse mesmo workflow e mais de
7000 O.S. abertas — batendo com o volume que o usuario via direto no IXC.

Como nao ha campo confiavel no IXC para confirmar o assunto original de uma
O.S. orfa/reatribuida, o relatorio agora parte do LOGIN (cada login do
cliente deve ter um atendimento de assunto 133 associado, regra de negocio
informada pelo usuario) em vez do atendimento. Para cada login com O.S. no
workflow "Processo Cotacao Parceiro" (id_processo=18, mesma constante
WORKFLOW_COTACAO_PARCEIRO de cria_atendimento_ixc.py), a linha traz o
atendimento ATUAL vinculado a essa O.S. — que pode nao ser mais o de
assunto 133 — e a coluna Observação explica quando isso acontece:

  - vazia: o atendimento atual existe no su_ticket e tem id_assunto = 133
    (situacao esperada, sem problema);
  - "Atendimento ... nao existe mais no IXC": a O.S. ficou orfa (o
    su_ticket foi removido);
  - "Atendimento atual tem assunto diferente ...": a O.S. foi reatribuida a
    um atendimento de outro assunto.

Regra: o login entra no relatorio se tiver pelo menos 1 O.S. nesse workflow
(aberta ou ja solucionada). A coluna de O.S. mostra apenas a que esta aberta
no momento (a mais antiga em aberto, seguindo a mesma convencao de
resolver_os_atendimento_ixc.py); se todas ja foram solucionadas, a coluna
fica vazia. A coluna Setor traz o setor (su_ticket_setor.setor, ex.:
"Comercial | Lastmile") em que essa O.S. de referencia se encontra.

Uso:
    python scripts/integracoes/ixc_relatorio_atendimentos_cotacao_parceiro.py [cliente_id]

Toda comunicacao HTTP com o IXC passa pelo IXCClient (ADR-005, PO-025); o
token vem de IXC_TOKEN (variavel de ambiente / .env), nunca hardcoded no
codigo.
"""
import os
import sys
from collections import defaultdict

import pandas as pd

DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(DIRETORIO_ATUAL))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(BASE_DIR, ".env"))

from apps.integracoes.ixc.client import IXCClient  # noqa: E402


CLIENTE_ID_PADRAO = "575"
ID_ASSUNTO_COTACAO_PARCEIRO = "133"
TITULO_COTACAO_PARCEIRO = "Processo Cotação Parceiro"
ID_PROCESSO_COTACAO_PARCEIRO = "18"  # WORKFLOW_COTACAO_PARCEIRO em cria_atendimento_ixc.py

REGISTROS_POR_PAGINA_LOGIN = 500
REGISTROS_POR_PAGINA_OS = 1000
REGISTROS_POR_PAGINA_TICKET = 200
TAMANHO_LOTE_SETOR = 100
REGISTROS_POR_PAGINA_SETOR = 1000


def _listar_paginado(cliente_ixc, tabela, qtype, query, rp, oper="="):
    pagina = 1
    registros_total = []
    while True:
        payload = {
            "qtype": qtype,
            "query": str(query),
            "oper": oper,
            "page": str(pagina),
            "rp": str(rp),
            "sortname": "id",
            "sortorder": "asc",
        }
        status_code, corpo = cliente_ixc.listar(tabela, payload)
        if status_code is None or not (200 <= status_code < 300) or not isinstance(corpo, dict):
            raise RuntimeError(f"Falha ao consultar {tabela} no IXC: HTTP {status_code} - {corpo}")

        registros = corpo.get("registros") or []
        if not registros:
            break

        registros_total.extend(registros)
        if len(registros) < rp:
            break
        pagina += 1

    return registros_total


def buscar_logins_cliente(cliente_id, cliente_ixc):
    logins = _listar_paginado(cliente_ixc, "radusuarios", "id_cliente", cliente_id, REGISTROS_POR_PAGINA_LOGIN)
    print(f"Logins (radusuarios) encontrados para o cliente {cliente_id}: {len(logins)}")
    return {str(login.get("id")): login for login in logins if login.get("id")}


def buscar_atendimentos_cliente(cliente_id, cliente_ixc):
    atendimentos = _listar_paginado(cliente_ixc, "su_ticket", "id_cliente", cliente_id, REGISTROS_POR_PAGINA_TICKET)
    print(f"Atendimentos (su_ticket) encontrados para o cliente {cliente_id}: {len(atendimentos)}")
    return {str(atendimento.get("id")): atendimento for atendimento in atendimentos if atendimento.get("id")}


def buscar_todas_os_cliente(cliente_id, cliente_ixc):
    registros_os = _listar_paginado(cliente_ixc, "su_oss_chamado", "id_cliente", cliente_id, REGISTROS_POR_PAGINA_OS)
    print(f"O.S. (su_oss_chamado) encontradas para o cliente {cliente_id}: {len(registros_os)}")
    return registros_os


def buscar_tarefas_do_processo(id_processo, cliente_ixc):
    """IDs de wfl_tarefa que pertencem ao workflow indicado — usado para
    reconhecer O.S. do processo "Cotacao Parceiro" mesmo quando o atendimento
    (su_ticket) que as originou ja foi removido ou reatribuido no IXC."""
    tarefas = _listar_paginado(cliente_ixc, "wfl_tarefa", "id_processo", id_processo, rp=100)
    return {str(tarefa.get("id")) for tarefa in tarefas if tarefa.get("id")}


def buscar_setores_por_lotes(setor_ids, cliente_ixc):
    """Retorna {setor_id: nome_do_setor} consultando su_ticket_setor em lotes
    com oper IN. IDs de setor antigos que ja foram removidos do cadastro do
    IXC simplesmente nao aparecem no resultado — o chamador decide o texto de
    fallback."""
    setores_por_id = {}
    ids_unicos = [setor_id for setor_id in dict.fromkeys(setor_ids) if setor_id and setor_id != "0"]

    for inicio in range(0, len(ids_unicos), TAMANHO_LOTE_SETOR):
        lote = ids_unicos[inicio:inicio + TAMANHO_LOTE_SETOR]
        payload = {
            "qtype": "id",
            "query": ",".join(lote),
            "oper": "IN",
            "page": "1",
            "rp": str(REGISTROS_POR_PAGINA_SETOR),
        }
        status_code, corpo = cliente_ixc.listar("su_ticket_setor", payload)
        if status_code is None or not (200 <= status_code < 300) or not isinstance(corpo, dict):
            raise RuntimeError(f"Falha ao consultar su_ticket_setor no IXC: HTTP {status_code} - {corpo}")

        for registro in corpo.get("registros") or []:
            setor_id = str(registro.get("id") or "").strip()
            if setor_id:
                setores_por_id[setor_id] = str(registro.get("setor") or "").strip()

    return setores_por_id


def selecionar_os_referencia(registros_os):
    """O.S. usada para preencher as colunas do relatorio: a mais antiga ainda
    aberta (mesmo criterio de "O.S. atual" do resto do projeto); se todas ja
    foram solucionadas, cai para a mais recente delas (so para ter
    atendimento/setor de referencia — nao aparece como "aberta").
    Retorna (registro_os, esta_aberta)."""
    abertas = [
        registro for registro in registros_os
        if str(registro.get("status") or "").strip().upper() != "F"
    ]
    if abertas:
        abertas.sort(key=lambda registro: int(str(registro.get("id") or "0")))
        return abertas[0], True

    if not registros_os:
        return None, False

    mais_recente = sorted(registros_os, key=lambda registro: int(str(registro.get("id") or "0")))[-1]
    return mais_recente, False


def montar_assunto_e_observacao(ticket_id, tickets_por_id):
    """Compara o atendimento ATUAL vinculado a O.S. de referencia com o
    esperado (assunto 133) e explica a divergencia na Observação, quando
    houver."""
    ticket = tickets_por_id.get(ticket_id)

    if not ticket:
        return "", f"Atendimento {ticket_id} não existe mais no IXC (removido)."

    id_assunto = str(ticket.get("id_assunto") or "").strip()
    titulo = ticket.get("titulo") or ""

    if id_assunto == ID_ASSUNTO_COTACAO_PARCEIRO:
        return titulo or TITULO_COTACAO_PARCEIRO, ""

    return (
        titulo,
        f"Atendimento atual (ID {ticket_id}) tem assunto diferente: "
        f"'{titulo}' (Assunto ID {id_assunto or '--'}).",
    )


def montar_relatorio(cliente_id):
    cliente_ixc = IXCClient()

    logins_por_id = buscar_logins_cliente(cliente_id, cliente_ixc)
    tickets_por_id = buscar_atendimentos_cliente(cliente_id, cliente_ixc)
    todas_os = buscar_todas_os_cliente(cliente_id, cliente_ixc)
    tarefas_cotacao_parceiro = buscar_tarefas_do_processo(ID_PROCESSO_COTACAO_PARCEIRO, cliente_ixc)

    os_por_login = defaultdict(list)
    for registro_os in todas_os:
        if str(registro_os.get("id_wfl_tarefa") or "").strip() not in tarefas_cotacao_parceiro:
            continue
        login_id = str(registro_os.get("id_login") or "").strip()
        if login_id and login_id != "0":
            os_por_login[login_id].append(registro_os)

    print(f"Logins com ao menos 1 O.S. no workflow 'Processo Cotação Parceiro': {len(os_por_login)}")

    referencias = {
        login_id: selecionar_os_referencia(os_do_login)
        for login_id, os_do_login in os_por_login.items()
    }

    setor_ids = [str(os_ref.get("setor") or "").strip() for os_ref, _ in referencias.values()]
    setores_por_id = buscar_setores_por_lotes(setor_ids, cliente_ixc)

    linhas = []
    for login_id in sorted(referencias, key=int):
        os_referencia, esta_aberta = referencias[login_id]
        login = logins_por_id.get(login_id, {})
        ticket_id = str(os_referencia.get("id_ticket") or "").strip()
        setor_id = str(os_referencia.get("setor") or "").strip()
        nome_setor = setores_por_id.get(setor_id, f"Setor {setor_id} (não encontrado no IXC)" if setor_id else "")

        assunto, observacao = montar_assunto_e_observacao(ticket_id, tickets_por_id)

        linhas.append({
            "ID Atendimento": ticket_id,
            "Assunto": assunto,
            "ID OS Aberta no Momento": str(os_referencia.get("id") or "") if esta_aberta else "",
            "Login (Endereço)": login.get("login") or f"(login {login_id} não encontrado no IXC)",
            "Setor": nome_setor,
            "Observação": observacao,
        })

    com_observacao = sum(1 for linha in linhas if linha["Observação"])
    print(f"Linhas geradas: {len(linhas)} (das quais {com_observacao} com Observação sobre o atendimento).")
    return linhas


def gerar_planilha(linhas, caminho_saida):
    dataframe = pd.DataFrame(
        linhas,
        columns=["ID Atendimento", "Assunto", "ID OS Aberta no Momento", "Login (Endereço)", "Setor", "Observação"],
    )
    with pd.ExcelWriter(caminho_saida, engine="xlsxwriter") as writer:
        dataframe.to_excel(writer, sheet_name="Atendimentos", index=False)
        worksheet = writer.sheets["Atendimentos"]
        for col_num, coluna in enumerate(dataframe.columns):
            serie = dataframe[coluna].fillna("").astype(str) if not dataframe.empty else pd.Series([coluna])
            largura = max(len(str(coluna)), serie.map(len).max())
            worksheet.set_column(col_num, col_num, min(max(largura + 2, 14), 60))


if __name__ == "__main__":
    cliente_id_arg = sys.argv[1] if len(sys.argv) > 1 else CLIENTE_ID_PADRAO
    linhas_relatorio = montar_relatorio(cliente_id_arg)
    arquivo_saida = os.path.join(BASE_DIR, f"atendimentos_cotacao_parceiro_cliente_{cliente_id_arg}.xlsx")
    gerar_planilha(linhas_relatorio, arquivo_saida)
    print(f"Planilha gerada em: {arquivo_saida}")
