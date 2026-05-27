# Modulo Core

## Objetivo

Centralizar fundamentos transversais do sistema, incluindo autenticacao, usuario, historico global, telas iniciais e partes de relatorio/gestao.

## Responsabilidades atuais observadas

- autenticacao e sessao;
- home e navegacao principal;
- healthcheck interno;
- historico global;
- parte de relatorios e operacoes comuns.

## Pontos de atencao

- modulo com concentracao alta de responsabilidades;
- possui mistura de tela, resposta JSON e apoio operacional;
- deve permanecer como modulo de base, nao como fronteira de API externa.

## Relacao com a iniciativa atual

Sera fonte de regras e dados para a API, mas nao deve ser a camada publica da integracao.
