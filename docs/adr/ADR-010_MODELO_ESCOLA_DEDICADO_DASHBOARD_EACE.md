# ADR-010 - Modelo de dados dedicado para Escola (DashboardEACE), sem mapear para Cliente/Endereco

## Status

`Aprovado`

> **Emenda (2026-08-07):** confirmado contra a API real que `EscolaOut` usa
> o campo `key` (nao `jira_key`) como identificador — corrigido no codigo.
> Campos `inep`, `nome`, `municipio` e `endereco_descricao` (mapeado de
> `descricao`) promovidos de `dados_api` para colunas tipadas, conforme
> esta ADR ja previa ("decisao incremental, nao exige nova ADR"). Ver
> `docs/adr/ADR-011_TELA_ENDERECOS_LASTMILE_PASSA_A_EXIBIR_ESCOLA.md` para
> o motivo (tela de Enderecos Lastmile passou a exibir `Escola`).

## Contexto

A ADR-009 previu que a integração com o DashboardEACE alimentaria os
models já existentes `apps.clientes.Cliente`/`Endereco` (o mesmo destino que
antes era populado pelo IXC, desativado pela ADR-008). O usuário mudou essa
direção: os dados de `GET /escolas` (contrato em `API_EXTERNA.md`) devem
ir para uma **tabela nova, própria**, "começando do zero" — sem tentar
encaixar no modelo `Cliente`/`Endereco` existente. O banco atual não é
apagado nem migrado: continua existindo, disponível para consulta "conforme
a necessidade", mas deixa de ser o destino desta sincronização.

O schema completo de `EscolaOut` (resposta de `/escolas`) ainda não foi
confirmado — pendência já registrada quando o Dev implementou o client
(faltam os campos exatos, hoje só disponíveis no Swagger/`/docs` do
DashboardEACE ou em `ARQUITETURA_BANCO_DE_DADOS.md` §7, nenhum dos dois
acessível deste repositório ainda). Não é aceitável inventar nomes de
campo (CLAUDE.md seção 9) nem esperar indefinidamente para começar a
capturar dados.

## Decisao

Criar um novo app de domínio `apps.escolas` (mesmo padrão de app-por-domínio
já usado por `apps.clientes`, `apps.leads`, `apps.partners` — ADR-005/006),
com um model `Escola` que combina campos tipados (o que já está confirmado
por `API_EXTERNA.md`) com um campo JSON para o restante da resposta da API,
sem perder nenhum dado hoje disponível mesmo sem o schema completo.

## Decisao detalhada

### Model `Escola` (`apps/escolas/models.py`)

| Campo | Tipo | Origem |
|---|---|---|
| `jira_key` | `CharField`, único | confirmado (`GET /escolas/{jira_key}`) |
| `uf` | `CharField`, opcional | confirmado (filtro `?uf=`) |
| `status_escola` | `CharField`, opcional | confirmado (filtro `?status_escola=`) |
| `dados_api` | `JSONField` | payload bruto **completo** retornado pela API para aquela escola — fonte de verdade até o schema de `EscolaOut` ser confirmado |
| `atualizado_em` | `DateTimeField(auto_now=True)` | controle interno, não vem da API |

`dados_api` existe justamente para cumprir "puxar todos os dados da rota"
sem exigir que a gente já saiba o nome de cada campo. Quando o schema de
`EscolaOut` for confirmado, campos relevantes de dentro de `dados_api` podem
ser promovidos a colunas tipadas próprias — decisão incremental, não exige
nova ADR (é reversível e de baixo risco), só uma migration nova.

### Sincronização

- reaproveitar `listar_escolas()` (já implementado em
  `apps/integracoes/dashboard_eace/services/escolas.py`, PO anterior);
- uma função de serviço em `apps/escolas/services.py` que chama
  `listar_escolas()` e grava um `Escola` por item via `update_or_create`
  (chave: `jira_key`), guardando o item inteiro em `dados_api`;
- disparo manual via management command (`python manage.py
  sincronizar_escolas_dashboard_eace`), no mesmo espírito dos demais
  comandos de sincronização do projeto — **sem** agendamento automático
  ainda (isso seria uma decisão própria, tipo ADR-008, não coberta aqui);
- sem testar contra a API real ainda: não há credenciais reais
  configuradas (`DASHBOARD_EACE_URL`/`DASHBOARD_EACE_TOKEN` vazias) — os
  testes usam a API mockada, como já vem sendo feito.

### O que NÃO muda

- `apps.clientes.Cliente`/`Endereco` continuam existindo, intocados;
- RN-017 (abertura de cotação exige endereço) **não foi redecidida** —
  continua referenciando `Cliente`/`Endereco`; se/quando `Escola` deve
  alimentar esse fluxo é decisão futura, fora desta ADR;
- nenhuma migração de dados do banco antigo para o novo — são
  independentes; cruzar os dois, se precisar, é decisão futura.

## Consequências positivas

- Nenhuma invenção de schema: `dados_api` captura tudo que a API já manda
  hoje, mesmo sem o detalhamento completo;
- Simples de evoluir depois (promover campos do JSON para colunas tipadas)
  sem perder histórico nem reprocessar nada;
- Independência total do banco atual reduz risco de regressão em
  `Cliente`/`Endereco` e no que já depende deles (RN-017, `apps/leads`,
  `apps/partners`).

## Consequências negativas / riscos

- Filtrar/consultar por campos que só existem dentro de `dados_api` (JSON)
  é mais lento e menos ergonômico que uma coluna tipada, até serem
  promovidos;
- Sem agendamento automático, a tabela só reflete a API no momento em que
  alguém rodar o comando manualmente — aceitável por ora, dado que ainda
  não há credenciais reais para validar a integração de ponta a ponta.

## Alternativas consideradas

### Mapear direto para Cliente/Endereco (decisão original da ADR-009)

Superada por decisão do usuário: quer come çar do zero, sem reaproveitar o
modelo existente.

### Esperar o schema completo de EscolaOut antes de criar qualquer tabela

Rejeitada. O usuário quer a estrutura pronta e os dados sendo capturados já
— o campo `dados_api` (JSON) resolve isso sem exigir o schema completo
agora.

## Pendencias

- Credenciais reais (`DASHBOARD_EACE_URL`, `DASHBOARD_EACE_TOKEN`) — sem
  elas, a sincronização não pode ser testada contra a API de verdade.
- Quando o schema de `EscolaOut` for conhecido, avaliar quais campos de
  `dados_api` merecem coluna tipada própria.
  > **Emenda (2026-08-13):** primeiro caso concreto registrado —
  > Velocidade Mínima, Kit Inicial e TARGET EACE (dados técnicos EACE por
  > escola, confirmados pelo usuário como vindos do DashboardEACE, um valor
  > por escola). Ver `docs/business_rules.md` RN-057 e `docs/BACKLOG.md`
  > PO-076 — bloqueados pela mesma pendência de credenciais/schema abaixo.
  >
  > **Emenda (2026-08-13, mesmo dia):** usuário forneceu um backup real do
  > banco de origem (`eace_jira_backup_20260813.sql.gz`, banco MySQL
  > `eace_jira`). Orquestrador inspecionou somente a estrutura (`CREATE
  > TABLE`, nomes/tipos de coluna — nenhum dado real copiado para a
  > documentação) e confirmou `velocidade_dl_minima` (tabela `issues`) com
  > alta confiança e `kit_wifi` como candidato provável para "Kit
  > Inicial" — ver RN-057/PO-076 para o detalhamento. **TARGET EACE não é
  > coluna por escola**: vem de uma tabela de referência
  > (`target_rede_externa`, por UF + velocidade exata) que não aparece
  > em nenhum endpoint documentado em `API_EXTERNA.md`. **Decisão tomada em
  > 2026-08-13** (mesmo dia): usuário confirmou espelhar essa tabela de
  > referência por completo no SGP — ver
  > `docs/adr/ADR-029_TABELA_DE_REFERENCIA_TARGET_REDE_EXTERNA_PARA_TARGET_EACE_POR_ESCOLA.md`,
  > que cobre essa decisão isoladamente (complementar a esta ADR-010, não é
  > redecisão dela).
- Se/como `Escola` deve se relacionar com `Cliente`/`Endereco` (e com
  RN-017) — decisão futura, não coberta aqui.

## Gatilho de regeneracao

Nenhum diagrama documenta esta ADR ainda. Quando a integração real estiver
funcionando (credenciais confirmadas), atualizar o diagrama `05 · Módulos e
dependências` para incluir `apps.escolas`.
