# ADR-026 - Cotacao de RE/RI com multiplos parceiros candidatos, via novo model em apps.escolas

## Status

`Aprovado`

> **Emenda (2026-08-12):** o Dev, ao implementar a PO-068, verificou que o
> MySQL de producao (`speed_prod`, ADR-005) nao suporta `UniqueConstraint`
> condicional (Django emite o warning `models.W036` e a constraint nao e
> criada no banco). A regra de "no maximo um Selecionado por RE/RI"
> (secao "Modelo de dados" abaixo) fica garantida **somente pela camada de
> servico** (`selecionar_candidato_cotacao_rede`, que move os demais
> candidatos para "Recusado" na mesma transacao antes de marcar o
> selecionado), sem reforco no banco. Risco residual aceito: uma condicao de
> corrida entre duas requisicoes concorrentes selecionando candidatos
> diferentes do mesmo RE/RI ao mesmo tempo nao e impedida pelo banco — mesma
> classe de risco ja implicitamente aceita em outras invariantes deste
> sistema que dependem so da camada de servico. Nao ha acao corretiva
> proposta agora; registrado para o caso de o volume de uso tornar essa
> condicao de corrida um problema real observado.

## Contexto

Usuario pediu (2026-08-12) que, quando um RE ou RI (subatividade da Escola,
ADR-012) estiver no Setor de negocio "Lastmile" com Status de "Cotacao", o
analista possa vincular aquele RE/RI a **N Parceiros candidatos** ("cotacao"),
sabendo que apenas um deles vai seguir. O usuario informou que esse processo
ja existe no sistema, na arquitetura antiga, e precisa ser adaptado para a
arquitetura atual.

Investigacao do Orquestrador antes de desenhar a feature:

- hoje `RedeExterna`/`RedeInterna` (`ProcessoRedeBase`, ADR-012) tem um unico
  campo `parceiro` (FK para `partners.Partner`), editavel somente na Tela do
  Setor "Lastmile", via modal de selecao (RN-030/ADR-018) — sem conceito de
  multiplos candidatos;
- o processo "da arquitetura antiga" citado pelo usuario e, com alta
  confianca, o model `Proposal` (`apps/partners/models.py`): hoje usado na
  cotacao de Lead, onde N `Proposal` (uma por Parceiro candidato) sao
  agrupadas por `grupo_proposta_id`, cada uma com seu proprio `status`
  (`analise`/`ativa`/`aguardando_contratacao`/`contratado`/`declinado`/
  `encerrada`) — so uma chega a `contratado`;
- o catalogo de Status por Setor (`SetorStatus`, RN-025) ja e livre e
  administravel — "Cotacao" pode ser cadastrado como mais um Status do Setor
  "Lastmile" (nos Processos de RE e de RI) sem exigir campo novo no model
  para representar esse Status; nao ha, hoje, nenhum Status chamado
  "Cotacao" semeado no catalogo (a semeadura existente, migration
  `0006_seed_processos_setores_status_teste.py`, e dado de teste: "A fazer",
  "Em andamento", "Concluido").

Perguntado ao usuario (para nao inventar o desenho), decidido em 2026-08-12:

1. ao selecionar o vencedor da cotacao, o campo `parceiro` do RE/RI e
   preenchido automaticamente por esse vencedor — o modal de selecao manual
   (ADR-018/RN-030) deixa de ser o caminho enquanto a cotacao estiver
   definindo o Parceiro;
2. o fluxo vale somente para Rede Externa (RE) e Rede Interna (RI) — Mapa
   Calor (RN-043) fica fora por agora, sem necessidade concreta confirmada;
3. cada candidato guarda somente Parceiro + situacao da candidatura (Em
   cotacao / Selecionado / Recusado) — sem campos comerciais (valor, prazo)
   nesta versao;
4. selecionar o vencedor nao move o Status do RE/RI para fora de "Cotacao"
   automaticamente — trocar de Status continua sendo acao manual do
   analista, mesmo mecanismo ja usado hoje (RN-026/RN-033).

## Decisao

Criar um model novo, `CotacaoParceiro`, dentro de `apps.escolas` — nao
reaproveitar `Proposal` (`apps.partners`) e nao criar um model generico de
"subatividade" (ADR-025 ja adiou essa generalizacao). Cada linha representa
um Parceiro candidato em cotacao para um RE ou RI especifico.

## Decisao detalhada

### Por que nao reaproveitar `Proposal`

`Proposal` (`apps.partners`) tem FK para `leads.Lead`/`leads.LeadEndereco`/
`clientes.Cliente`/`clientes.Endereco` — nenhum desses se aplica a RE/RI, e
a maior parte dos ~30 campos comerciais/tecnicos de `Proposal` tambem nao
(decisao 3 acima: sem campos comerciais nesta versao). Reaproveitar exigiria
tornar todos esses campos opcionais para um caso de uso que nao os usa, ou
criar um segundo fluxo dentro do mesmo model — confuso.

Mais grave: adicionar a `Proposal` uma FK para `RedeExterna`/`RedeInterna`
inverteria a direcao de dependencia hoje aprovada. `apps.escolas` ja importa
`apps.partners` (campo `parceiro`, ADR-012) — mesma camada (1, dominio;
ADR-007 item 7), excecao nao listada na tabela de excecoes daquela ADR (a
unica excecao de mesma camada aprovada e `leads -> partners`), mas unidirecional.
Um FK de `Proposal` para `RedeExterna`/`RedeInterna` criaria
`partners -> escolas` **junto** com `escolas -> partners` (via `parceiro`),
reabrindo exatamente o tipo de ciclo de importacao que a emenda da ADR-007
eliminou (ex.: `core <-> leads`).

### Por que nao um model generico de "subatividade"

A ADR-025 ja registrou a decisao de adiar catalogo generico de subatividade
e model de instancia generico. Criar aqui, so para a cotacao, um mecanismo
generico que nao existe para o resto do RE/RI (Setor, Status, Parceiro,
Campo) contradiria aquela decisao sem necessidade nova que a justifique.

### Modelo de dados

```text
CotacaoParceiro
  content_type, object_id, content_object  -> GenericForeignKey (RedeExterna ou RedeInterna)
  parceiro       -> FK partners.Partner (mesma direcao de ProcessoRedeBase.parceiro)
  situacao       -> "em_cotacao" | "selecionado" | "recusado"
  criado_em, atualizado_em
```

`GenericForeignKey` em vez de duas FK nullable (uma para `RedeExterna`, outra
para `RedeInterna`): mesmo padrao ja usado por `CampoValor` e
`RegistroHistorico` (`apps.core.models`) para o mesmo problema (um dado que
se aplica a mais de um model concreto de subatividade). Reaproveitar o
padrao existente, em vez de inventar um terceiro jeito de resolver a mesma
coisa nesta base de codigo.

Regra de vencedor unico: no maximo uma linha com `situacao="selecionado"`
por `(content_type, object_id)` — `UniqueConstraint` condicional no banco,
reforcada tambem na camada de servico (ao marcar um candidato como
"Selecionado", os demais daquele mesmo RE/RI passam automaticamente para
"Recusado" na mesma operacao).

Efeito colateral direto, ja decidido: marcar "Selecionado" grava esse
Parceiro em `RedeExterna.parceiro`/`RedeInterna.parceiro` (RN-030), gerando
`RegistroHistorico` no mesmo padrao Antes/Depois ja usado para Parceiro
(RN-030/041) — a lista de candidatos em si (adicionar/remover) nao gera
`RegistroHistorico` proprio nesta versao.

### Acesso e permissao

Mesma trava ja usada para Parceiro (RN-030/ADR-018): o modal de gestao de
cotacao so fica disponivel quando a tela atual for a do Setor de negocio
"Lastmile" (`setor_atual == "Lastmile"`), dentro da permissao
`grupo_LastMile_required` (ADR-011) que ja protege a tela inteira.

### O que NAO faz parte desta ADR

- Mapa Calor (fora do escopo, decisao do usuario);
- campos comerciais por candidato (valor mensal, prazo, plano etc.);
- transicao automatica de Status ao selecionar o vencedor;
- historico proprio de adicionar/remover candidato (so a mudanca de
  `parceiro` decorrente entra em `RegistroHistorico`).

## Consequencias positivas

- resolve o pedido concreto (N parceiros em cotacao, um vencedor) sem
  reabrir ciclo de importacao entre `partners` e `escolas`;
- reaproveita o padrao `GenericForeignKey` ja validado (`CampoValor`,
  `RegistroHistorico`) em vez de inventar um quarto jeito de modelar RE/RI/
  algo-generico;
- `parceiro` continua sendo a mesma FK unica de sempre (RN-030) — nenhuma
  tela ou regra que ja consome esse campo precisa mudar; só passa a ser
  preenchido por outro caminho quando a cotacao estiver em uso;
- "Cotacao" como Status do catalogo (RN-025) evita alteracao de schema para
  representar esse estado — mesma flexibilidade que qualquer outro Status.

## Consequencias negativas / riscos

- convivem, na mesma tela, dois caminhos que escrevem `parceiro`: o modal de
  selecao direta (ADR-018, continua existindo para os casos fora do fluxo de
  cotacao) e a selecao de vencedor da cotacao — quem le o codigo sem esta ADR
  pode nao entender por que `parceiro` mudou sem passar pelo modal de
  selecao; mitigado por comentario no codigo apontando para esta ADR;
- sem campos comerciais por candidato nesta versao: se o time precisar
  comparar propostas por preco/prazo dentro da cotacao de RE/RI, isso ainda
  nao existe — extensao aditiva futura, se pedida;
- "Cotacao" depende de existir, no catalogo (RN-025), um `SetorStatus` com
  esse nome para o Setor "Lastmile" nos Processos de RE e de RI — se nao for
  semeado/cadastrado, a tela simplesmente nunca entra nesse estado (falha
  silenciosa de configuracao, nao de codigo); cabe ao Dev garantir que esse
  Status exista (semeadura ou instrucao de cadastro manual).

## Alternativas consideradas

### Reaproveitar `Proposal` (apps.partners), com FK opcional para RedeExterna/RedeInterna

Rejeitada. Ver "Por que nao reaproveitar `Proposal`" acima — inverteria a
direcao de dependencia aprovada pela ADR-007 (item 7) e traria ~30 campos
irrelevantes para o caso de uso.

### Duas FK nullable (`rede_externa`, `rede_interna`) em vez de GenericForeignKey

Rejeitada. Resolveria o caso de RE/RI, mas duplicaria exatamente o problema
que `CampoValor`/`RegistroHistorico` ja resolveram de outro jeito nesta base
de codigo — preferiu-se manter um padrao unico para "dado que se aplica a
mais de um model de subatividade".

### Generalizar catalogo de subatividade agora, aproveitando a demanda

Rejeitada. Contradiria a decisao de adiamento da ADR-025 sem um segundo caso
concreto novo que a justifique.

## Pendencias

- Mapa Calor: se o usuario pedir esse fluxo tambem para Mapa Calor, e
  extensao aditiva (o `GenericForeignKey` ja aceita qualquer model, sem
  mudanca de schema em `CotacaoParceiro`) — falta so habilitar na tela;
- campos comerciais por candidato: nao pedido agora; se pedido depois,
  campos novos em `CotacaoParceiro`, aditivo;
- semeadura do Status "Cotacao" no catalogo (RN-025) para os Processos de RE
  e RI, Setor "Lastmile" — decisao de como (migration de dados ou cadastro
  manual pela tela de Administracao, PO-050) fica com o Dev, sem exigir nova
  decisao de produto.

## Gatilho de regeneracao

`docs/diagrams/03 - modelo-dominio.html` (e o JSON que o gera,
`modelo-dominio.architecture.json`) documenta hoje `RedeExterna`/
`RedeInterna` e a FK `parceiro` para `partners.Partner`. Quando esta feature
for implementada, esse diagrama fica desatualizado (falta `CotacaoParceiro` e
sua ligacao generica com RE/RI e com `Partner`) — regenerar via `archify`
(comando `atualizar diagrama`) somente quando solicitado, nao automaticamente.
