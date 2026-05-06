import argparse
import json
import os
import sys
from datetime import datetime
from types import SimpleNamespace


DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(DIRETORIO_ATUAL))

if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

APPS_DIR = os.path.join(BASE_DIR, "apps")
if APPS_DIR not in sys.path:
    sys.path.insert(0, APPS_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from clientes.models import Endereco
from core.models import RegistroHistorico
from scripts.integracoes.ixc_client import IXCClient


OS_ENDPOINTS_CANDIDATOS = [
    "su_os",
    "su_ordem_servico",
    "ordem_servico",
    "su_oss_chamado",
    "su_oss",
]

USUARIO_IXC_PADRAO = os.getenv("IXC_DEFAULT_USER_ID", "76")


def normalizar_texto(valor):
    return str(valor or "").strip()


def agora_ixc():
    atual = timezone.localtime() if timezone.is_aware(timezone.now()) else timezone.now()
    return atual.strftime("%d/%m/%Y %H:%M:%S")


def primeiro_preenchido(origem, chaves):
    for chave in chaves:
        valor = normalizar_texto(origem.get(chave))
        if valor:
            return valor
    return ""

def montar_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Finaliza a O.S. atual de um endereco em Comercial | Lastmile no IXC, "
            "enviando a mensagem de encerramento e deixando o workflow do IXC seguir para o proximo setor."
        )
    )
    parser.add_argument("--endereco-id", type=int, help="ID local do Endereco no Django.")
    parser.add_argument("--os-id", help="ID da O.S./ticket no IXC para uso direto, sem depender do snapshot local.")
    parser.add_argument("--cliente-id", help="ID do cliente no IXC quando a finalizacao for feita por O.S. direta.")
    parser.add_argument("--login-id", default="", help="ID do login no IXC para complementar a finalizacao direta.")
    parser.add_argument("--contrato-id", default="", help="ID do contrato no IXC para complementar a finalizacao direta.")
    parser.add_argument("--mensagem", required=True, help="Mensagem obrigatoria da finalizacao.")
    parser.add_argument(
        "--usuario-ixc-id",
        default=USUARIO_IXC_PADRAO,
        help="ID do usuario no IXC usado para a finalizacao.",
    )
    parser.add_argument(
        "--tecnico-ixc-id",
        default="",
        help="ID do tecnico/colaborador responsavel na O.S. Se vazio, mantem o valor atual ou usa o tecnico padrao do fluxo.",
    )
    parser.add_argument("--equipe-id", default="", help="ID da equipe no IXC.")
    parser.add_argument("--diagnostico-id", default="", help="ID do diagnostico no IXC.")
    parser.add_argument("--status-complementar-id", default="", help="ID do status complementar no IXC.")
    parser.add_argument("--resposta-padrao-id", default="", help="ID da resposta padrao no IXC.")
    parser.add_argument("--justificativa-sla", default="", help="Justificativa de SLA atrasado.")
    parser.add_argument(
        "--finaliza-atendimento",
        action="store_true",
        help="Marca a opcao de finalizar atendimento junto com a O.S. se o IXC aceitar.",
    )
    parser.add_argument(
        "--registrar-historico-local",
        action="store_true",
        help="Registra um log local no historico do Endereco ao concluir.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nao chama a API do IXC; apenas monta e exibe os payloads candidatos.",
    )
    return parser


def montar_payloads_finalizacao(endereco, mensagem, args):
    data_hora = agora_ixc()
    os_id = normalizar_texto(endereco.ticket_os_atual_ixc)
    login_id = normalizar_texto(endereco.login_id_ixc)
    cliente_id = normalizar_texto(getattr(endereco.cliente, "id_ixc", ""))
    contrato_id = normalizar_texto(endereco.contrato_id_ixc)
    usuario_ixc_id = normalizar_texto(args.usuario_ixc_id)
    id_filial = normalizar_texto(getattr(endereco, "id_filial_ixc", ""))
    status_os = normalizar_texto(getattr(endereco, "status_ixc", "")) or "F"
    id_assunto = normalizar_texto(getattr(endereco, "id_assunto_ixc", ""))
    id_setor = normalizar_texto(getattr(endereco, "id_setor_ixc", ""))
    prioridade = normalizar_texto(getattr(endereco, "prioridade_ixc", "")) or "N"
    origem_endereco = normalizar_texto(getattr(endereco, "origem_endereco_ixc", ""))
    id_ticket = normalizar_texto(getattr(endereco, "id_ticket_ixc", ""))

    base_variacoes = [
        {
            "action": "finalizar",
            "id": os_id,
            "mensagem": mensagem,
            "data_hora_inicio": data_hora,
            "data_hora_fim": data_hora,
            "id_usuarios": usuario_ixc_id,
            "id_colaborador": usuario_ixc_id,
            "id_equipe": normalizar_texto(args.equipe_id),
            "id_diagnostico": normalizar_texto(args.diagnostico_id),
            "id_status_complementar": normalizar_texto(args.status_complementar_id),
            "id_resposta_padrao": normalizar_texto(args.resposta_padrao_id),
            "justificativa_sla_atrasado": normalizar_texto(args.justificativa_sla),
            "finaliza_atendimento": "S" if args.finaliza_atendimento else "N",
            "gera_comissao": "S",
            "id_login": login_id,
            "id_cliente": cliente_id,
            "id_contrato": contrato_id,
            "id_filial": id_filial,
            "status": status_os,
            "id_assunto": id_assunto,
            "setor": id_setor,
            "prioridade": prioridade,
            "origem_endereco": origem_endereco,
            "id_ticket": id_ticket,
        },
        {
            "action": "finalizar",
            "id": os_id,
            "mensagem": mensagem,
            "menssagem": mensagem,
            "data_inicio": data_hora,
            "data_fim": data_hora,
            "id_usuarios": usuario_ixc_id,
            "id_usuario": usuario_ixc_id,
            "equipe": normalizar_texto(args.equipe_id),
            "diagnostico": normalizar_texto(args.diagnostico_id),
            "status_complementar": normalizar_texto(args.status_complementar_id),
            "resposta_padrao": normalizar_texto(args.resposta_padrao_id),
            "justificativa": normalizar_texto(args.justificativa_sla),
            "finalizar_atendimento": "S" if args.finaliza_atendimento else "N",
            "gera_comissao": "S",
            "id_login": login_id,
            "id_cliente": cliente_id,
            "id_contrato": contrato_id,
            "id_filial": id_filial,
            "status": status_os,
            "id_assunto": id_assunto,
            "setor": id_setor,
            "prioridade": prioridade,
            "origem_endereco": origem_endereco,
            "id_ticket": id_ticket,
        },
        {
            "action": "finalizar",
            "id_os": os_id,
            "mensagem": mensagem,
            "data_hora_inicio": data_hora,
            "data_hora_fim": data_hora,
            "colaborador_responsavel": usuario_ixc_id,
            "id_usuarios": usuario_ixc_id,
            "equipe": normalizar_texto(args.equipe_id),
            "id_diagnostico": normalizar_texto(args.diagnostico_id),
            "id_status_complementar": normalizar_texto(args.status_complementar_id),
            "justificativa_sla_atrasado": normalizar_texto(args.justificativa_sla),
            "finaliza_atendimento": "S" if args.finaliza_atendimento else "N",
            "gera_comissao": "S",
            "id_login": login_id,
            "id_cliente": cliente_id,
            "id_contrato": contrato_id,
            "id_filial": id_filial,
            "status": status_os,
            "id_assunto": id_assunto,
            "setor": id_setor,
            "prioridade": prioridade,
            "origem_endereco": origem_endereco,
            "id_ticket": id_ticket,
        },
    ]

    payloads = []
    for endpoint in OS_ENDPOINTS_CANDIDATOS:
        for indice, base in enumerate(base_variacoes, start=1):
            payload_limpo = {chave: valor for chave, valor in base.items() if valor not in ("", None)}
            payloads.append({
                "endpoint": endpoint,
                "rotulo": f"{endpoint}::variacao_{indice}",
                "payload": payload_limpo,
            })
    return payloads


def buscar_detalhes_os_ixc(os_id):
    client = IXCClient()
    consultas = [
        ("su_oss_chamado", "su_oss_chamado.id"),
        ("su_ordem_servico", "su_ordem_servico.id"),
        ("ordem_servico", "ordem_servico.id"),
    ]
    for endpoint, qtype in consultas:
        payload = {
            "qtype": qtype,
            "query": os_id,
            "oper": "=",
            "page": "1",
            "rp": "1",
            "sortname": qtype.rsplit(".", 1)[0] + ".id",
            "sortorder": "desc",
        }
        status_code, body = client.listar(endpoint, payload)
        if status_code != 200 or not isinstance(body, dict):
            continue
        registros = body.get("registros") or []
        if registros:
            return registros[0]
    return {}


def construir_alvo_finalizacao(args):
    if args.endereco_id:
        endereco = Endereco.objects.select_related("cliente").filter(pk=args.endereco_id).first()
        if not endereco:
            print(json.dumps({"ok": False, "message": f"Endereco {args.endereco_id} nao encontrado."}, ensure_ascii=False, indent=2))
            raise SystemExit(1)

        if not normalizar_texto(endereco.ticket_os_atual_ixc):
            print(json.dumps({"ok": False, "message": "O endereco nao possui ticket/O.S. atual mapeado no snapshot local."}, ensure_ascii=False, indent=2))
            raise SystemExit(1)
        return endereco

    os_id = normalizar_texto(args.os_id)
    cliente_id = normalizar_texto(args.cliente_id)
    if not os_id or not cliente_id:
        print(
            json.dumps(
                {
                    "ok": False,
                    "message": "Informe --endereco-id ou a combinacao --os-id + --cliente-id.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(1)

    detalhes_os = buscar_detalhes_os_ixc(os_id)
    cliente_stub = SimpleNamespace(id_ixc=cliente_id)
    return SimpleNamespace(
        id=None,
        cliente=cliente_stub,
        login_ixc="",
        login_id_ixc=normalizar_texto(args.login_id) or primeiro_preenchido(detalhes_os, ["id_login"]),
        contrato_id_ixc=normalizar_texto(args.contrato_id) or primeiro_preenchido(detalhes_os, ["id_contrato", "id_contrato_kit"]),
        ticket_os_atual_ixc=os_id,
        id_filial_ixc=primeiro_preenchido(detalhes_os, ["id_filial"]),
        status_ixc=primeiro_preenchido(detalhes_os, ["status"]),
        id_assunto_ixc=primeiro_preenchido(detalhes_os, ["id_assunto"]),
        id_setor_ixc=primeiro_preenchido(detalhes_os, ["setor", "id_setor"]),
        prioridade_ixc=primeiro_preenchido(detalhes_os, ["prioridade"]),
        origem_endereco_ixc=primeiro_preenchido(detalhes_os, ["origem_endereco"]),
        id_ticket_ixc=primeiro_preenchido(detalhes_os, ["id_ticket"]),
        id_tecnico_ixc=primeiro_preenchido(detalhes_os, ["id_tecnico"]),
        data_abertura_ixc=primeiro_preenchido(detalhes_os, ["data_abertura"]),
        tipo_ixc=primeiro_preenchido(detalhes_os, ["tipo"]),
        id_wfl_tarefa_ixc=primeiro_preenchido(detalhes_os, ["id_wfl_tarefa"]),
        id_wfl_param_os_ixc=primeiro_preenchido(detalhes_os, ["id_wfl_param_os"]),
        id_cidade_ixc=primeiro_preenchido(detalhes_os, ["id_cidade"]),
        melhor_horario_agenda_ixc=primeiro_preenchido(detalhes_os, ["melhor_horario_agenda"]),
        liberado_ixc=primeiro_preenchido(detalhes_os, ["liberado"]),
        origem_os_aberta_ixc=primeiro_preenchido(detalhes_os, ["origem_os_aberta"]),
        protocolo_ixc=primeiro_preenchido(detalhes_os, ["protocolo"]),
        endereco_ixc=primeiro_preenchido(detalhes_os, ["endereco"]),
        complemento_ixc=primeiro_preenchido(detalhes_os, ["complemento"]),
        id_condominio_ixc=primeiro_preenchido(detalhes_os, ["id_condominio"]),
        bairro_ixc=primeiro_preenchido(detalhes_os, ["bairro"]),
        impresso_ixc=primeiro_preenchido(detalhes_os, ["impresso"]),
        id_estrutura_ixc=primeiro_preenchido(detalhes_os, ["id_estrutura"]),
        origem_endereco_estrutura_ixc=primeiro_preenchido(detalhes_os, ["origem_endereco_estrutura"]),
        origem_cadastro_ixc=primeiro_preenchido(detalhes_os, ["origem_cadastro"]),
        status_assinatura_ixc=primeiro_preenchido(detalhes_os, ["status_assinatura"]),
        habilita_assinatura_cliente_ixc=primeiro_preenchido(detalhes_os, ["habilita_assinatura_cliente"]),
        mensagem_ixc=primeiro_preenchido(detalhes_os, ["mensagem"]),
    )


def montar_payload_put_existente(endereco, mensagem, args):
    data_hora = agora_ixc()
    tecnico_ixc_id = normalizar_texto(args.tecnico_ixc_id) or normalizar_texto(getattr(endereco, "id_tecnico_ixc", "")) or "84"
    return {
        "id": normalizar_texto(endereco.ticket_os_atual_ixc),
        "tipo": normalizar_texto(getattr(endereco, "tipo_ixc", "")) or "C",
        "id_filial": normalizar_texto(getattr(endereco, "id_filial_ixc", "")),
        "id_wfl_tarefa": normalizar_texto(getattr(endereco, "id_wfl_tarefa_ixc", "")),
        "status": "F",
        "data_abertura": normalizar_texto(getattr(endereco, "data_abertura_ixc", "")),
        "melhor_horario_agenda": normalizar_texto(getattr(endereco, "melhor_horario_agenda_ixc", "")) or "Q",
        "liberado": normalizar_texto(getattr(endereco, "liberado_ixc", "")) or "1",
        "id_cliente": normalizar_texto(getattr(endereco.cliente, "id_ixc", "")),
        "id_assunto": normalizar_texto(getattr(endereco, "id_assunto_ixc", "")),
        "setor": normalizar_texto(getattr(endereco, "id_setor_ixc", "")),
        "id_cidade": normalizar_texto(getattr(endereco, "id_cidade_ixc", "")),
        "id_tecnico": tecnico_ixc_id,
        "prioridade": normalizar_texto(getattr(endereco, "prioridade_ixc", "")) or "N",
        "origem_os_aberta": normalizar_texto(getattr(endereco, "origem_os_aberta_ixc", "")) or "P",
        "mensagem": normalizar_texto(getattr(endereco, "mensagem_ixc", "")),
        "mensagem_resposta": mensagem,
        "protocolo": normalizar_texto(getattr(endereco, "protocolo_ixc", "")),
        "endereco": normalizar_texto(getattr(endereco, "endereco_ixc", "")),
        "complemento": normalizar_texto(getattr(endereco, "complemento_ixc", "")),
        "id_condominio": normalizar_texto(getattr(endereco, "id_condominio_ixc", "")) or "0",
        "bairro": normalizar_texto(getattr(endereco, "bairro_ixc", "")),
        "impresso": normalizar_texto(getattr(endereco, "impresso_ixc", "")) or "N",
        "data_inicio": data_hora,
        "data_final": data_hora,
        "data_fechamento": data_hora,
        "id_wfl_param_os": normalizar_texto(getattr(endereco, "id_wfl_param_os_ixc", "")),
        "gera_comissao": "S",
        "id_su_diagnostico": normalizar_texto(args.diagnostico_id) or "0",
        "id_estrutura": normalizar_texto(getattr(endereco, "id_estrutura_ixc", "")),
        "id_login": normalizar_texto(getattr(endereco, "login_id_ixc", "")),
        "id_ticket": normalizar_texto(getattr(endereco, "id_ticket_ixc", "")),
        "origem_endereco": normalizar_texto(getattr(endereco, "origem_endereco_ixc", "")) or "L",
        "justificativa_sla_atrasado": normalizar_texto(args.justificativa_sla),
        "origem_endereco_estrutura": normalizar_texto(getattr(endereco, "origem_endereco_estrutura_ixc", "")) or "E",
        "origem_cadastro": normalizar_texto(getattr(endereco, "origem_cadastro_ixc", "")) or "P",
        "id_contrato_kit": normalizar_texto(getattr(endereco, "contrato_id_ixc", "")),
        "status_assinatura": normalizar_texto(getattr(endereco, "status_assinatura_ixc", "")) or "A",
        "habilita_assinatura_cliente": normalizar_texto(getattr(endereco, "habilita_assinatura_cliente_ixc", "")) or "N",
        "id_usuarios": normalizar_texto(args.usuario_ixc_id),
        "finaliza_atendimento": "S" if args.finaliza_atendimento else "N",
    }


def resposta_indica_sucesso(status_code, body):
    if status_code not in (200, 201):
        return False

    if isinstance(body, dict):
        tipo = normalizar_texto(body.get("type")).lower()
        mensagem = normalizar_texto(body.get("message")).lower()
        if tipo == "success":
            return True
        if "sucesso" in mensagem or "finaliz" in mensagem:
            return True
        if body.get("resultado") is True:
            return True

    return False


def registrar_historico_local(endereco, mensagem, resultado):
    RegistroHistorico.objects.create(
        tipo="sistema",
        acao=(
            "Tentativa de finalizacao de O.S. Lastmile no IXC.\n\n"
            f"Login: {endereco.login_ixc or '--'}\n"
            f"Ticket/O.S.: {endereco.ticket_os_atual_ixc or '--'}\n"
            f"Mensagem enviada: {mensagem}\n"
            f"Resultado: {resultado}"
        ),
        content_type=ContentType.objects.get_for_model(Endereco),
        object_id=endereco.id,
    )


def executar_finalizacao(endereco, mensagem, args):
    client = IXCClient()
    payload_put = {k: v for k, v in montar_payload_put_existente(endereco, mensagem, args).items() if v not in ("", None)}
    payloads = [
        {
            "endpoint": f"su_oss_chamado/{normalizar_texto(endereco.ticket_os_atual_ixc)}",
            "rotulo": "su_oss_chamado::put_existente",
            "payload": payload_put,
            "method": "put",
        }
    ]

    if args.dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "payloads": payloads,
        }

    tentativas = []

    for item in payloads:
        if item.get("method") == "put":
            status_code, body = client.put(item["endpoint"], item["payload"])
        else:
            status_code, body = client.escrever(item["endpoint"], item["payload"])
        tentativa = {
            "endpoint": item["endpoint"],
            "rotulo": item["rotulo"],
            "status_code": status_code,
            "body": body,
            "payload": item["payload"],
        }
        tentativas.append(tentativa)

        if resposta_indica_sucesso(status_code, body):
            return {
                "ok": True,
                "endpoint_vencedor": item["endpoint"],
                "rotulo_vencedor": item["rotulo"],
                "tentativas": tentativas,
            }

    return {
        "ok": False,
        "tentativas": tentativas,
    }


def main():
    parser = montar_parser()
    args = parser.parse_args()
    endereco = construir_alvo_finalizacao(args)

    resultado = executar_finalizacao(endereco, args.mensagem, args)

    if args.registrar_historico_local and getattr(endereco, "id", None):
        registrar_historico_local(
            endereco,
            args.mensagem,
            "Sucesso" if resultado.get("ok") else "Falha",
        )

    print(json.dumps(resultado, ensure_ascii=False, indent=2, default=str))
    raise SystemExit(0 if resultado.get("ok") else 2)


if __name__ == "__main__":
    main()
