from django.urls import path

from . import views

app_name = "backoffice"

urlpatterns = [
    path("cotacao/importar/", views.cotacao_import, name="cotacao_import"),
    path("cotacao/modelo/", views.download_modelo_cotacao, name="download_modelo"),
    path(
        "relatorios/<int:audit_id>/download/",
        views.download_relatorio_automacao,
        name="download_relatorio_automacao",
    ),
    path(
        "atendimentos/modelo/",
        views.download_modelo_atendimento,
        name="download_modelo_atendimento",
    ),
    path("atendimentos/importar/", views.atendimento_import, name="atendimento_import"),
]
