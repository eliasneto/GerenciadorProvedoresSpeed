from urllib.parse import urlencode

from django.core.exceptions import RequestDataTooBig, SuspiciousOperation
from django.http import HttpResponseRedirect
from django.http.multipartparser import MultiPartParserError
from django.utils.datastructures import MultiValueDictKeyError


class RestoreBackupUploadGuardMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except (RequestDataTooBig, MultiPartParserError, SuspiciousOperation, MultiValueDictKeyError) as exc:
            if request.path.startswith("/ferramentas/restaurar-backup/"):
                params = urlencode(
                    {
                        "restore_error": "1",
                        "restore_error_detail": str(exc)[:300],
                    }
                )
                return HttpResponseRedirect(f"{request.path}?{params}")
            raise
