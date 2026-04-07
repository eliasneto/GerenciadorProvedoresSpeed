import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
GITIGNORE = ROOT / ".gitignore"


def _git_output(*args):
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Falha ao executar comando git.")
    return result.stdout


def verificar_gitignore():
    problemas = []
    if not GITIGNORE.exists():
        return ["Arquivo .gitignore nao encontrado."]

    conteudo = GITIGNORE.read_text(encoding="utf-8", errors="ignore")
    if "*/migrations/0*.py" in conteudo:
        problemas.append("A regra '*/migrations/0*.py' ainda existe no .gitignore e bloqueia migrations.")
    return problemas


def verificar_arquivos_compilados_versionados():
    problemas = []
    arquivos = _git_output("ls-files").splitlines()
    invalidos = [
        arquivo
        for arquivo in arquivos
        if "__pycache__/" in arquivo or arquivo.endswith(".pyc")
    ]
    for arquivo in invalidos:
        problemas.append(f"Arquivo compilado versionado indevidamente: {arquivo}")
    return problemas


def main():
    problemas = []

    try:
        problemas.extend(verificar_gitignore())
        problemas.extend(verificar_arquivos_compilados_versionados())
    except Exception as exc:
        print(f"Falha ao validar o repositorio: {exc}")
        return 1

    if problemas:
        print("Repositorio reprovado nas validacoes:")
        for problema in problemas:
            print(f"- {problema}")
        return 1

    print("Repositorio validado com sucesso.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
