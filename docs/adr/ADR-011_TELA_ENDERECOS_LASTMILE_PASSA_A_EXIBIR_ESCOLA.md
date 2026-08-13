# ADR-011 - Tela de Enderecos Lastmile passa a exibir Escola (DashboardEACE); criacao de cotacao fica temporariamente indisponivel nessa tela

## Status

`Aprovado`

## Contexto

A tela "Enderecos / Lastmile" (`apps/leads/views.py::enderecos_lastmile_view`,
rota `leads:enderecos_lastmile`) hoje filtra
`Endereco.objects.filter(em_os_comercial_lastmile=True, os_atual_aberta=True)`
— exatamente os dois campos que a ADR-008 parou de atualizar (rotina
`ixc_os_comercial_lastmile` desativada). Por isso a tela está vazia
("Enderecos elegiveis: 0").

Essa tela nao e so uma listagem: o icone de Acoes abre um modal que cria
`Proposal` (cotacao) vinculada ao `Endereco`/`Cliente` daquela linha
(`Proposal.client_address`, `Proposal.cliente` — RN-017), via
`apps/leads/lastmile_views.py::endereco_lastmile_batch_proposal_create`.

O usuario decidiu que essa tela deve passar a mostrar os dados de
`apps.escolas.Escola` (sincronizados do DashboardEACE, ADR-009/010), com as
colunas INEP, Nome da escola, Estado, Municipio e Endereco. Como `Escola`
nao tem vinculo com `Cliente`/`Endereco` (ADR-010: model independente, "do
zero"), a criacao de cotacao a partir desta tela nao tem, hoje, para onde
apontar. Perguntado sobre isso, o usuario confirmou: por agora, so a grade
muda — a acao de criar cotacao fica indisponivel nessas linhas, sem decidir
ainda como uma `Escola` vira uma `Proposal`.

## Decisao

Trocar a fonte de dados da tela **global** de Enderecos Lastmile
(`enderecos_lastmile_view`/`enderecos_lastmile.html`) de `Endereco` para
`Escola`, removendo temporariamente a acao de criar cotacao nessa tela.

## Decisao detalhada

### Model `Escola` — promover campos confirmados (ADR-010 ja autoriza isso sem nova ADR)

Confirmado contra a API real em 2026-08-07 (ver `apps/escolas/services.py`),
`EscolaOut` traz (entre outros) `inep`, `nome`, `municipio` e `descricao`
(texto com o endereco completo). Promover de `dados_api` (JSON) para
colunas tipadas em `Escola`:

- `inep` (`CharField`);
- `nome` (`CharField`);
- `municipio` (`CharField`);
- `endereco_descricao` (`TextField`) — mapeado do campo `descricao` da API
  (unico campo parecido com "endereco" disponivel hoje; nao ha
  logradouro/numero/bairro separados no schema atual).

`uf` e `status_escola` ja existem como coluna tipada desde a PO-046.
Migration de `AddField` (com backfill dos registros ja sincronizados a
partir de `dados_api`, para nao exigir re-sincronizar do zero).

### Tela (`apps/leads/views.py`, `apps/leads/templates/leads/enderecos_lastmile.html`)

- `enderecos_lastmile_view` passa a consultar `Escola.objects.all()`
  (sem filtro de elegibilidade — usuario pediu "todos esses enderecos");
  busca textual (`q`) passa a considerar `nome`/`inep`/`municipio`/`uf`/
  `jira_key` em vez dos campos de `Endereco`/`Cliente`;
- colunas da grade: INEP, Nome da escola, Estado (UF), Municipio,
  Endereco (`endereco_descricao`);
- contador "Enderecos elegiveis" e reescrito para refletir o novo
  significado (ex.: "Total de escolas") — nao ha mais conceito de
  elegibilidade nesta tela;
- icone de Acoes que abria o modal de criar cotacao (`file-pen-line`,
  `openPartnerProposalModal`) e **removido/ocultado** nesta tela. O icone
  de detalhe tecnico (`endereco_tecnico_detail`) tambem sai, pois e
  especifico de `Endereco` e nao existe equivalente para `Escola` ainda;
- endpoints AJAX ligados ao modal
  (`endereco_lastmile_lead_address_grid`, `endereco_lastmile_partner_search`,
  `endereco_lastmile_batch_proposal_create`) **nao sao alterados nem
  removidos** — ficam sem uso nesta tela, prontos se a criacao de cotacao
  a partir de `Escola` for decidida no futuro.

### O que NAO muda

- `enderecos_lastmile_cliente_view`/`enderecos_lastmile_cliente.html` (a
  variante por cliente) **nao e alterada nesta ADR** — nao ha vinculo
  `Escola`↔`Cliente`, entao nao ha um equivalente direto; permanece como
  esta (mostrando 0 resultados, mesma causa da ADR-008), ate nova decisao;
- `RN-017` nao muda: continua exigindo `Endereco` (do `Cliente`) + `Partner`
  para abrir uma medicao. O que muda e que **esta tela especifica** deixa
  de ser um dos caminhos de entrada para criar essa `Proposal` — se for o
  unico caminho hoje, isso e um risco a validar (ver Pendencias), nao uma
  mudanca de regra;
- `Proposal` nao ganha vinculo com `Escola` nesta ADR.

## Consequencias positivas

- Resolve a tela vazia sem inventar filtro de elegibilidade para `Escola`
  (usuario pediu explicitamente "todos");
- Baixo risco: nao toca no model `Proposal` nem em RN-017/018;
- Reaproveita exatamente os campos que a API confirma hoje, sem inventar
  nome de campo.

## Consequencias negativas / riscos

- Usuarios que usavam esta tela especificamente para abrir cotacao a
  partir de um endereco lastmile perdem esse caminho ate nova decisao —
  **verificar se existe caminho alternativo** para criar `Proposal`
  (Dev deve confirmar e reportar como achado, nao assumir);
- a variante por cliente (`enderecos_lastmile_cliente`) fica inconsistente
  com a tela global (uma mostra `Escola`, a outra continua tentando
  mostrar `Endereco` vazio) — aceito temporariamente, registrado como
  pendencia.

## Alternativas consideradas

### Fazer a acao de cotar tambem funcionar com Escola (criar/vincular Cliente+Endereco na hora, ou dar FK direta em Proposal)

Rejeitada por agora. Usuario escolheu explicitamente a opcao de menor
risco ("so a grade por agora"), deixando o desenho de como uma `Escola`
se torna uma `Proposal` para uma decisao futura.

### Filtrar Escola por status_escola (ex.: so "Conectado") em vez de mostrar tudo

Rejeitada. Usuario pediu explicitamente "todos esses enderecos".

## Pendencias

- Confirmar se existe outro caminho no sistema para abrir `Proposal`
  vinculada a `Endereco`/`Cliente` fora desta tela — se esta tela for a
  unica porta de entrada, o usuario deve ser avisado antes do QA aprovar.
- Decisao futura: como (se) `Escola` se relaciona com `Cliente`/`Endereco`
  para permitir criar cotacao a partir dela.
- `enderecos_lastmile_cliente` continua quebrada (mesma causa da ADR-008,
  agora tambem defasada em relacao a tela global) — sem decisao ainda.

## Gatilho de regeneracao

Nenhum diagrama documenta esta tela ainda.
