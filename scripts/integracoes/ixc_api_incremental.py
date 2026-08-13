import os
import sys


sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402


if __name__ == "__main__":
    dias = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 0
    call_command("ixc_sincronizacao_incremental", manual=("manual" in sys.argv), dias_retroativos=dias)
