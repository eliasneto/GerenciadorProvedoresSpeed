# Sprint 001 - Fundacao da API publica e documentacao

## Objetivo da sprint

Entregar a base tecnica minima para a API publica v1 sem misturar rotas internas HTML com o contrato externo.

## Status

`Concluida`

## Time principal

- `backend_django`

## Apoio recomendado

- `software_architect`
- `qa_tests`

## Itens da sprint

### SP1-001 - Criar modulo dedicado para API/integracoes

Tipo:
estrutura

Resultado esperado:
- app dedicado criado;
- responsabilidade isolada das telas internas;
- ponto unico para exposicao da API publica.

Criterios de aceite:
- modulo novo registrado;
- URLs proprias da API criadas;
- responsabilidade documentada no modulo.

### SP1-002 - Configurar fundacao do DRF

Tipo:
infraestrutura de aplicacao

Resultado esperado:
- DRF ativo no projeto;
- configuracao basica pronta para serializers, views e versionamento.

Criterios de aceite:
- configuracao funcional em ambiente local;
- base pronta para endpoints versionados.

### SP1-003 - Habilitar OpenAPI/Swagger

Tipo:
documentacao de API

Resultado esperado:
- schema OpenAPI gerado;
- tela Swagger acessivel em ambiente interno/homologacao.

Criterios de aceite:
- rota de schema criada;
- rota de Swagger criada;
- documentacao refletindo apenas endpoints publicos da API.

### SP1-004 - Publicar endpoint de healthcheck da API

Tipo:
endpoint

Resultado esperado:
- endpoint simples de validacao operacional da API.

Criterios de aceite:
- retorno padrao e previsivel;
- documentado no Swagger.

### SP1-005 - Publicar leitura de clientes

Tipo:
endpoint

Resultado esperado:
- listagem de clientes;
- detalhe de cliente.

Criterios de aceite:
- filtros basicos documentados, se implementados;
- payload padronizado;
- sem dependencia de template HTML.

### SP1-006 - Publicar leitura de enderecos por cliente

Tipo:
endpoint

Resultado esperado:
- consulta de enderecos associados ao cliente.

Criterios de aceite:
- relacionamento claro no contrato;
- documentado no Swagger.

### SP1-007 - Publicar leitura de parceiros

Tipo:
endpoint

Resultado esperado:
- listagem e consulta basica de parceiros para integracao externa.

Criterios de aceite:
- contrato minimamente util para consulta;
- documentado no Swagger.

### SP1-008 - Publicar leitura de propostas

Tipo:
endpoint

Resultado esperado:
- listagem e detalhe basico de propostas.

Criterios de aceite:
- campos essenciais expostos;
- status e referencias relacionais claros;
- documentado no Swagger.

### SP1-009 - Cobertura minima de testes da API

Tipo:
qualidade

Resultado esperado:
- testes dos endpoints e do schema publico.

Criterios de aceite:
- validacao de status code;
- validacao de contrato basico;
- execucao registrada.

## Fora de escopo da sprint

- escrita de dados por integracoes externas;
- autenticacao definitiva de producao;
- reescrita completa de views antigas;
- migracao total dos endpoints JSON internos espalhados no sistema.

## Definicao de pronto para backend

- backlog priorizado aprovado;
- decisao pela Opcao B registrada;
- escopo da v1 limitado a leitura;
- novos endpoints versionados em `/api/v1/`.
