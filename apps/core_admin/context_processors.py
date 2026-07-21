from core_admin.models import AutomacaoMenu


def automacoes_realocadas(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}

    automacoes = (
        AutomacaoMenu.objects.filter(ativo=True)
        .exclude(menu=AutomacaoMenu.MENU_ADMINISTRADOR)
        .order_by("menu", "ordem", "nome_exibicao")
    )

    por_menu = {}
    for automacao in automacoes:
        por_menu.setdefault(automacao.menu, []).append(automacao)

    return {"automacoes_por_menu": por_menu}
