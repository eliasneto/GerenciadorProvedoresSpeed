# Roadmap

## Objetivo do roadmap

Organizar a evolucao do sistema em fases pequenas, com entrega incremental de documentacao, API e capacidade de suporte.

## Fase 1 - Fundacao documental

Objetivo:
criar a base de organizacao e leitura do projeto.

Entregas:
- estrutura `docs/`;
- backlog inicial;
- sprint inicial;
- catalogo de modulos.

Status:
`Iniciada`

## Fase 2 - Fundacao da API publica

Objetivo:
criar a camada dedicada de API/integracoes e habilitar Swagger.

Entregas:
- modulo dedicado de API;
- namespace `/api/v1/`;
- OpenAPI/Swagger;
- healthcheck publico interno.

Status:
`Planejada`

## Fase 3 - Primeiros recursos integraveis

Objetivo:
publicar os primeiros recursos de consulta externa.

Entregas:
- clientes;
- enderecos;
- parceiros;
- propostas.

Status:
`Planejada`

## Fase 4 - Seguranca e governanca

Objetivo:
garantir acesso controlado e previsibilidade contratual.

Entregas:
- autenticacao da API;
- regras de versionamento;
- politica de erros e codigos de resposta;
- rastreabilidade de consumo.

Status:
`Planejada`

## Fase 5 - Sustentacao e desacoplamento

Objetivo:
melhorar manutenibilidade sem interromper a operacao.

Entregas:
- extracao gradual de logicas de views extensas;
- consolidacao das integracoes existentes;
- documentacao funcional aprofundada por modulo.

Status:
`Planejada`
