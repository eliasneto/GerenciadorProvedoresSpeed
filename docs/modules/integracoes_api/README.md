# Modulo Planejado - Integracoes API

## Objetivo

Ser a fronteira oficial de integracao do sistema com consumidores externos e internos que necessitem contrato estavel de API.

## Missao

- centralizar a API publica;
- separar rotas externas das rotas HTML internas;
- concentrar versionamento;
- concentrar schema OpenAPI/Swagger;
- reduzir acoplamento entre telas e integracoes.

## Escopo inicial proposto

- namespace `/api/v1/`;
- healthcheck da API;
- consulta de clientes;
- consulta de enderecos por cliente;
- consulta de parceiros;
- consulta de propostas.

## Nao deve fazer

- assumir regras de negocio de todos os modulos;
- substituir telas internas;
- incorporar toda a logica operacional existente de uma vez;
- publicar rotas sem contrato claro.

## Dependencias

- decisao tecnica final do `software_architect`;
- implementacao pelo `backend_django`;
- testes pelo `qa_tests`.

## Seguranca planejada

- autenticacao JWT para rotas de negocio;
- uso de contas tecnicas;
- Swagger e schema restritos fora do contexto interno.

## Status

`Implementado na Sprint 001`
