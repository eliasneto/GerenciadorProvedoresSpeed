from io import BytesIO

from apps.integracoes.ixc.services.cria_atendimento_ixc import limpar_texto, normalizar_id_numerico
from apps.integracoes.ixc.services.desativar_atendimento_ixc import (
    buscar_atendimento_ixc_por_id,
    listar_os_para_desativacao,
)
from scripts.integracoes.ixc_finalizacao_service import (
    finalizar_os_existente,
    normalizar_texto,
    resolver_usuario_ixc_por_email,
    resumir_erro_finalizacao,
)
from scripts.integracoes.ixc_ticket_arquivo_service import anexar_arquivo_ticket_ixc


CONFIRMACAO_RESOLUCAO_VALIDAS = {"SIM", "S", "TRUE", "1", "CONFIRMADO", "CONFIRMAR"}
VALORES_SIM = {"SIM", "S", "TRUE", "1"}
VALORES_NAO = {"NAO", "NÃO", "N", "FALSE", "0"}
MENSAGEM_PADRAO_RESOLUCAO = "O.S. solucionada administrativamente. Atendimento permanece ativo."
LIMITE_MAXIMO_RODADAS_FECHAMENTO = 20
STATUS_ATENDIMENTO_EM_PROGRESSO = "EP"

COLUNAS_OBRIGATORIAS_RESOLUCAO_OS_ATENDIMENTO_IXC = [
    "Atendimento_ID",
    "Confirmar_Resolucao",
    "Tem_Anexo",
    "Fechar_Todas_OS",
]
COLUNAS_OPCIONAIS_RESOLUCAO_OS_ATENDIMENTO_IXC = [
    "Nome_Anexo",
    "Mais_de_um_anexo",
    "Nome_Anexo_2",
    "Nome_Anexo_3",
    "Mensagem",
    "Proxima_Tarefa_ID",
    "Informar_Colaborador",
    "Email_Colaborador",
]

# Tarefas de decisao conhecidas do workflow do IXC (RN-019). Lista de referencia
# para a aba de ajuda da planilha — nao e uma validacao: o IXC e quem aceita ou
# recusa o ID informado em Proxima_Tarefa_ID. Ampliar conforme novas tarefas de
# decisao forem identificadas pelo usuario.
TAREFAS_DECISAO_CONHECIDAS_RESOLUCAO_OS_ATENDIMENTO_IXC = [
    {"ID": "147", "Tarefa": "Realizar Implantacao"},
    {"ID": "150", "Tarefa": "Realizar Implantacao EACE"},
    {"ID": "151", "Tarefa": "Nao Atende Requisitos Tecnicos"},
]

INSTRUCOES_RESOLUCAO_OS_ATENDIMENTO_IXC = [
    {
        "Campo": "Atendimento_ID",
        "Descricao": "ID numerico do atendimento no IXC cujas O.S. abertas serao fechadas.",
        "Tipo de dado": "Numero inteiro",
        "Obrigatorio?": "Sim",
        "Regras / Exemplo": "Use apenas o ID numerico do atendimento. Ex.: 6502",
    },
    {
        "Campo": "Confirmar_Resolucao",
        "Descricao": "Confirmacao explicita para autorizar o fechamento das O.S. do atendimento.",
        "Tipo de dado": "Texto curto",
        "Obrigatorio?": "Sim",
        "Regras / Exemplo": "Digite exatamente SIM.",
    },
    {
        "Campo": "Tem_Anexo",
        "Descricao": "Indica se este atendimento tem um documento a anexar antes do fechamento das O.S.",
        "Tipo de dado": "Texto curto",
        "Obrigatorio?": "Sim",
        "Regras / Exemplo": "Digite SIM ou NAO. Se SIM, preencha tambem Nome_Anexo.",
    },
    {
        "Campo": "Fechar_Todas_OS",
        "Descricao": "SIM fecha todas as O.S. abertas do atendimento (repetindo ate esgotar). NAO fecha somente a O.S. atual.",
        "Tipo de dado": "Texto curto",
        "Obrigatorio?": "Sim",
        "Regras / Exemplo": "Digite SIM ou NAO.",
    },
    {
        "Campo": "Nome_Anexo",
        "Descricao": "Nome do arquivo PDF (dentro do ZIP importado) a anexar neste atendimento.",
        "Tipo de dado": "Texto",
        "Obrigatorio?": "Somente quando Tem_Anexo = SIM",
        "Regras / Exemplo": "Deve corresponder a um arquivo PDF dentro do ZIP. Ex.: contrato_cliente123.pdf",
    },
    {
        "Campo": "Mais_de_um_anexo",
        "Descricao": "Indica se este atendimento tem mais de um documento a anexar (ex.: contrato + aditivos).",
        "Tipo de dado": "Texto curto",
        "Obrigatorio?": "Nao (avaliado somente quando Tem_Anexo = SIM)",
        "Regras / Exemplo": "Digite SIM ou NAO. Se SIM, preencha tambem Nome_Anexo_2 e/ou Nome_Anexo_3.",
    },
    {
        "Campo": "Nome_Anexo_2",
        "Descricao": "Nome do segundo arquivo PDF (dentro do ZIP importado) a anexar neste atendimento.",
        "Tipo de dado": "Texto",
        "Obrigatorio?": "Somente quando Mais_de_um_anexo = SIM e houver um segundo arquivo",
        "Regras / Exemplo": "Deve corresponder a um arquivo PDF dentro do ZIP. Ignorado se Mais_de_um_anexo = NAO.",
    },
    {
        "Campo": "Nome_Anexo_3",
        "Descricao": "Nome do terceiro arquivo PDF (dentro do ZIP importado) a anexar neste atendimento.",
        "Tipo de dado": "Texto",
        "Obrigatorio?": "Somente quando Mais_de_um_anexo = SIM e houver um terceiro arquivo",
        "Regras / Exemplo": "Deve corresponder a um arquivo PDF dentro do ZIP. Ignorado se Mais_de_um_anexo = NAO.",
    },
    {
        "Campo": "Mensagem",
        "Descricao": "Mensagem registrada no fechamento de cada O.S. e usada como descricao do anexo.",
        "Tipo de dado": "Texto",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Se ficar vazio, usamos uma mensagem padrao administrativa.",
    },
    {
        "Campo": "Proxima_Tarefa_ID",
        "Descricao": (
            "ID da proxima tarefa do workflow no IXC, exigido quando a O.S. abrir uma tela de "
            "decisao (ex.: Realizar Implantacao, Realizar Implantacao EACE, Nao Atende Requisitos "
            "Tecnicos). Consulte a aba Tarefas_Decisao_IXC para ver os IDs conhecidos."
        ),
        "Tipo de dado": "Numero inteiro",
        "Obrigatorio?": "Somente quando a O.S. exigir escolha de proxima tarefa",
        "Regras / Exemplo": "Use apenas o ID numerico da tarefa. Ex.: 147. Se a O.S. nao exigir decisao, deixe vazio.",
    },
    {
        "Campo": "Informar_Colaborador",
        "Descricao": "Indica se a finalizacao deve ser atribuida a outro colaborador do IXC, em vez de quem esta executando a automacao.",
        "Tipo de dado": "Texto curto",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Digite SIM ou NAO. Se SIM, preencha tambem Email_Colaborador.",
    },
    {
        "Campo": "Email_Colaborador",
        "Descricao": "E-mail do colaborador do IXC que deve constar como responsavel pela finalizacao desta linha.",
        "Tipo de dado": "Texto",
        "Obrigatorio?": "Somente quando Informar_Colaborador = SIM",
        "Regras / Exemplo": "Deve corresponder a um usuario cadastrado no IXC. Ignorado se Informar_Colaborador = NAO.",
    },
]


def normalizar_confirmacao_resolucao(valor):
    texto = limpar_texto(valor).upper()
    if texto in CONFIRMACAO_RESOLUCAO_VALIDAS:
        return True, None
    return False, "Confirmar_Resolucao deve ser preenchido com SIM para fechar as O.S. do atendimento."


def normalizar_sim_nao(valor, nome_campo):
    texto = limpar_texto(valor).upper()
    if texto in VALORES_SIM:
        return True, None
    if texto in VALORES_NAO:
        return False, None
    return None, f"{nome_campo} deve ser preenchido com SIM ou NAO."


def normalizar_tem_anexo(valor):
    return normalizar_sim_nao(valor, "Tem_Anexo")


def normalizar_fechar_todas_os(valor):
    return normalizar_sim_nao(valor, "Fechar_Todas_OS")


def normalizar_sim_nao_opcional(valor, nome_campo):
    texto = limpar_texto(valor).upper()
    if not texto:
        return False, None
    if texto in VALORES_SIM:
        return True, None
    if texto in VALORES_NAO:
        return False, None
    return None, f"{nome_campo} deve ser preenchido com SIM ou NAO."


def normalizar_mais_de_um_anexo(valor):
    return normalizar_sim_nao_opcional(valor, "Mais_de_um_anexo")


def normalizar_informar_colaborador(valor):
    return normalizar_sim_nao_opcional(valor, "Informar_Colaborador")


def normalizar_proxima_tarefa_id(valor):
    return normalizar_id_numerico(valor, "Proxima_Tarefa_ID", obrigatorio=False)


def _normalizar_nome_comparacao(nome):
    return limpar_texto(nome).strip().casefold()


def localizar_anexo_no_zip(zip_arquivos, nome_anexo):
    if not zip_arquivos:
        return None, None, "Nenhum arquivo ZIP de anexos foi importado nesta execucao."

    nome_normalizado = _normalizar_nome_comparacao(nome_anexo)
    for nome_no_zip in zip_arquivos.namelist():
        if nome_no_zip.endswith("/"):
            continue
        nome_base = nome_no_zip.rsplit("/", 1)[-1]
        if _normalizar_nome_comparacao(nome_base) != nome_normalizado:
            continue
        if not nome_base.lower().endswith(".pdf"):
            return None, nome_base, f"O arquivo '{nome_base}' encontrado no ZIP nao e um PDF."
        return zip_arquivos.read(nome_no_zip), nome_base, None

    return None, None, f"Nenhum arquivo chamado '{nome_anexo}' foi encontrado no ZIP de anexos."


def _anexar_um_arquivo_ao_atendimento(atendimento_id, nome_anexo, zip_arquivos, mensagem):
    conteudo_anexo, nome_real_anexo, erro_zip = localizar_anexo_no_zip(zip_arquivos, nome_anexo)
    if erro_zip:
        return False, erro_zip

    arquivo_extraido = BytesIO(conteudo_anexo)
    arquivo_extraido.name = nome_real_anexo
    arquivo_extraido.content_type = "application/pdf"

    resultado_anexo = anexar_arquivo_ticket_ixc(atendimento_id, arquivo_extraido, descricao=mensagem)
    if resultado_anexo.get("ok"):
        return True, None

    body_anexo = resultado_anexo.get("body")
    detalhe = (
        (body_anexo.get("message") if isinstance(body_anexo, dict) else "")
        or resultado_anexo.get("message")
        or "Falha ao anexar o documento no IXC."
    )
    return False, detalhe


def _falha_fechamento_os(atendimento_id, os_id, resultado, resultados, tem_anexo):
    os_fechadas_antes = [
        item_id for item_id, item_resultado in resultados[:-1] if item_resultado.get("ok")
    ]
    trecho_sucesso = (
        f" O.S. ja fechadas antes da falha: {', '.join(os_fechadas_antes)}."
        if os_fechadas_antes
        else ""
    )
    prefixo_falha = f"Documento anexado ao atendimento {atendimento_id}, mas " if tem_anexo else ""
    return (
        False,
        (
            f"{prefixo_falha}falhou ao fechar a O.S. {os_id}: "
            f"{resumir_erro_finalizacao(resultado)}{trecho_sucesso}"
        ),
        atendimento_id,
        ", ".join(os_fechadas_antes),
    )


def executar_resolucao_os_atendimento_ixc(dados, zip_arquivos=None, usuario_sistema=None):
    linha = {str(k).replace("﻿", "").strip(): v for k, v in dados.items()}

    atendimento_id, erro = normalizar_id_numerico(
        linha.get("Atendimento_ID"),
        "Atendimento_ID",
        obrigatorio=True,
    )
    if erro:
        return False, erro, "", ""

    confirmado, erro_confirmacao = normalizar_confirmacao_resolucao(
        linha.get("Confirmar_Resolucao")
    )
    if not confirmado:
        return False, erro_confirmacao, atendimento_id, ""

    tem_anexo, erro_tem_anexo = normalizar_tem_anexo(linha.get("Tem_Anexo"))
    if erro_tem_anexo:
        return False, erro_tem_anexo, atendimento_id, ""

    mais_de_um_anexo = False
    if tem_anexo:
        mais_de_um_anexo, erro_mais_de_um_anexo = normalizar_mais_de_um_anexo(linha.get("Mais_de_um_anexo"))
        if erro_mais_de_um_anexo:
            return False, erro_mais_de_um_anexo, atendimento_id, ""

    fechar_todas_os, erro_fechar_todas_os = normalizar_fechar_todas_os(linha.get("Fechar_Todas_OS"))
    if erro_fechar_todas_os:
        return False, erro_fechar_todas_os, atendimento_id, ""

    proxima_tarefa_id, erro_proxima_tarefa = normalizar_proxima_tarefa_id(linha.get("Proxima_Tarefa_ID"))
    if erro_proxima_tarefa:
        return False, erro_proxima_tarefa, atendimento_id, ""

    informar_colaborador, erro_informar_colaborador = normalizar_informar_colaborador(
        linha.get("Informar_Colaborador")
    )
    if erro_informar_colaborador:
        return False, erro_informar_colaborador, atendimento_id, ""

    email_colaborador = None
    if informar_colaborador:
        email_colaborador = limpar_texto(linha.get("Email_Colaborador"))
        if not email_colaborador:
            return (
                False,
                "Email_Colaborador e obrigatorio quando Informar_Colaborador = SIM.",
                atendimento_id,
                "",
            )

        resolucao_colaborador = resolver_usuario_ixc_por_email(email_colaborador)
        if resolucao_colaborador.get("fallback"):
            return (
                False,
                (
                    f"O e-mail '{email_colaborador}' informado em Email_Colaborador nao foi "
                    "encontrado no cadastro de usuarios do IXC."
                ),
                atendimento_id,
                "",
            )

    atendimento = buscar_atendimento_ixc_por_id(atendimento_id)
    if not atendimento:
        return False, f"Atendimento {atendimento_id} nao encontrado no IXC.", atendimento_id, ""

    status_atendimento = normalizar_texto(atendimento.get("su_status")).upper()
    if status_atendimento != STATUS_ATENDIMENTO_EM_PROGRESSO:
        return (
            False,
            (
                f"Atendimento {atendimento_id} nao pode ter O.S. fechada: o status do atendimento "
                f"e diferente de 'Em progresso' (codigo IXC: {status_atendimento or '--'})."
            ),
            atendimento_id,
            "",
        )

    mensagem = limpar_texto(linha.get("Mensagem")) or MENSAGEM_PADRAO_RESOLUCAO

    if tem_anexo:
        nome_anexo = limpar_texto(linha.get("Nome_Anexo"))
        if not nome_anexo:
            return (
                False,
                "Nome_Anexo e obrigatorio quando Tem_Anexo = SIM.",
                atendimento_id,
                "",
            )

        nomes_anexo = [nome_anexo]
        if mais_de_um_anexo:
            for campo_anexo_extra in ("Nome_Anexo_2", "Nome_Anexo_3"):
                nome_anexo_extra = limpar_texto(linha.get(campo_anexo_extra))
                if nome_anexo_extra:
                    nomes_anexo.append(nome_anexo_extra)

        for nome_anexo_atual in nomes_anexo:
            anexo_ok, erro_anexo = _anexar_um_arquivo_ao_atendimento(
                atendimento_id, nome_anexo_atual, zip_arquivos, mensagem
            )
            if not anexo_ok:
                return (
                    False,
                    (
                        f"Nao foi possivel anexar o documento '{nome_anexo_atual}' ao atendimento "
                        f"{atendimento_id}: {erro_anexo} Nenhuma O.S. foi fechada."
                    ),
                    atendimento_id,
                    "",
                )

    resultados = []
    esgotou_sem_limite = False

    if fechar_todas_os:
        for _rodada in range(LIMITE_MAXIMO_RODADAS_FECHAMENTO):
            os_abertas = listar_os_para_desativacao(atendimento_id)
            if not os_abertas:
                esgotou_sem_limite = True
                break

            for os_atual in os_abertas:
                os_id = normalizar_texto(os_atual.get("id"))
                resultado = finalizar_os_existente(
                    os_id,
                    mensagem=mensagem,
                    finaliza_atendimento=False,
                    usuario_sistema=usuario_sistema,
                    id_proxima_tarefa=proxima_tarefa_id or None,
                    email_ixc=email_colaborador,
                )
                resultados.append((os_id, resultado))

                if not resultado.get("ok"):
                    return _falha_fechamento_os(atendimento_id, os_id, resultado, resultados, tem_anexo)
    else:
        # Fechar_Todas_OS = NAO: fecha somente a O.S. atual (a mais antiga em aberto),
        # sem repetir a busca para perseguir novas tarefas do workflow (RN-010 nao se aplica aqui).
        os_abertas = listar_os_para_desativacao(atendimento_id)
        esgotou_sem_limite = True
        if os_abertas:
            os_atual = os_abertas[0]
            os_id = normalizar_texto(os_atual.get("id"))
            resultado = finalizar_os_existente(
                os_id,
                mensagem=mensagem,
                finaliza_atendimento=False,
                usuario_sistema=usuario_sistema,
                id_proxima_tarefa=proxima_tarefa_id or None,
                email_ixc=email_colaborador,
            )
            resultados.append((os_id, resultado))

            if not resultado.get("ok"):
                return _falha_fechamento_os(atendimento_id, os_id, resultado, resultados, tem_anexo)

    if not resultados:
        mensagem_sem_os = (
            f"Documento anexado ao atendimento {atendimento_id}. Nenhuma O.S. aberta encontrada para fechar."
            if tem_anexo
            else f"Atendimento {atendimento_id} nao possui O.S. aberta para fechar."
        )
        return True, mensagem_sem_os, atendimento_id, ""

    os_ids_fechadas = ", ".join(item_id for item_id, _ in resultados)

    if not esgotou_sem_limite:
        # O laco rodou LIMITE_MAXIMO_RODADAS_FECHAMENTO vezes sem encontrar uma rodada
        # com lista vazia; o IXC pode ter criado uma nova O.S. na ultima rodada, entao
        # precisamos checar de novo antes de decidir entre sucesso e falha (RN-010).
        if listar_os_para_desativacao(atendimento_id):
            return (
                False,
                (
                    f"Atendimento {atendimento_id}: limite de {LIMITE_MAXIMO_RODADAS_FECHAMENTO} rodadas de "
                    f"fechamento atingido e ainda ha O.S. aberta. O.S. fechadas até aqui: {os_ids_fechadas}."
                ),
                atendimento_id,
                os_ids_fechadas,
            )

    atendimento_atualizado = buscar_atendimento_ixc_por_id(atendimento_id)
    atendimento_ainda_ativo = normalizar_texto(atendimento_atualizado.get("status")).upper() != "F"
    aviso_atendimento = (
        ""
        if atendimento_ainda_ativo
        else (
            " Atencao: o atendimento apareceu como finalizado no IXC apos o fechamento das O.S.; "
            "verifique manualmente."
        )
    )

    prefixo_sucesso = "Documento anexado e " if tem_anexo else ""
    return (
        True,
        (
            f"{prefixo_sucesso}{len(resultados)} O.S. fechada(s) no atendimento {atendimento_id}: "
            f"{os_ids_fechadas}.{aviso_atendimento}"
        ),
        atendimento_id,
        os_ids_fechadas,
    )
