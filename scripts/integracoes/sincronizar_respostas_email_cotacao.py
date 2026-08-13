import os
import sys


sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from apps.integracoes.email.sincronizar_respostas_email_cotacao import main  # noqa: E402


if __name__ == "__main__":
    main()
