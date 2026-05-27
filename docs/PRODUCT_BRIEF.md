# Product Brief

## Nome da iniciativa

Organizacao documental, modularizacao de integracoes e API publica v1

## Contexto

O sistema cresceu de forma incremental e hoje concentra processos operacionais, cadastros, importacoes, auditoria e integracoes em uma base unica.

Apesar de existir separacao inicial por modulos, a documentacao funcional e tecnica nao foi consolidada, o que dificulta:

- manutencao;
- onboarding;
- suporte;
- rastreabilidade de regras;
- integracao com sistemas externos.

## Objetivo principal

Deixar o sistema:

- organizado por dominios de responsabilidade;
- documentado de forma navegavel;
- mais facil de sustentar e evoluir;
- pronto para integracao com outros sistemas via API documentada.

## Decisao de produto

Seguir com a `Opcao B`:

- manter os modulos de negocio como donos do dominio;
- criar uma camada dedicada para API e integracoes;
- expor apenas rotas publicas versionadas em `/api/v1/`;
- documentar essa camada via OpenAPI/Swagger.

## Problemas que a iniciativa resolve

- ausencia de documentacao central;
- mistura de rotas internas HTML com endpoints JSON dispersos;
- dificuldade de descobrir responsabilidades de cada modulo;
- falta de contrato estavel para integracoes externas;
- alto acoplamento operacional entre telas, scripts e integracoes.

## Fora de escopo nesta fase

- reescrita completa dos modulos atuais;
- redesenho completo do banco;
- alteracao ampla de regra de negocio ja em producao;
- substituicao imediata de todas as rotas internas existentes.

## Resultados esperados

- base documental inicial criada em `docs/`;
- backlog priorizado de organizacao e API;
- sprint inicial pronta para execucao do backend;
- definicao da primeira versao da API publica;
- caminho seguro para evolucao incremental.

## Publico impactado

- time interno de desenvolvimento;
- suporte/operacao;
- integradores externos;
- lideranca responsavel por continuidade do sistema.

## Indicadores de sucesso

- documentacao central disponivel e utilizada como referencia;
- Swagger acessivel em ambiente interno/homologacao;
- primeira versao da API publicada com contratos claros;
- reducao de duvidas operacionais sobre rotas, dominios e responsabilidades;
- menor dependencia de conhecimento informal para manutencao.
