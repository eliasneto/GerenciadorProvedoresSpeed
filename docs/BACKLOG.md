# Backlog

## Visao geral

Este backlog cobre a iniciativa de organizacao documental e preparacao da API publica v1.

Status utilizados neste documento:

- `Planejada`
- `Pronta para sprint`
- `Em execucao`
- `Bloqueada`
- `Concluida`

## Epic 1 - Fundacao documental do produto

### PO-001 - Criar base documental do projeto

Status: `Concluida`

Objetivo:
Criar a estrutura inicial de documentacao para servir como ponto de entrada do projeto.

Entregas:
- indice geral;
- brief do produto;
- status atual;
- backlog;
- roadmap;
- sprint inicial.

### PO-002 - Catalogar modulos existentes

Status: `Concluida`

Objetivo:
Registrar os modulos atuais e suas responsabilidades funcionais iniciais.

Entregas:
- README por modulo atual;
- identificacao do modulo planejado para API/integracoes.

### PO-003 - Completar regras, fluxos e contratos por modulo

Status: `Planejada`

Objetivo:
Detalhar regras de negocio, fluxos e contratos dos modulos com profundidade suficiente para manutencao e suporte.

Criterios de aceite:
- cada modulo ter regras rastreaveis;
- contratos principais documentados;
- fluxos criticos descritos em portugues do Brasil.

Proximo agente recomendado:
- `docs_writer`
- apoio de `product_owner_requirements`

## Epic 2 - Fronteira de API publica

### PO-004 - Definir escopo da API publica v1

Status: `Pronta para sprint`

Objetivo:
Definir quais recursos entram na primeira versao da API.

Escopo inicial proposto:
- clientes;
- enderecos;
- parceiros;
- propostas;
- healthcheck.

Criterios de aceite:
- recursos v1 priorizados;
- operacoes iniciais definidas;
- exclusoes explicitas fora do escopo v1.

### PO-005 - Definir padrao de versionamento e publicacao

Status: `Pronta para sprint`

Objetivo:
Garantir que a API nasca com fronteira estavel.

Diretrizes de produto:
- prefixo `/api/v1/`;
- Swagger acessivel em ambiente interno/homologacao;
- rotas internas HTML nao entram no contrato publico.

### PO-006 - Criar modulo dedicado para API/integracoes

Status: `Concluida`

Objetivo:
Centralizar a exposicao externa da aplicacao em uma camada separada dos modulos web internos.

Criterios de aceite:
- modulo novo criado;
- namespace de URL proprio;
- responsabilidade documentada.

Agente executor:
- `backend_django`

Observacao:
- implementado na Sprint 001 com app dedicado `integracoes_api` e namespace `/api/v1/`.

## Epic 3 - Swagger e contratos externos

### PO-007 - Habilitar OpenAPI/Swagger

Status: `Concluida`

Objetivo:
Disponibilizar documentacao navegavel das rotas publicas da API.

Criterios de aceite:
- schema OpenAPI gerado;
- interface Swagger acessivel;
- apenas endpoints publicos versionados documentados.

Dependencia:
- PO-006

Agente executor:
- `backend_django`

Observacao:
- schema OpenAPI e tela Swagger publicados para a camada publica da API.

### PO-008 - Publicar endpoints de leitura de clientes e enderecos

Status: `Concluida`

Objetivo:
Entregar primeiro conjunto de integracao util para consulta externa.

Escopo minimo:
- listar clientes;
- detalhar cliente;
- listar enderecos de um cliente.

Observacao:
- implementado em `/api/v1/clientes/`, `/api/v1/clientes/<id>/` e `/api/v1/clientes/<cliente_pk>/enderecos/`.

### PO-009 - Publicar endpoints de leitura de parceiros e propostas

Status: `Concluida`

Objetivo:
Entregar visibilidade externa controlada do funil operacional.

Escopo minimo:
- listar parceiros;
- listar propostas;
- detalhar proposta.

Observacao:
- implementado em `/api/v1/parceiros/`, `/api/v1/propostas/` e `/api/v1/propostas/<id>/`.

### PO-010 - Definir autenticacao da API

Status: `Planejada`

Objetivo:
Definir modelo de acesso seguro para integracoes externas.

Observacao:
Nao bloquear a fundacao da API e do Swagger em ambiente interno, mas deve anteceder publicacao externa produtiva.

Agentes recomendados:
- `software_architect`
- `backend_django`

Observacao arquitetural:
- decisao recomendada: JWT com contas tecnicas reutilizando `core.User` e grupo `api_integracao_publica`.

## Epic 4 - Organizacao interna para suporte

### PO-011 - Separar logica reutilizavel de views extensas

Status: `Planejada`

Objetivo:
Reduzir acoplamento entre tela web, resposta JSON e integracoes.

Observacao:
Esta tarefa deve ser fatiada pelo `software_architect` e executada pelo `backend_django`.

### PO-012 - Consolidar mapa de integracoes existentes

Status: `Planejada`

Objetivo:
Documentar entradas, saidas, dependencia de scripts e efeitos colaterais das integracoes atuais.

Agentes recomendados:
- `product_owner_requirements`
- `docs_writer`

## Ordem de prioridade sugerida

1. PO-004
2. PO-005
3. PO-006
4. PO-007
5. PO-008
6. PO-009
7. PO-010
8. PO-011
9. PO-012
