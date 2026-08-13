# Indice da documentacao

Porta de entrada dos documentos do projeto. Atualizado em 2026-07-29, quando a
documentacao foi consolidada e as pastas de sprints, change requests e manuais
de uso foram removidas.

## Por onde comecar

Quem chega ao projeto le nesta ordem:

1. [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md) — o que o produto e e para quem;
2. `diagrams/contexto-sistema.html` — o sistema e os externos, numa tela so;
3. `diagrams/ciclo-vida-cotacao.html` — o processo de negocio;
4. [ARCHITECTURE.md](ARCHITECTURE.md) — as decisoes tecnicas consolidadas.

## Documentos

| Documento | Conteudo |
|---|---|
| [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md) | Visao do produto, objetivo, publico e escopo |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Decisoes arquiteturais consolidadas: dominio, camadas, estrutura alvo, ciclo de vida da cotacao, catalogo de automacoes e indice dos diagramas |
| [business_rules.md](business_rules.md) | Regras de negocio rastreaveis (`RN-XXX`) |
| [BACKLOG.md](BACKLOG.md) | Somente o que esta aberto: planejado, em execucao, aguardando QA |
| [BACKLOG_ARCHIVE.md](BACKLOG_ARCHIVE.md) | Historico das features concluidas (aprovadas pelo QA) e das descontinuadas (fechadas sem execucao) |
| [CURRENT_STATUS.md](CURRENT_STATUS.md) | Leitura de status do projeto |
| `adr/` | Uma decisao arquitetural por arquivo, com contexto, alternativas e consequencias |
| `diagrams/` | Conjunto numerado de diagramas (ordem de leitura abaixo) |
| `devops/` | Infraestrutura e containers |
| `modules/` | README por modulo do sistema |

## Decisoes arquiteturais (ADR)

| ADR | Decisao |
|---|---|
| [ADR-001](adr/ADR-001_AUTENTICACAO_API_PUBLICA_JWT_CONTAS_TECNICAS.md) | Autenticacao da API publica com JWT e contas tecnicas |
| [ADR-002](adr/ADR-002_RESOLUCAO_OS_ATENDIMENTO_SEM_FINALIZAR_IXC.md) | Resolucao de O.S. de atendimento sem finalizar no IXC |
| [ADR-003](adr/ADR-003_RESOLUCAO_OS_ATENDIMENTO_EM_LOTE_COM_ANEXO_CONDICIONAL.md) | Resolucao de O.S. em lote com anexo condicional |
| [ADR-004](adr/ADR-004_FECHAMENTO_OS_EM_LOOP_ATE_ESGOTAR.md) | Fechamento de O.S. em loop ate esgotar |
| [ADR-005](adr/ADR-005_MONOLITO_MODULAR_EM_CAMADAS.md) | Evolucao para monolito modular em camadas |
| [ADR-006](adr/ADR-006_EXPANSAO_MODULAR_MODULO_2.md) | Expansao modular: Modulo 2, kill switch e padrao de fila para o IXC |
| [ADR-007](adr/ADR-007_ESTRUTURA_ALVO_DO_REPOSITORIO.md) | Estrutura alvo do repositorio: namespace unico, camada de integracao e ordem de camada entre apps |

## Diagramas — ordem de leitura

Conjunto complementar, do negocio para o tecnico. Servidos tambem pelo portal
`/docs/` do proprio sistema. A tabela completa, com o publico de cada um, esta
na secao "Conjunto de diagramas e ordem de leitura" do `ARCHITECTURE.md`.

| # | Diagrama | Pergunta que responde |
|---|---|---|
| `01` | Contexto do sistema | Quem usa e com quais sistemas externos falamos? |
| `02` | Ciclo de vida da cotacao | Qual e o processo de negocio? |
| `03` | Modelo de dominio | Quais entidades existem e como se relacionam? |
| `04` | Arquitetura-alvo | Como o sistema se organiza por dentro? |
| `05` | Modulos e dependencias | Quais apps existem e quem chama quem? |
| `06` | Arquitetura do Modulo 1 | Como os dados entram, saem e se recuperam de falha? |
| `07` | Processos de automacoes e rotinas | O que roda, quando e por qual caminho? |
| `ANEXO A` | Integration Hub conceitual | Por que **nao** adotamos um hub generico? |

## Removido em 2026-07-29

- `sprints/` — historico de duas sprints encerradas, superado pelo backlog;
- `change_requests/` — continha apenas o `CR-001` (API publica), ja absorvido
  pelas ADR-001 e ADR-005;
- `manuais/` — tres guias de uso das automacoes de Backoffice (abertura de
  atendimento, cadastro de clientes, criacao de logins IXC), removidos por
  decisao do dono do produto. Recuperaveis pelo historico do git se voltarem a
  ser necessarios.
