from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import LoginAuditoria


def _extrair_ip(request):
    if request is None:
        return ""

    forwarded_for = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return (request.META.get("REMOTE_ADDR") or "").strip()


def _extrair_user_agent(request):
    if request is None:
        return ""
    return (request.META.get("HTTP_USER_AGENT") or "")[:500]


def _extrair_username(credentials):
    if not isinstance(credentials, dict):
        return ""

    for chave in ("username", "email", "login"):
        valor = str(credentials.get(chave) or "").strip()
        if valor:
            return valor[:150]
    return ""


@receiver(user_logged_in)
def auditar_login_sucesso(sender, request, user, **kwargs):
    LoginAuditoria.objects.create(
        usuario=user,
        username_informado=(getattr(user, "username", "") or "")[:150],
        acao="login_sucesso",
        sucesso=True,
        endereco_ip=_extrair_ip(request) or None,
        user_agent=_extrair_user_agent(request),
    )


@receiver(user_logged_out)
def auditar_logout(sender, request, user, **kwargs):
    username = ""
    if user is not None:
        username = (getattr(user, "username", "") or "")[:150]

    LoginAuditoria.objects.create(
        usuario=user if getattr(user, "pk", None) else None,
        username_informado=username,
        acao="logout",
        sucesso=True,
        endereco_ip=_extrair_ip(request) or None,
        user_agent=_extrair_user_agent(request),
    )


@receiver(user_login_failed)
def auditar_login_falha(sender, credentials, request, **kwargs):
    LoginAuditoria.objects.create(
        username_informado=_extrair_username(credentials),
        acao="login_falha",
        sucesso=False,
        endereco_ip=_extrair_ip(request) or None,
        user_agent=_extrair_user_agent(request),
        detalhes="Credenciais invalidas ou acesso recusado pelo backend de autenticacao.",
    )
