import logging
from urllib.parse import urlencode

from django.core.exceptions import (
    RequestDataTooBig,
    SuspiciousOperation,
    TooManyFieldsSent,
    TooManyFilesSent,
)
from django.http import UnreadablePostError
from django.http import HttpResponseRedirect
from django.http.multipartparser import MultiPartParserError
from django.utils.datastructures import MultiValueDictKeyError


logger = logging.getLogger(__name__)


class RestoreBackupUploadGuardMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.path.startswith("/ferramentas/restaurar-backup/"):
            logger.warning(
                "Restore backup POST recebido: content_length=%s content_type=%s",
                request.META.get("CONTENT_LENGTH"),
                request.META.get("CONTENT_TYPE"),
            )
        try:
            response = self.get_response(request)
            if (
                request.method == "POST"
                and request.path.startswith("/ferramentas/restaurar-backup/")
                and getattr(response, "status_code", None) == 400
            ):
                logger.warning(
                    "Restore de backup retornou HTTP 400 antes de concluir o processamento."
                )
                params = urlencode(
                    {
                        "restore_error": "1",
                        "restore_error_detail": "O servidor recusou o upload do arquivo antes de concluir o processamento.",
                    }
                )
                return HttpResponseRedirect(f"{request.path}?{params}")
            return response
        except (
            RequestDataTooBig,
            MultiPartParserError,
            SuspiciousOperation,
            MultiValueDictKeyError,
            UnreadablePostError,
            TooManyFieldsSent,
            TooManyFilesSent,
        ) as exc:
            logger.exception("Falha no upload do restore de backup.")
            if request.path.startswith("/ferramentas/restaurar-backup/"):
                params = urlencode(
                    {
                        "restore_error": "1",
                        "restore_error_detail": str(exc)[:300],
                    }
                )
                return HttpResponseRedirect(f"{request.path}?{params}")
            raise
        except Exception as exc:
            if request.path.startswith("/ferramentas/restaurar-backup/"):
                logger.exception(
                    "Falha inesperada no processamento do restore de backup: %s",
                    exc.__class__.__name__,
                )
                params = urlencode(
                    {
                        "restore_error": "1",
                        "restore_error_detail": f"{exc.__class__.__name__}: {str(exc)[:240]}",
                    }
                )
                return HttpResponseRedirect(f"{request.path}?{params}")
            raise
