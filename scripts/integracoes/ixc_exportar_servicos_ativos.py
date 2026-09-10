"""Extrai o catalogo de Produtos e Servicos do IXC (tabela `produtos_servicos`)
e exporta os registros ativos para uma planilha na raiz do projeto.

Uso:
    python scripts/integracoes/ixc_exportar_servicos_ativos.py

Toda comunicacao HTTP com o IXC passa pelo IXCClient (ADR-005, PO-025); o
token vem de IXC_TOKEN (variavel de ambiente / .env), nunca hardcoded no
codigo.
"""
import os
import sys

import pandas as pd

DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(DIRETORIO_ATUAL))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(BASE_DIR, ".env"))

from apps.integracoes.ixc.client import IXCClient  # noqa: E402


TABELA = "produtos_servicos"
REGISTROS_POR_PAGINA = 100
ARQUIVO_SAIDA = os.path.join(BASE_DIR, "servicos_ixc_ativos.xlsx")


def _esta_ativo(registro):
    """Identifica se o servico esta ativo. A maioria das tabelas do IXC usa
    o campo 'ativo' (S/N); cai para 'status' (A/I) quando o campo nao existir."""
    if "ativo" in registro:
        return str(registro.get("ativo") or "").strip().upper() in {"S", "SIM", "1"}
    if "status" in registro:
        return str(registro.get("status") or "").strip().upper() in {"A", "ATIVO"}
    return True


def buscar_servicos_ativos():
    cliente = IXCClient()
    pagina = 1
    servicos_ativos = []
    total_lido = 0

    while True:
        payload = {
            "qtype": "id",
            "query": "0",
            "oper": ">",
            "page": str(pagina),
            "rp": str(REGISTROS_POR_PAGINA),
            "sortname": "id",
            "sortorder": "asc",
        }
        status_code, corpo = cliente.listar(TABELA, payload)
        if status_code is None or not (200 <= status_code < 300) or not isinstance(corpo, dict):
            raise RuntimeError(f"Falha ao consultar {TABELA} no IXC: HTTP {status_code} - {corpo}")

        registros = corpo.get("registros") or []
        if not registros:
            break

        total_lido += len(registros)
        servicos_ativos.extend(registro for registro in registros if _esta_ativo(registro))
        print(f"Pagina {pagina}: {len(registros)} lidos, {total_lido} no total, {len(servicos_ativos)} ativos ate agora.")

        if len(registros) < REGISTROS_POR_PAGINA:
            break
        pagina += 1

    return servicos_ativos


def gerar_planilha(servicos):
    dataframe = pd.DataFrame(servicos)
    with pd.ExcelWriter(ARQUIVO_SAIDA, engine="xlsxwriter") as writer:
        dataframe.to_excel(writer, sheet_name="Servicos Ativos", index=False)
        worksheet = writer.sheets["Servicos Ativos"]
        for col_num, coluna in enumerate(dataframe.columns):
            serie = dataframe[coluna].fillna("").astype(str) if not dataframe.empty else pd.Series([coluna])
            largura = max(len(str(coluna)), serie.map(len).max())
            worksheet.set_column(col_num, col_num, min(max(largura + 2, 14), 60))


if __name__ == "__main__":
    servicos = buscar_servicos_ativos()
    print(f"Total de servicos ativos encontrados: {len(servicos)}")
    gerar_planilha(servicos)
    print(f"Planilha gerada em: {ARQUIVO_SAIDA}")
