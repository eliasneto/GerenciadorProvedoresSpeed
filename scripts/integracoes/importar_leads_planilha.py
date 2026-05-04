import os
import sys
import traceback
from pathlib import Path


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

from core.models import IntegrationAudit
from core_admin.import_services import processar_importacao_leads


def main():
    if len(sys.argv) < 3:
        raise SystemExit("Uso: python scripts/integracoes/importar_leads_planilha.py <audit_id> <arquivo>")

    audit_id = int(sys.argv[1])
    arquivo = Path(sys.argv[2]).resolve()

    processar_importacao_leads(str(arquivo), audit_id)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if len(sys.argv) >= 2 and str(sys.argv[1]).isdigit():
            audit = IntegrationAudit.objects.filter(pk=int(sys.argv[1])).first()
            if audit:
                detalhes = dict(audit.detalhes_json or {})
                detalhes["traceback"] = traceback.format_exc()
                audit.detalhes_json = detalhes
                audit.save(update_fields=["detalhes_json"])
        raise
