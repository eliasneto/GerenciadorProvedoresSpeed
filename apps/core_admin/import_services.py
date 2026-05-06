import os
import signal
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
IMPORT_STATUS_STOPPED = "interrompida"
IMPORT_PROGRESS_SAVE_EVERY = 25
TEXT_EMPTY_MARKERS = {"", "NAN", "NONE", "NAT"}

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


class ImportacaoInterrompida(Exception):
    pass


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
    valor = row.get(key, default)

    if valor is None or pd.isna(valor):
        return default

    valor_limpo = str(valor).strip()
    if valor_limpo.upper() in TEXT_EMPTY_MARKERS:
        return default

    return valor_limpo


def _normalizar_chave_texto(valor):
    return str(valor or "").strip().casefold()


def _atualizar_instancia_se_houver_mudanca(instancia, dados):
    changed_fields = []

    for campo, valor in dados.items():
        if getattr(instancia, campo) != valor:
            setattr(instancia, campo, valor)
            changed_fields.append(campo)

    return changed_fields


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


def _obter_ou_criar_empresa(dados_empresa, dados_endereco=None, cache=None):
    cache = cache or {}
    empresas_por_cnpj = cache.setdefault("empresas_por_cnpj", {})
    empresas_por_razao_email = cache.setdefault("empresas_por_razao_email", {})
    empresas_por_razao_telefone = cache.setdefault("empresas_por_razao_telefone", {})

    cnpj_cpf = dados_empresa["cnpj_cpf"]
    razao_social = dados_empresa["razao_social"]
    email = dados_empresa["email"]
    telefone = dados_empresa["telefone"]

    empresa = None
    cnpj_key = _normalizar_chave_texto(cnpj_cpf)
    razao_email_key = (_normalizar_chave_texto(razao_social), _normalizar_chave_texto(email))
    razao_telefone_key = (_normalizar_chave_texto(razao_social), _normalizar_chave_texto(telefone))

    if cnpj_key:
        empresa = empresas_por_cnpj.get(cnpj_key)

    if empresa is None and razao_social and email:
        empresa = empresas_por_razao_email.get(razao_email_key)

    if empresa is None and razao_social and telefone:
        empresa = empresas_por_razao_telefone.get(razao_telefone_key)

    if empresa is None and dados_endereco:
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
        changed_fields = _atualizar_instancia_se_houver_mudanca(empresa, dados_empresa)
        if changed_fields:
            empresa.save(update_fields=changed_fields)
        created = False

    if cnpj_key:
        empresas_por_cnpj[cnpj_key] = empresa
    if razao_social and email:
        empresas_por_razao_email[razao_email_key] = empresa
    if razao_social and telefone:
        empresas_por_razao_telefone[razao_telefone_key] = empresa

    return empresa, created


def _obter_ou_criar_endereco(empresa, dados_endereco, cache=None):
    cache = cache or {}
    enderecos_por_chave = cache.setdefault("enderecos_por_chave", {})

    endereco_key = (
        empresa.pk,
        _normalizar_chave_texto(dados_endereco["endereco"]),
        _normalizar_chave_texto(dados_endereco["numero"]),
        _normalizar_chave_texto(dados_endereco["bairro"]),
        _normalizar_chave_texto(dados_endereco["cidade"]),
        _normalizar_chave_texto(dados_endereco["estado"]),
        _normalizar_chave_texto(dados_endereco["cep"]),
    )

    endereco = enderecos_por_chave.get(endereco_key)
    if endereco is not None:
        return endereco, False

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
        changed_fields = _atualizar_instancia_se_houver_mudanca(endereco, dados_endereco)
        if endereco.empresa_id != empresa.id:
            endereco.empresa = empresa
            changed_fields.append("empresa")
        if changed_fields:
            endereco.save(update_fields=changed_fields)
        created = False

    enderecos_por_chave[endereco_key] = endereco

    return endereco, created


def _obter_ou_criar_lead_espelho(empresa, endereco, dados_lead, cache=None):
    cache = cache or {}
    leads_por_endereco = cache.setdefault("leads_por_endereco", {})

    lead = leads_por_endereco.get(endereco.pk)
    if lead is None:
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
        changed_fields = _atualizar_instancia_se_houver_mudanca(lead, dados_lead)
        if changed_fields:
            lead.save(update_fields=changed_fields)
        created = False

    leads_por_endereco[endereco.pk] = lead

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


def solicitar_interrupcao_importacao(audit):
    payload = dict(audit.detalhes_json or {})
    payload["stop_requested"] = True
    payload["mensagem"] = "Solicitacao de interrupcao enviada. Aguarde alguns segundos."
    payload["atualizado_em"] = timezone.now().isoformat()
    audit.detalhes_json = payload
    audit.save(update_fields=["detalhes_json"])

    worker_pid = payload.get("worker_pid")
    if worker_pid:
        try:
            os.kill(int(worker_pid), signal.SIGTERM)
        except (OSError, ValueError, TypeError):
            pass

    return audit


def _interrupcao_solicitada(audit):
    audit.refresh_from_db(fields=["detalhes_json"])
    return bool((audit.detalhes_json or {}).get("stop_requested"))


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
        df = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    else:
        df = pd.read_excel(caminho, dtype=str, keep_default_na=False)
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
    cache_importacao = {}
    ultima_linha_processada = 0
    signal_anterior = None

    def _handler_sigterm(_signum, _frame):
        raise ImportacaoInterrompida("Importacao interrompida manualmente.")

    try:
        signal_anterior = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGTERM, _handler_sigterm)

        atualizar_auditoria_importacao(
            audit,
            status_execucao=IMPORT_STATUS_RUNNING,
            mensagem="Lendo planilha e preparando importacao.",
            worker_pid=os.getpid(),
            stop_requested=False,
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
            ultima_linha_processada = indice

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
                    empresa, empresa_created = _obter_ou_criar_empresa(
                        dados_empresa,
                        dados_endereco=dados_endereco,
                        cache=cache_importacao,
                    )
                    endereco, endereco_created = _obter_ou_criar_endereco(
                        empresa,
                        dados_endereco,
                        cache=cache_importacao,
                    )

                    dados_lead = {
                        **dados_empresa,
                        **dados_endereco,
                        "empresa_estruturada": empresa,
                        "endereco_estruturado": endereco,
                    }

                    _, lead_created = _obter_ou_criar_lead_espelho(
                        empresa,
                        endereco,
                        dados_lead,
                        cache=cache_importacao,
                    )

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
                if _interrupcao_solicitada(audit):
                    raise ImportacaoInterrompida("Importacao interrompida manualmente.")

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
    except ImportacaoInterrompida as exc:
        processadas = min(ultima_linha_processada, audit.detalhes_json.get("processadas") or ultima_linha_processada)
        audit.total_registros = processadas
        audit.total_sucessos = max(0, processadas - ignorados)
        audit.total_erros = 0
        audit.arquivo_nome = audit.arquivo_nome or arquivo_path.name
        audit.detalhes_json = {
            **(audit.detalhes_json or {}),
            "status_execucao": IMPORT_STATUS_STOPPED,
            "mensagem": str(exc),
            "arquivo_nome": audit.arquivo_nome or arquivo_path.name,
            "arquivo_caminho": str(arquivo_path),
            "processadas": processadas,
            "total_previsto": audit.detalhes_json.get("total_previsto") or processadas,
            "ignorados": ignorados,
            "empresas_novas": empresas_novas,
            "empresas_atualizadas": empresas_atualizadas,
            "enderecos_novos": enderecos_novos,
            "enderecos_atualizados": enderecos_atualizados,
            "leads_novos": leads_novos,
            "leads_atualizados": leads_atualizados,
            "stop_requested": False,
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
        if signal_anterior is not None:
            signal.signal(signal.SIGTERM, signal_anterior)
        try:
            os.remove(arquivo_path)
        except OSError:
            pass
