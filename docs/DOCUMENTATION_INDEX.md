# Indice Geral da Documentacao

## Objetivo

Este indice centraliza a documentacao funcional e de planejamento do projeto `gerenciadorProvedores`.

O objetivo desta base documental e:

- facilitar suporte e manutencao;
- dar visibilidade da estrutura atual do sistema;
- preparar o projeto para exposicao de API publica documentada;
- organizar backlog, roadmap e sprint de evolucao.

## Documentos principais

- [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [CURRENT_STATUS.md](CURRENT_STATUS.md)
- [BACKLOG.md](BACKLOG.md)
- [ROADMAP.md](ROADMAP.md)

## Change requests

- [change_requests/CR-001_API_PUBLICA_E_DOCUMENTACAO.md](change_requests/CR-001_API_PUBLICA_E_DOCUMENTACAO.md)

## ADRs

- [adr/ADR-001_AUTENTICACAO_API_PUBLICA_JWT_CONTAS_TECNICAS.md](adr/ADR-001_AUTENTICACAO_API_PUBLICA_JWT_CONTAS_TECNICAS.md)

## Sprints

- [sprints/SPRINT_001_API_PUBLICA_E_DOCUMENTACAO.md](sprints/SPRINT_001_API_PUBLICA_E_DOCUMENTACAO.md)
- [sprints/SPRINT_002_AUTENTICACAO_API_JWT_CONTAS_TECNICAS.md](sprints/SPRINT_002_AUTENTICACAO_API_JWT_CONTAS_TECNICAS.md)

## Modulos atuais

- [modules/core/README.md](modules/core/README.md)
- [modules/leads/README.md](modules/leads/README.md)
- [modules/partners/README.md](modules/partners/README.md)
- [modules/clientes/README.md](modules/clientes/README.md)
- [modules/auditoria/README.md](modules/auditoria/README.md)
- [modules/core_admin/README.md](modules/core_admin/README.md)
- [modules/backoffice/README.md](modules/backoffice/README.md)

## Modulo planejado

- [modules/integracoes_api/README.md](modules/integracoes_api/README.md)

## Observacoes

- Esta documentacao foi iniciada apos decisao de seguir com a Opcao B: criar uma camada dedicada para API e integracoes.
- Decisoes tecnicas detalhadas devem ser consolidadas pelo agente `software_architect`.
- A implementacao dos endpoints e do Swagger deve ser executada pelo agente `backend_django`.
