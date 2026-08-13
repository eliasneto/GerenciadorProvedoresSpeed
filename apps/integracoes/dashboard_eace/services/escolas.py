from apps.integracoes.dashboard_eace.client import DashboardEACEClient

# Endpoints confirmados em API_EXTERNA.md (raiz do projeto), secao 4.1.
# Somente leitura: nao existe rota de escrita para escolas (dominio
# sincronizado do Jira a cada 30min no DashboardEACE; qualquer alteracao
# deve ser feita la, nao por aqui).
#
# O mapeamento dos campos de EscolaOut para apps.clientes.Cliente/Endereco
# ainda nao foi feito -- falta o schema completo (ver EscolaOut em /docs,
# ou ARQUITETURA_BANCO_DE_DADOS.md secao 7, nenhum dos dois disponivel
# neste repositorio ainda). Estas funcoes retornam o corpo bruto da API.


def listar_escolas(uf=None, status_escola=None, client=None):
    client = client or DashboardEACEClient()
    params = {}
    if uf:
        params["uf"] = uf
    if status_escola:
        params["status_escola"] = status_escola
    return client.get("escolas", params=params)


def buscar_escola_por_jira_key(jira_key, client=None):
    client = client or DashboardEACEClient()
    return client.get(f"escolas/{jira_key}")
