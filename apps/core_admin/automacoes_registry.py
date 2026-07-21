from django.core.exceptions import PermissionDenied

from .models import AutomacaoMenu

GRUPO_POR_MENU = {
    AutomacaoMenu.MENU_ADMINISTRADOR: "Administrador",
    AutomacaoMenu.MENU_BACKOFFICE: "Backoffice",
    AutomacaoMenu.MENU_LASTMILE: "LastMile",
    AutomacaoMenu.MENU_PARCEIRO: "Parceiro",
}

# Pagina que serve de "container" para cada menu. Administrador e Backoffice
# ja tinham uma pagina propria antes desta feature (import_prospects e
# backoffice:cotacao_import); LastMile e Parceiro nao tinham, por isso usam
# a pagina generica automacoes_area.
MENU_CONTAINER = {
    AutomacaoMenu.MENU_ADMINISTRADOR: ("import_prospects", {}),
    AutomacaoMenu.MENU_BACKOFFICE: ("backoffice:cotacao_import", {}),
    AutomacaoMenu.MENU_LASTMILE: ("automacoes_area", {"menu": AutomacaoMenu.MENU_LASTMILE}),
    AutomacaoMenu.MENU_PARCEIRO: ("automacoes_area", {"menu": AutomacaoMenu.MENU_PARCEIRO}),
}


def usuario_pode_acessar_automacao(user, slug):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    automacao = AutomacaoMenu.objects.filter(slug=slug, ativo=True).first()
    if automacao is None:
        return False

    grupo_exigido = GRUPO_POR_MENU.get(automacao.menu)
    return bool(grupo_exigido) and user.groups.filter(name=grupo_exigido).exists()


def automacoes_do_menu(menu):
    return AutomacaoMenu.objects.filter(menu=menu, ativo=True).order_by("ordem", "nome_exibicao")


def permissao_automacao(slug):
    def checagem(user):
        if usuario_pode_acessar_automacao(user, slug):
            return True
        raise PermissionDenied

    return checagem


def redirect_kwargs_pagina_automacao(slug):
    padrao = MENU_CONTAINER[AutomacaoMenu.MENU_ADMINISTRADOR]
    try:
        automacao = AutomacaoMenu.objects.filter(slug=slug, ativo=True).first()
    except Exception:
        return padrao
    if automacao is None:
        return padrao
    return MENU_CONTAINER.get(automacao.menu, padrao)
