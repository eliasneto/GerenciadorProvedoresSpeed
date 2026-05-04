import os
from pathlib import Path

import pandas as pd
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from core.models import IntegrationAudit
from leads.models import Lead, LeadEmpresa, LeadEndereco


IMPORT_INTEGRATION = "importador_leads"
IMPORT_ACTION = "importacao_planilha"
IMPORT_STATUS_RUNNING = "rodando"
IMPORT_STATUS_SUCCESS = "sucesso"
IMPORT_STATUS_ERROR = "erro"
IMPORT_PROGRESS_SAVE_EVERY = 25

LEAD_IMPORT_COLUMNS = [
    "CNPJ_CPF",
    "RAZAO_SOCIAL",
    "NOME_FANTASIA",
    "SITE",
    "CEP",
    "ENDERECO",
    "NUMERO",
    "BAIRRO",
    "CIDADE",
    "ESTADO",
    "CONTATO_NOME",
    "EMAIL",
    "TELEFONE",
    "INSTAGRAM_USERNAME",
    "INSTAGRAM_URL",
]

LEAD_COLUMN_ALIASES = {
    "CNPJ": "CNPJ_CPF",
    "CPF": "CNPJ_CPF",
    "CNPJ/CPF": "CNPJ_CPF",
    "DOCUMENTO": "CNPJ_CPF",
    "RAZAO SOCIAL": "RAZAO_SOCIAL",
    "NOME": "RAZAO_SOCIAL",
    "NOME FANTASIA": "NOME_FANTASIA",
    "FANTASIA": "NOME_FANTASIA",
    "URL": "SITE",
    "SITE_URL": "SITE",
    "ENDERECO_COMPLETO": "ENDERECO",
    "ENDEREÃ‡O": "ENDERECO",
    "NÃšMERO": "NUMERO",
    "MUNICIPIO": "CIDADE",
    "MUNICÃPIO": "CIDADE",
    "UF": "ESTADO",
    "CONTATO": "CONTATO_NOME",
    "CONTATO PRINCIPAL": "CONTATO_NOME",
    "E-MAIL": "EMAIL",
    "MAIL": "EMAIL",
    "CELULAR": "TELEFONE",
    "FONE": "TELEFONE",
    "INSTAGRAM": "INSTAGRAM_URL",
    "INSTAGRAM_USER": "INSTAGRAM_USERNAME",
    "ARROBA_INSTAGRAM": "INSTAGRAM_USERNAME",
}


def _normalizar_coluna(nome):
    return str(nome or "").strip().upper().replace("-", "_").replace(" ", "_")


def _normalizar_dataframe(df):
    colunas = []
    for coluna in df.columns:
        normalizada = _normalizar_coluna(coluna)
        normalizada = LEAD_COLUMN_ALIASES.get(normalizada, normalizada)
        colunas.append(normalizada)
    df.columns = colunas
    return df.fillna("")


def _valor_limpo(row, key, default=""):
    return str(row.get(key, default) or default).strip()


def _buscar_empresa_duplicada_por_endereco(dados_empresa, dados_endereco):
    filtros_endereco = {
        "enderecos__endereco__iexact": dados_endereco["endereco"],
        "enderecos__numero__iexact": dados_endereco["numero"],
        "enderecos__bairro__iexact": dados_endereco["bairro"],
        "enderecos__cidade__iexact": dados_endereco["cidade"],
        "enderecos__estado__iexact": dados_endereco["estado"],
        "enderecos__cep__iexact": dados_endereco["cep"],
    }

    cnpj_cpf = dados_empresa["cnpj_cpf"]
    razao_social = dados_empresa["razao_social"]

    if cnpj_cpf:
        empresa = LeadEmpresa.objects.filter(
            cnpj_cpf__iexact=cnpj_cpf,
            **filtros_endereco,
        ).order_by("id").first()
        if empresa:
            return empresa

    if razao_social:
        empresa = LeadEmpresa.objects.filter(
            razao_social__iexact=razao_social,
            **filtros_endereco,
        ).order_by("id").first()
        if empresa:
            return empresa

    return None


def _obter_ou_criar_empresa(dados_empresa, dados_endereco=None):
    cnpj_cpf = dados_empresa["cnpj_cpf"]
    razao_social = dados_empresa["razao_social"]
    email = dados_empresa["email"]
    telefone = dados_empresa["telefone"]

    empresa = None

    if dados_endereco:
        empresa = _buscar_empresa_duplicada_por_endereco(dados_empresa, dados_endereco)

    if empresa is None and cnpj_cpf:
        empresa = LeadEmpresa.objects.filter(cnpj_cpf=cnpj_cpf).order_by("id").first()

    if empresa is None and razao_social and email:
        empresa = LeadEmpresa.objects.filter(
            razao_social__iexact=razao_social,
            email__iexact=email,
        ).order_by("id").first()

    if empresa is None and razao_social and telefone:
        empresa = LeadEmpresa.objects.filter(
            razao_social__iexact=razao_social,
            telefone=telefone,
        ).order_by("id").first()

    if empresa is None:
        empresa = LeadEmpresa.objects.create(**dados_empresa)
        created = True
    else:
        for campo, valor in dados_empresa.items():
            setattr(empresa, campo, valor)
        empresa.save()
        created = False

    return empresa, created


def _obter_ou_criar_endereco(empresa, dados_endereco):
    endereco = LeadEndereco.objects.filter(
        empresa=empresa,
        endereco=dados_endereco["endereco"],
        numero=dados_endereco["numero"],
        bairro=dados_endereco["bairro"],
        cidade=dados_endereco["cidade"],
        estado=dados_endereco["estado"],
        cep=dados_endereco["cep"],
    ).order_by("id").first()

    if endereco is None:
        endereco = LeadEndereco.objects.create(empresa=empresa, **dados_endereco)
        created = True
    else:
        for campo, valor in dados_endereco.items():
            setattr(endereco, campo, valor)
        endereco.empresa = empresa
        endereco.save()
        created = False

    return endereco, created


def _obter_ou_criar_lead_espelho(empresa, endereco, dados_lead):
    lead = Lead.objects.filter(endereco_estruturado=endereco).order_by("id").first()

    if lead is None:
        lead = Lead.objects.filter(
            empresa_estruturada=empresa,
            endereco__iexact=dados_lead["endereco"],
            numero=dados_lead["numero"],
            bairro__iexact=dados_lead["bairro"],
            cidade__iexact=dados_lead["cidade"],
            estado__iexact=dados_lead["estado"],
            cep=dados_lead["cep"],
        ).order_by("id").first()

    if lead is None:
        lead = Lead.objects.create(**dados_lead)
        created = True
    else:
        for campo, valor in dados_lead.items():
            setattr(lead, campo, valor)
        lead.save()
        created = False

    return lead, created


def buscar_importacao_em_andamento():
    auditorias = IntegrationAudit.objects.filter(
        integration=IMPORT_INTEGRATION,
        action=IMPORT_ACTION,
    ).order_by("-criado_em")[:10]

    for audit in auditorias:
        if (audit.detalhes_json or {}).get("status_execucao") == IMPORT_STATUS_RUNNING:
            return audit
    return None


def buscar_ultima_importacao():
    return (
        IntegrationAudit.objects.filter(
            integration=IMPORT_INTEGRATION,
            action=IMPORT_ACTION,
        )
        .order_by("-criado_em")
        .first()
    )


def criar_auditoria_importacao(*, usuario_id=None, arquivo_nome="", arquivo_caminho=""):
    usuario = None
    if usuario_id:
        usuario = get_user_model().objects.filter(pk=usuario_id).first()

    return IntegrationAudit.objects.create(
        integration=IMPORT_INTEGRATION,
        action=IMPORT_ACTION,
        usuario=usuario,
        arquivo_nome=arquivo_nome or "",
        detalhes_json={
            "status_execucao": IMPORT_STATUS_RUNNING,
            "mensagem": "Importacao em fila para processamento.",
            "arquivo_nome": arquivo_nome or "",
            "arquivo_caminho": arquivo_caminho or "",
            "iniciado_em": timezone.now().isoformat(),
            "atualizado_em": timezone.now().isoformat(),
            "processadas": 0,
            "total_previsto": 0,
        },
    )


def atualizar_auditoria_importacao(audit, **detalhes):
    payload = dict(audit.detalhes_json or {})
    payload.update(detalhes)
    payload["atualizado_em"] = timezone.now().isoformat()
    audit.detalhes_json = payload
    audit.save(update_fields=["detalhes_json"])


def salvar_arquivo_importacao(uploaded_file, media_root):
    destino_dir = Path(media_root) / "importacoes_leads"
    destino_dir.mkdir(parents=True, exist_ok=True)

    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S_%f")
    nome_base = Path(uploaded_file.name).name
    destino = destino_dir / f"{timestamp}_{nome_base}"

    with destino.open("wb") as arquivo_destino:
        for chunk in uploaded_file.chunks():
            arquivo_destino.write(chunk)

    return destino


def carregar_dataframe_importacao(caminho_arquivo):
    caminho = Path(caminho_arquivo)
    if caminho.suffix.lower() == ".csv":
        df = pd.read_csv(caminho)
    else:
        df = pd.read_excel(caminho)
    return _normalizar_dataframe(df)


def processar_importacao_leads(caminho_arquivo, audit_id):
    audit = IntegrationAudit.objects.get(pk=audit_id)
    arquivo_path = Path(caminho_arquivo)

    empresas_novas = 0
    empresas_atualizadas = 0
    enderecos_novos = 0
    enderecos_atualizados = 0
    leads_novos = 0
    leads_atualizados = 0
    ignorados = 0

    try:
        atualizar_auditoria_importacao(
            audit,
            status_execucao=IMPORT_STATUS_RUNNING,
            mensagem="Lendo planilha e preparando importacao.",
        )

        df = carregar_dataframe_importacao(arquivo_path)
        total_linhas = len(df.index)

        if "RAZAO_SOCIAL" not in df.columns:
            raise ValueError("A planilha precisa ter pelo menos a coluna RAZAO_SOCIAL.")

        atualizar_auditoria_importacao(
            audit,
            status_execucao=IMPORT_STATUS_RUNNING,
            mensagem="Planilha carregada. Processando registros.",
            total_previsto=total_linhas,
            processadas=0,
        )

        for indice, row in enumerate(df.to_dict("records"), start=1):
            razao_social = _valor_limpo(row, "RAZAO_SOCIAL")
            if not razao_social:
                ignorados += 1
            else:
                email = _valor_limpo(row, "EMAIL")
                telefone = _valor_limpo(row, "TELEFONE")

                dados_empresa = {
                    "razao_social": razao_social,
                    "cnpj_cpf": _valor_limpo(row, "CNPJ_CPF"),
                    "nome_fantasia": _valor_limpo(row, "NOME_FANTASIA"),
                    "site": _valor_limpo(row, "SITE"),
                    "contato_nome": _valor_limpo(row, "CONTATO_NOME"),
                    "email": email,
                    "telefone": telefone,
                    "instagram_username": _valor_limpo(row, "INSTAGRAM_USERNAME"),
                    "instagram_url": _valor_limpo(row, "INSTAGRAM_URL"),
                    "status": "novo",
                }

                dados_endereco = {
                    "cep": _valor_limpo(row, "CEP"),
                    "endereco": _valor_limpo(row, "ENDERECO"),
                    "numero": _valor_limpo(row, "NUMERO"),
                    "bairro": _valor_limpo(row, "BAIRRO"),
                    "cidade": _valor_limpo(row, "CIDADE"),
                    "estado": _valor_limpo(row, "ESTADO"),
                }

                with transaction.atomic():
                    empresa, empresa_created = _obter_ou_criar_empresa(dados_empresa, dados_endereco=dados_endereco)
                    endereco, endereco_created = _obter_ou_criar_endereco(empresa, dados_endereco)

                    dados_lead = {
                        **dados_empresa,
                        **dados_endereco,
                        "empresa_estruturada": empresa,
                        "endereco_estruturado": endereco,
                    }

                    _, lead_created = _obter_ou_criar_lead_espelho(empresa, endereco, dados_lead)

                if empresa_created:
                    empresas_novas += 1
                else:
                    empresas_atualizadas += 1

                if endereco_created:
                    enderecos_novos += 1
                else:
                    enderecos_atualizados += 1

                if lead_created:
                    leads_novos += 1
                else:
                    leads_atualizados += 1

            if indice == total_linhas or indice % IMPORT_PROGRESS_SAVE_EVERY == 0:
                atualizar_auditoria_importacao(
                    audit,
                    status_execucao=IMPORT_STATUS_RUNNING,
                    mensagem=f"Processando planilha: {indice} de {total_linhas} linha(s).",
                    total_previsto=total_linhas,
                    processadas=indice,
                    ignorados=ignorados,
                )

        resumo = (
            f"Processamento concluido: {empresas_novas} empresa(s) nova(s), "
            f"{enderecos_novos} endereco(s) novo(s), {leads_novos} lead(s) espelho novo(s), "
            f"{ignorados} linha(s) ignorada(s). Atualizados: {empresas_atualizadas} empresa(s), "
            f"{enderecos_atualizados} endereco(s) e {leads_atualizados} lead(s)."
        )

        audit.total_registros = total_linhas
        audit.total_sucessos = max(0, total_linhas - ignorados)
        audit.total_erros = 0
        audit.arquivo_nome = audit.arquivo_nome or arquivo_path.name
        audit.detalhes_json = {
            **(audit.detalhes_json or {}),
            "status_execucao": IMPORT_STATUS_SUCCESS,
            "mensagem": resumo,
            "arquivo_nome": audit.arquivo_nome or arquivo_path.name,
            "arquivo_caminho": str(arquivo_path),
            "processadas": total_linhas,
            "total_previsto": total_linhas,
            "ignorados": ignorados,
            "empresas_novas": empresas_novas,
            "empresas_atualizadas": empresas_atualizadas,
            "enderecos_novos": enderecos_novos,
            "enderecos_atualizados": enderecos_atualizados,
            "leads_novos": leads_novos,
            "leads_atualizados": leads_atualizados,
            "finalizado_em": timezone.now().isoformat(),
            "atualizado_em": timezone.now().isoformat(),
        }
        audit.save(
            update_fields=[
                "arquivo_nome",
                "total_registros",
                "total_sucessos",
                "total_erros",
                "detalhes_json",
            ]
        )
    except Exception as exc:
        audit.total_erros = 1
        audit.detalhes_json = {
            **(audit.detalhes_json or {}),
            "status_execucao": IMPORT_STATUS_ERROR,
            "mensagem": str(exc),
            "arquivo_nome": audit.arquivo_nome or arquivo_path.name,
            "arquivo_caminho": str(arquivo_path),
            "finalizado_em": timezone.now().isoformat(),
            "atualizado_em": timezone.now().isoformat(),
        }
        audit.save(update_fields=["total_erros", "detalhes_json"])
        raise
    finally:
        try:
            os.remove(arquivo_path)
        except OSError:
            pass
