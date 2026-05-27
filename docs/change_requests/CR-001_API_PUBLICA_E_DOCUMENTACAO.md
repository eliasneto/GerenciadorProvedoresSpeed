# CR-001 - API publica e documentacao estruturada

## Solicitante

Produto

## Motivo da mudanca

O sistema cresceu sem uma base documental consolidada e sem uma fronteira clara para integracoes externas.

Isso passou a gerar risco de:

- baixa rastreabilidade;
- dificuldade de manutencao;
- dependencia de conhecimento informal;
- retrabalho para integracoes futuras.

## Decisao aprovada

Adotar a `Opcao B`:

- manter os modulos atuais como donos do dominio;
- criar uma camada dedicada para API/integracoes;
- expor contratos publicos apenas em `/api/v1/`;
- documentar essa camada com Swagger/OpenAPI.

## Resultado esperado

- documentacao navegavel do projeto;
- backlog priorizado de reorganizacao;
- primeira versao da API pronta para consulta externa;
- menor acoplamento entre interface web interna e integracoes.

## Impacto esperado

### Positivo

- suporte facilitado;
- onboarding mais rapido;
- integracao externa previsivel;
- melhor governanca de evolucao.

### Risco

- necessidade de revisao de responsabilidades entre modulos;
- definicao de autenticacao da API antes de publicacao externa;
- possivel refatoracao gradual de views extensas.

## Dependencias

- validacao arquitetural detalhada do modulo novo;
- execucao pelo `backend_django`;
- testes contratuais pelo `qa_tests`.

## Observacao

Este change request nao autoriza mudanca de regra de negocio por si so.
As regras atuais devem ser preservadas, salvo decisao especifica posterior.
