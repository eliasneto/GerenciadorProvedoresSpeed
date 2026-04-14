from io import BytesIO
import logging
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
from django.contrib import messages
from django.conf import settings
from django.db import transaction
from django.core.exceptions import RequestDataTooBig, SuspiciousOperation
from django.http import HttpResponse
from django.http.multipartparser import MultiPartParserError
from django.shortcuts import redirect, render
from django.utils.datastructures import MultiValueDictKeyError

from leads.models import Lead, LeadEmpresa, LeadEndereco
from core.views import grupo_Administrador_required
from django.contrib.auth.decorators import login_required, user_passes_test

from .forms import BackupRestoreForm, ExcelUploadForm


logger = logging.getLogger(__name__)


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
    "ENDEREÇO": "ENDERECO",
    "NÚMERO": "NUMERO",
    "MUNICIPIO": "CIDADE",
    "MUNICÍPIO": "CIDADE",
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


def _obter_ou_criar_empresa(dados_empresa):
    cnpj_cpf = dados_empresa["cnpj_cpf"]
    razao_social = dados_empresa["razao_social"]
    email = dados_empresa["email"]
    telefone = dados_empresa["telefone"]

    empresa = None

    if cnpj_cpf:
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


def import_prospects(request):
    form = ExcelUploadForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        arquivo = form.cleaned_data["file"]

        try:
            if arquivo.name.lower().endswith(".csv"):
                df = pd.read_csv(arquivo)
            else:
                df = pd.read_excel(arquivo)

            df = _normalizar_dataframe(df)

            if "RAZAO_SOCIAL" not in df.columns:
                messages.error(
                    request,
                    "A planilha precisa ter pelo menos a coluna RAZAO_SOCIAL.",
                )
                return render(request, "core_admin/import_form.html", {"form": form})

            empresas_novas = 0
            empresas_atualizadas = 0
            enderecos_novos = 0
            enderecos_atualizados = 0
            leads_novos = 0
            leads_atualizados = 0
            ignorados = 0

            with transaction.atomic():
                for _, row in df.iterrows():
                    razao_social = _valor_limpo(row, "RAZAO_SOCIAL")
                    if not razao_social:
                        ignorados += 1
                        continue

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

                    empresa, empresa_created = _obter_ou_criar_empresa(dados_empresa)
                    endereco, endereco_created = _obter_ou_criar_endereco(empresa, dados_endereco)

                    dados_lead = {
                        **dados_empresa,
                        **dados_endereco,
                        "empresa_estruturada": empresa,
                        "endereco_estruturado": endereco,
                    }

                    lead, lead_created = _obter_ou_criar_lead_espelho(empresa, endereco, dados_lead)

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

            messages.success(
                request,
                (
                    "Processamento concluido: "
                    f"{empresas_novas} empresa(s) nova(s), {enderecos_novos} endereco(s) novo(s), "
                    f"{leads_novos} lead(s) espelho novo(s), {ignorados} linha(s) ignorada(s). "
                    f"Atualizados: {empresas_atualizadas} empresa(s), {enderecos_atualizados} endereco(s) e {leads_atualizados} lead(s)."
                ),
            )
            return redirect("lead_list")
        except Exception as exc:
            messages.error(request, f"Erro critico na planilha: {exc}")

    return render(request, "core_admin/import_form.html", {"form": form})


def _is_within_directory(base_dir, target_path):
    base_dir = Path(base_dir).resolve()
    target_path = Path(target_path).resolve()
    try:
        target_path.relative_to(base_dir)
        return True
    except ValueError:
        return False


def _extract_zip_safely(zip_path, target_dir):
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            extracted_path = Path(target_dir) / member.filename
            if not _is_within_directory(target_dir, extracted_path):
                raise ValueError(f"Arquivo inválido dentro do ZIP: {member.filename}")
        archive.extractall(target_dir)


def _find_first_file(root_dir, suffix):
    for path in Path(root_dir).rglob(f"*{suffix}"):
        if path.is_file():
            return path
    return None


def _find_media_dir(root_dir):
    candidates = [path for path in Path(root_dir).rglob("media") if path.is_dir()]
    if candidates:
        return candidates[0]
    return None


@user_passes_test(grupo_Administrador_required)
@login_required
def restore_backup(request):
    try:
        form = BackupRestoreForm(request.POST or None, request.FILES or None)
    except (RequestDataTooBig, MultiPartParserError, SuspiciousOperation, MultiValueDictKeyError) as exc:
        logger.exception("Falha ao ler o upload do backup.")
        messages.error(
            request,
            f"Falha ao receber o arquivo enviado. Verifique o ZIP e tente novamente. Detalhe: {exc}",
        )
        form = BackupRestoreForm()
        return render(request, "core_admin/restore_backup_form.html", {"form": form}, status=200)

    if request.method == "POST" and form.is_valid():
        backup_zip = form.cleaned_data["file"]
        if not backup_zip.name.lower().endswith(".zip"):
            messages.error(request, "Envie um arquivo .zip válido.")
            return render(request, "core_admin/restore_backup_form.html", {"form": form})

        temp_dir = tempfile.mkdtemp(prefix="speed_restore_")
        temp_zip = None

        try:
            temp_zip = Path(temp_dir) / backup_zip.name
            with open(temp_zip, "wb") as handler:
                for chunk in backup_zip.chunks():
                    handler.write(chunk)

            extract_dir = Path(temp_dir) / "extract"
            extract_dir.mkdir(parents=True, exist_ok=True)
            _extract_zip_safely(temp_zip, extract_dir)

            sql_file = _find_first_file(extract_dir, ".sql")
            media_dir = _find_media_dir(extract_dir)

            if sql_file is None:
                messages.error(request, "O ZIP não contém um arquivo .sql de backup.")
                return render(request, "core_admin/restore_backup_form.html", {"form": form})

            db_conf = settings.DATABASES["default"]
            mysql_host = db_conf.get("HOST") or "localhost"
            mysql_port = str(db_conf.get("PORT") or 3306)
            mysql_name = db_conf.get("NAME")
            mysql_user = os.getenv("DB_ADMIN_USER", "root")
            mysql_password = os.getenv("DB_ADMIN_PASSWORD", os.getenv("MYSQL_ROOT_PASSWORD", ""))

            env = os.environ.copy()
            env["MYSQL_PWD"] = mysql_password

            mysql_cmd = [
                "mysql",
                "-h",
                mysql_host,
                "-P",
                mysql_port,
                "-u",
                mysql_user,
                mysql_name,
            ]

            with open(sql_file, "rb") as sql_handler:
                result = subprocess.run(
                    mysql_cmd,
                    stdin=sql_handler,
                    env=env,
                    capture_output=True,
                )

            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Falha ao restaurar o banco.")

            media_restaurado = False
            if media_dir is not None:
                media_root = Path(settings.MEDIA_ROOT)
                media_root.mkdir(parents=True, exist_ok=True)
                for item in media_dir.iterdir():
                    destino = media_root / item.name
                    if item.is_dir():
                        if destino.exists():
                            shutil.rmtree(destino)
                        shutil.copytree(item, destino)
                    else:
                        shutil.copy2(item, destino)
                media_restaurado = True

            messages.success(
                request,
                "Backup restaurado com sucesso. Banco de dados atualizado" + (" e mídia sincronizada." if media_restaurado else "."),
            )
            return redirect("import_prospects")
        except Exception as exc:
            messages.error(request, f"Falha ao restaurar backup: {exc}")
        finally:
            if temp_dir and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    return render(request, "core_admin/restore_backup_form.html", {"form": form})


def download_template(request):
    df = pd.DataFrame(columns=LEAD_IMPORT_COLUMNS)
    df.loc[0] = [
        "00.000.000/0001-00",
        "EMPRESA EXEMPLO LTDA",
        "EXEMPLO TELECOM",
        "https://www.exemplo.com.br",
        "60000-000",
        "RUA EXEMPLO",
        "1500",
        "CENTRO",
        "FORTALEZA",
        "CE",
        "JOAO SILVA",
        "contato@exemplo.com",
        "(85) 99999-9999",
        "exemplo_telecom",
        "https://instagram.com/exemplo_telecom",
    ]
    df.loc[1] = [
        "00.000.000/0001-00",
        "EMPRESA EXEMPLO LTDA",
        "EXEMPLO TELECOM",
        "https://www.exemplo.com.br",
        "60100-000",
        "AVENIDA FILIAL",
        "200",
        "ALDEOTA",
        "FORTALEZA",
        "CE",
        "JOAO SILVA",
        "contato@exemplo.com",
        "(85) 99999-9999",
        "exemplo_telecom",
        "https://instagram.com/exemplo_telecom",
    ]

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Leads")

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = "attachment; filename=modelo_importacao_leads.xlsx"
    return response
