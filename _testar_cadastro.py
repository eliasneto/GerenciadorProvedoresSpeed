"""Script temporário para testar o cadastro das primeiras linhas da planilha."""
import sys
import re
import os

# Forçar UTF-8 no stdout para nomes com caracteres especiais
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from scripts.integracoes.backoffice.cadastrar_cliente_ixc import executar_cadastro_cliente_ixc


def normalizar_df(df):
    df = df.copy()
    df.columns = [
        re.sub(r"\s*\*\s*$", "", str(c).replace("﻿", "").strip())
        for c in df.columns
    ]
    return df


df = normalizar_df(pd.read_excel("Modelo_Cadastro_Clientes_IXC_Lote03.xlsx"))
print(f"Total de linhas: {len(df)}")
print(f"IXC_URL: {os.getenv('IXC_URL', '(default)')}")
print()

from io import BytesIO

df["Status_Importacao"] = ""
df["Mensagem_Importacao"] = ""
df["ID_IXC"] = ""

sucessos = 0
falhas = 0
total = 0

for index, linha in df.iterrows():
    if not (pd.notna(linha.get("Razao_Social")) or pd.notna(linha.get("RAZAO_SOCIAL"))):
        continue

    total += 1
    razao = str(linha.get("Razao_Social") or linha.get("RAZAO_SOCIAL") or "")[:60]

    try:
        status, mensagem, ixc_id = executar_cadastro_cliente_ixc(linha)
    except Exception as exc:
        status, mensagem, ixc_id = False, f"Erro inesperado: {exc}", ""

    if status:
        sucessos += 1
        df.at[index, "Status_Importacao"] = "SUCESSO"
        icone = "OK"
    else:
        falhas += 1
        df.at[index, "Status_Importacao"] = "ERRO"
        icone = "ERRO"

    df.at[index, "Mensagem_Importacao"] = mensagem
    df.at[index, "ID_IXC"] = ixc_id or ""

    print(f"[{total:04d}/{len(df)}] [{icone}] Linha {index+2}: {razao[:50]}")
    if icone == "ERRO":
        print(f"         -> {mensagem}")

print()
print(f"RESULTADO: {total} processados | {sucessos} sucesso | {falhas} erro")

# Gerar relatório Excel
output = BytesIO()
with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
    df.to_excel(writer, index=False, sheet_name="Resultado")
    ws = writer.sheets["Resultado"]
    for col_num, col in enumerate(df.columns):
        ws.set_column(col_num, col_num, 90 if col == "Mensagem_Importacao" else 24)

relatorio = "Relatorio_Cadastro_Clientes_IXC_Lote03.xlsx"
with open(relatorio, "wb") as f:
    f.write(output.getvalue())
print(f"Relatório salvo em: {relatorio}")
