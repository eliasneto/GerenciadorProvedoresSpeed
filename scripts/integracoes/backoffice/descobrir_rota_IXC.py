import requests
import base64
import urllib3
import json
import re
from itertools import combinations

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

IXC_URL = "https://megainfraestrutura.com.br/webservice/v1"
IXC_TOKEN = "76:54f35af33ea35f3b8a9a8fa14868322662d0465ebbb63fc56c3fb499ac3e1b61"
ENDPOINT = f"{IXC_URL}/su_ticket"

def auth_headers():
    token_b64 = base64.b64encode(IXC_TOKEN.encode("utf-8")).decode("utf-8")
    return {
        "Authorization": f"Basic {token_b64}",
        "Content-Type": "application/json"
    }

def chamar_ixc(payload):
    r = requests.post(
        ENDPOINT,
        json=payload,
        headers=auth_headers(),
        verify=False,
        timeout=30
    )
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}
    return r.status_code, body

def faltando_descricao(body):
    msg = ""
    if isinstance(body, dict):
        msg = str(body.get("message", ""))
    else:
        msg = str(body)
    return "Preencha Descrição" in msg

def montar_payload_base():
    # ajuste esses valores para um caso real válido do seu ambiente
    return {
        "tipo": "I",
        "id_cliente": "55",
        "id_login": "2795",
        "id_assunto": "133",
        "id_filial": "1",
        "prioridade": "M",
        "titulo": "Processo Cotação Parceiro",
        "su_status": "N",
        "id_ticket_setor": "48"
    }

# Campos já testados por vocês
JA_TESTADOS = [
    "descricao",
    "mensagem",
    "mens_inicial",
    "mensagem_inicial",
    "descricao_ticket",
    "texto",
    "observacao",
    "obs",
    "comentario",
    "desc_atendimento",
    "descricao_inicial",
]

# Campos adicionais que valem testar
NOVOS_CANDIDATOS = [
    "descricao_chamado",
    "descricao_os",
    "descricao_atendimento",
    "detalhes",
    "detalhamento",
    "detalhamento_chamado",
    "texto_chamado",
    "texto_atendimento",
    "mensagem_ticket",
    "mensagem_chamado",
    "mensagem_atendimento",
    "observacoes",
    "obs_ticket",
    "obs_atendimento",
    "historico",
    "resumo",
    "anotacao",
    "anotacoes",
    "justificativa",
    "relato",
    "conteudo",
    "descricao_problema",
    "desc_problema",
    "parecer",
    "solicitacao",
    "request",
]

# Campos inspirados por convenções de front/backend
CANDIDATOS_ESPECIAIS = [
    "ticket_mensagem",
    "ticket_descricao",
    "su_descricao",
    "su_mensagem",
    "mensagem_interna",
    "descricao_interna",
    "descricao_inicial_ticket",
    "descricao_atendimento_ticket",
    "tx_descricao",
    "ds_descricao",
    "ds_mensagem",
    "texto_inicial",
]

TODOS_CANDIDATOS = []
for campo in JA_TESTADOS + NOVOS_CANDIDATOS + CANDIDATOS_ESPECIAIS:
    if campo not in TODOS_CANDIDATOS:
        TODOS_CANDIDATOS.append(campo)

VALOR_TESTE = "Teste de processo via API"

def imprimir_resultado(rotulo, payload, status_code, body):
    print("\n" + "=" * 90)
    print(rotulo)
    print("=" * 90)
    print("Payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("\nHTTP:", status_code)
    print("Resposta:")
    print(json.dumps(body, indent=2, ensure_ascii=False))

def teste_individual():
    base = montar_payload_base()
    resultados = []

    for campo in TODOS_CANDIDATOS:
        payload = dict(base)
        payload[campo] = VALOR_TESTE

        status_code, body = chamar_ixc(payload)
        removeu = not faltando_descricao(body)

        resultados.append({
            "campo": campo,
            "removeu_preencha_descricao": removeu,
            "status_code": status_code,
            "body": body,
            "payload": payload,
        })

        print(f"[1 campo] {campo:<30} removeu_erro={removeu}")

        if removeu:
            imprimir_resultado(
                f"SUCESSO COM 1 CAMPO: {campo}",
                payload,
                status_code,
                body
            )
            return resultados, resultados[-1]

    return resultados, None

def teste_duplo():
    base = montar_payload_base()

    for c1, c2 in combinations(TODOS_CANDIDATOS, 2):
        payload = dict(base)
        payload[c1] = VALOR_TESTE
        payload[c2] = VALOR_TESTE

        status_code, body = chamar_ixc(payload)
        removeu = not faltando_descricao(body)

        print(f"[2 campos] {c1} + {c2} -> removeu_erro={removeu}")

        if removeu:
            imprimir_resultado(
                f"SUCESSO COM 2 CAMPOS: {c1} + {c2}",
                payload,
                status_code,
                body
            )
            return {
                "campos": [c1, c2],
                "status_code": status_code,
                "body": body,
                "payload": payload,
            }

    return None

def teste_triplo():
    base = montar_payload_base()

    # reduzimos o universo dos triplos para não explodir demais
    universo = JA_TESTADOS + [
        "descricao_atendimento",
        "mensagem_atendimento",
        "detalhamento",
        "texto_inicial",
        "su_mensagem",
        "ticket_descricao",
        "ticket_mensagem",
    ]
    universo = list(dict.fromkeys(universo))

    for c1, c2, c3 in combinations(universo, 3):
        payload = dict(base)
        payload[c1] = VALOR_TESTE
        payload[c2] = VALOR_TESTE
        payload[c3] = VALOR_TESTE

        status_code, body = chamar_ixc(payload)
        removeu = not faltando_descricao(body)

        print(f"[3 campos] {c1} + {c2} + {c3} -> removeu_erro={removeu}")

        if removeu:
            imprimir_resultado(
                f"SUCESSO COM 3 CAMPOS: {c1} + {c2} + {c3}",
                payload,
                status_code,
                body
            )
            return {
                "campos": [c1, c2, c3],
                "status_code": status_code,
                "body": body,
                "payload": payload,
            }

    return None

def main():
    print("Campos já testados:")
    print(json.dumps(JA_TESTADOS, indent=2, ensure_ascii=False))

    faltam_testar = [c for c in TODOS_CANDIDATOS if c not in JA_TESTADOS]
    print("\nCampos novos que este script vai testar:")
    print(json.dumps(faltam_testar, indent=2, ensure_ascii=False))

    print("\n>>> ETAPA 1: testando 1 campo por vez")
    resultados_individuais, sucesso_1 = teste_individual()
    if sucesso_1:
        return

    print("\n>>> ETAPA 2: testando 2 campos ao mesmo tempo")
    sucesso_2 = teste_duplo()
    if sucesso_2:
        return

    print("\n>>> ETAPA 3: testando 3 campos ao mesmo tempo")
    sucesso_3 = teste_triplo()
    if sucesso_3:
        return

    print("\nNenhuma combinação removeu o erro 'Preencha Descrição'.")
    print("Conclusão provável:")
    print("- o campo tem um nome fora do universo testado; ou")
    print("- a descrição é enviada em estrutura/objeto diferente; ou")
    print("- a UI faz alguma transformação antes de salvar.")

if __name__ == "__main__":
    main()