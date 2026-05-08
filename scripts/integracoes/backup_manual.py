import os
import sys
import traceback
import zipfile
import subprocess
from datetime import timedelta
from pathlib import Path


DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(DIRETORIO_ATUAL))

if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

APPS_DIR = os.path.join(BASE_DIR, 'apps')
if APPS_DIR not in sys.path:
    sys.path.insert(0, APPS_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model

from clientes.models import HistoricoSincronizacao
from clientes.sync_utils import descrever_rotina_em_execucao, iniciar_historico_com_trava


BACKUP_EXCLUDED_DIRS = {
    "backups",
    "temp_google",
    "importacoes_leads",
    "__pycache__",
}


def _resolver_usuario_executor():
    if 'manual' not in sys.argv:
        return None, 'automatica'

    origem = 'manual'
    username = None
    if len(sys.argv) >= 3:
        username = (sys.argv[2] or '').strip()

    User = get_user_model()
    if username:
        user = User.objects.filter(username=username).first()
        if user:
            return user, origem

    return User.objects.filter(is_superuser=True).first(), origem


def _gerar_dump_sql(sql_path):
    db_conf = settings.DATABASES["default"]
    host = db_conf.get("HOST") or "localhost"
    port = str(db_conf.get("PORT") or 3306)
    db_name = db_conf.get("NAME")
    user = (
        os.getenv("DB_ADMIN_USER")
        or db_conf.get("USER")
        or os.getenv("DB_USER")
        or "root"
    )
    password = (
        os.getenv("DB_ADMIN_PASSWORD")
        or db_conf.get("PASSWORD")
        or os.getenv("DB_PASSWORD")
        or os.getenv("MYSQL_ROOT_PASSWORD", "")
    )

    env = os.environ.copy()
    env["MYSQL_PWD"] = password

    cmd = [
        "mysqldump",
        "-h",
        host,
        "-P",
        port,
        "-u",
        user,
        "--no-tablespaces",
        db_name,
    ]

    with open(sql_path, "w", encoding="utf-8") as saida:
        resultado = subprocess.run(
            cmd,
            check=True,
            stdout=saida,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

    if not Path(sql_path).exists() or Path(sql_path).stat().st_size == 0:
        detalhe = (resultado.stderr or "").strip() or "mysqldump retornou sem conteudo."
        raise RuntimeError(f"O dump SQL foi gerado vazio. Detalhe: {detalhe}")


def _zipar_arquivos(sql_path, zip_path, media_dir):
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(sql_path, arcname=f"tmp/{Path(sql_path).name}")
        if media_dir.exists():
            for file_path in media_dir.rglob("*"):
                if file_path.is_file():
                    partes = set(file_path.relative_to(media_dir).parts)
                    if partes & BACKUP_EXCLUDED_DIRS:
                        continue
                    arc_name = Path("app") / "media" / file_path.relative_to(media_dir)
                    zipf.write(file_path, arcname=str(arc_name))


def _copiar_para_windows_se_disponivel(zip_path):
    subdir = (os.getenv("BACKUP_WINDOWS_SUBDIR") or "").strip()
    retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "10") or "10")
    destino_base = Path("/mnt/windows")
    if not destino_base.exists() or not subdir:
        return None

    destino = destino_base / subdir
    destino.mkdir(parents=True, exist_ok=True)
    destino_arquivo = destino / Path(zip_path).name
    subprocess.run(["cp", str(zip_path), str(destino_arquivo)], check=True)

    limite = timezone.now() - timedelta(days=retention_days)
    for arquivo in destino.glob("backup_speed_*.zip"):
        mtime = timezone.datetime.fromtimestamp(arquivo.stat().st_mtime, tz=timezone.get_current_timezone())
        if mtime < limite:
            try:
                arquivo.unlink()
            except Exception:
                pass
    return str(destino_arquivo)


def executar_backup():
    timestamp = timezone.now().strftime("%Y-%m-%d_%H-%M")
    tmp_dir = Path("/tmp/backups_speed")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    sql_path = tmp_dir / f"banco_{timestamp}.sql"
    media_dir = Path(settings.BASE_DIR) / "media"
    backup_dir = media_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    zip_path = backup_dir / f"backup_speed_{timestamp}.zip"

    _gerar_dump_sql(str(sql_path))
    _zipar_arquivos(str(sql_path), str(zip_path), media_dir)

    if not zip_path.exists() or zip_path.stat().st_size == 0:
        raise RuntimeError("O arquivo de backup ZIP foi gerado vazio.")

    try:
        sql_path.unlink(missing_ok=True)
    except Exception:
        pass

    destino_windows = _copiar_para_windows_se_disponivel(str(zip_path))
    return str(zip_path), destino_windows


if __name__ == "__main__":
    usuario_executor, origem = _resolver_usuario_executor()

    historico, rotina_ativa = iniciar_historico_com_trava(
        tipo="backup",
        origem=origem,
        executado_por=usuario_executor,
    )
    if rotina_ativa:
        print(descrever_rotina_em_execucao("backup", rotina_ativa))
        raise SystemExit(0)

    try:
        zip_local, zip_windows = executar_backup()
        historico.status = "sucesso"
        historico.registros_processados = 1
        detalhes = [f"Backup gerado em: {zip_local}"]
        if zip_windows:
            detalhes.append(f"Copia enviada para: {zip_windows}")
        else:
            detalhes.append("Copia em compartilhamento Windows nao realizada neste ambiente.")
        historico.detalhes = " | ".join(detalhes)
        print(historico.detalhes)
    except Exception:
        historico.status = "erro"
        historico.detalhes = traceback.format_exc()
        print("Erro ao executar backup manual.")
        print(historico.detalhes)
    finally:
        historico.data_fim = timezone.now()
        historico.save()
