# ADR-001 - Autenticacao da API publica com JWT e contas tecnicas

## Status

`Aprovado`

## Contexto

A Sprint 001 criou a fundacao da API publica e do Swagger, mas deixou a camada de integracao aberta para acelerar validacao inicial.

Para uso real com sistemas externos, isso nao e aceitavel porque:

- qualquer consumidor acessa dados sem credencial;
- o schema fica publicamente navegavel;
- nao existe separacao entre consumo humano e consumo tecnico.

## Decisao

Adotar autenticacao da API publica via `JWT`, emitida somente para `contas tecnicas`.

## Decisao detalhada

- reaproveitar `core.User` nesta fase;
- exigir grupo `api_integracao_publica` para emissao e uso do token;
- proteger todas as rotas de negocio da API publica;
- manter apenas a emissao/refresh de token como rotas anonimas;
- restringir Swagger e schema fora de ambiente de desenvolvimento/homologacao.

## Consequencias positivas

- melhora seguranca imediatamente;
- separa usuario humano de integracao;
- mantem baixo custo de implementacao;
- prepara a API para publicacao controlada.

## Consequencias negativas

- adiciona dependencia de JWT no backend;
- exige governanca operacional de contas tecnicas;
- requer novos testes e ajustes de documentacao.

## Alternativas consideradas

### 1. Manter API aberta

Rejeitada por risco de exposicao de dados.

### 2. Usar sessao web ou login do admin

Rejeitada por nao ser adequada para integracao sistema-a-sistema.

### 3. Criar API Key propria nesta fase

Nao escolhida agora.

Motivo:
- JWT com contas tecnicas resolve mais rapido com melhor alinhamento ao DRF;
- API Key continua como opcao futura se houver necessidade de modelo mais simples para parceiros especificos.

## Proxima acao

Implementar a Sprint 002 com o agente `backend_django`.
