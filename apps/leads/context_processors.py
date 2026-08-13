from . import services


def setores_disponiveis(request):
    """PO-052/ADR-016: nomes de Setor cadastrados (RN-025), usados para
    montar o menu "Setores" em toda pagina, sem cada view precisar
    repassar a lista manualmente.

    PO-075/RN-055: lista somente os nomes concedidos ao usuario logado
    (todos, para superusuario) — usuario sem nenhum Setor concedido
    recebe lista vazia e nao ve a secao no menu (mesmo comportamento ja
    aplicado hoje quando a lista de nomes esta vazia)."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}

    return {"nomes_setor_menu": services.nomes_setor_visiveis_para_usuario(user)}
