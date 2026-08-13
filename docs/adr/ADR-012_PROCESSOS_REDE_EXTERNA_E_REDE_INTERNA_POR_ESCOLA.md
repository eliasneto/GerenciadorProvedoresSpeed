# ADR-012 - Processos de Rede Externa (RE) e Rede Interna (RI) por Escola

## Status

`Aprovado`

> **Emenda (2026-08-07):** a pendencia de vocabulario de setor/status
> (secao "Pendencias" abaixo) foi resolvida pela ADR-014 — catalogo
> `Processo`/`Setor`/`SetorStatus`, com `RedeExterna`/`RedeInterna`
> ganhando um vinculo opcional para `Processo`. `setor`/`status` como
> `CharField` livre em `RedeExterna`/`RedeInterna` **nao mudaram** — a
> ADR-014 registra isso como pendencia propria, nao decisao tomada.

## Contexto

O usuario decidiu que cada `Escola` (`apps.escolas.Escola`, ADR-010) tem dois
processos de implantacao de conectividade, tratados como independentes entre
si: **Rede Externa (RE)** e **Rede Interna (RI)**. A API do DashboardEACE ja
sugere essa separacao — traz pares de campos como `setor_re`/`setor_ri`,
`parceiro_re`/`parceiro_ri`, `custo_re_implantacao`/`custo_ri_implantacao`,
hoje soterrados dentro do `dados_api` (JSON) de `Escola`, sem uso.

Perguntado se RE/RI seriam apenas uma leitura organizada desses campos da API
ou um processo gerido pelo proprio sistema, o usuario respondeu:

> "Cada RE e RI tem seu proprio processo, seu pode esta em setores
> diferentes e cada setor tem seu status, entao pode esta com status
> diferentes. Mas os dois tem que esta abaixo da escola (INEP). [...] cada
> um vai rodar seu processo, vai ter suas informacoes e seus status. cada
> um tambem tera um parceiro diferente ou o mesmo."

Confirmado via pergunta direta:

- RE e RI sao **geridos pelo nosso sistema** (fluxo de trabalho proprio,
  atualizado por quem opera o processo) — nao um espelho somente-leitura
  dos campos `*_re`/`*_ri` da API;
- cada `Escola` tem, no maximo, **1 RE e 1 RI** (sem historico de
  ciclos/tentativas por agora).

## Decisao

Criar dois models novos em `apps.escolas` — `RedeExterna` e `RedeInterna` —
cada um em relacao 1-para-1 com `Escola`, com um conjunto de campos comum
(setor, status, parceiro, informacoes adicionais), sem espelhar
automaticamente os campos `*_re`/`*_ri` da API do DashboardEACE.

## Decisao detalhada

### Por que duas tabelas, e nao uma so com campo `tipo`

O usuario deixou a escolha aberta ("precisamos criar uma tabela de banco
para cada um ou uma so para todos"). Optou-se por **duas tabelas**:

- RE e RI ja nascem como conceitos distintos no dominio (a propria API os
  trata como pares de campos separados, nunca um unico campo com
  discriminador);
- cada processo pode evoluir com campos proprios no futuro (ex.: RE ganhar
  um campo especifico de fibra/ultima milha, RI ganhar um campo especifico
  de kit wifi) sem exigir campos nulos condicionais numa tabela unica;
- `escola.rede_externa` / `escola.rede_interna` (via `OneToOneField` com
  `related_name`) e mais direto no codigo e nos templates do que
  `escola.processos.get(tipo="RE")`.

Custo aceito: duas migrations e dois `ModelAdmin` quase identicos. Mitigado
com uma classe abstrata (`ProcessoRedeBase`) compartilhando os campos
comuns — sem duplicar definicao de campo.

### Cardinalidade — 1 RE + 1 RI por escola

`OneToOneField(Escola, on_delete=models.CASCADE)`. Sem historico de
ciclos/tentativas por agora (confirmado pelo usuario). Se precisar de
historico depois, e mudanca aditiva (novo model de historico), nao
destrutiva.

`on_delete=CASCADE`: RE/RI sao subordinados a Escola ("os dois tem que esta
abaixo da escola") — se a Escola for excluida, nao ha sentido em manter o
processo orfao.

### Campos comuns (`ProcessoRedeBase`, abstrato)

Confirmados pelo usuario: setor, status, parceiro. Nao ha vocabulario de
setor/status definido ainda — **nao inventado** nesta ADR:

- `setor` — `CharField(max_length=120, blank=True)`, sem `choices=`. Texto
  livre por agora; se o usuario definir uma lista fixa de setores depois,
  trocar para `choices=` e uma migration aditiva simples;
- `status` — `CharField(max_length=60, blank=True)`, sem `choices=`, pelo
  mesmo motivo. RE e RI tem instancias separadas desse campo, portanto **ja
  podem estar em status diferentes** sem nenhum campo extra;
- `parceiro` — `ForeignKey("partners.Partner", null=True, blank=True,
  on_delete=models.SET_NULL)`. O projeto ja tem um cadastro de parceiros
  (`apps.partners.Partner`, usado em `Proposal`/cotacao) — reaproveitado em
  vez de criar um campo de texto livre duplicando essa informacao. RE e RI
  cada um tem sua propria FK, podendo apontar para o mesmo `Partner` ou para
  dois diferentes, exatamente como descrito;
- `dados_adicionais` — `JSONField(default=dict, blank=True)`. O usuario
  mencionou "suas informacoes" sem detalhar o formato. Em vez de inventar
  campos especificos, segue o mesmo padrao ja usado em `Escola.dados_api`
  (ADR-010): um espaco extensivel para o que for necessario registrar por
  processo, promovido a coluna tipada depois, quando o formato for
  confirmado;
- `criado_em` (`DateTimeField(auto_now_add=True)`), `atualizado_em`
  (`DateTimeField(auto_now=True)`) — auditoria basica de quando o processo
  foi aberto e a ultima atualizacao, no mesmo padrao do resto do projeto.

### Onde vivem os models

Dentro de `apps.escolas` (mesmo app de `Escola`), nao um app novo. RE/RI sao
subordinados 1-para-1 a `Escola`, sem dominio proprio ainda que justifique
um app dedicado (decisao tecnica reversivel e de baixo risco — extrair para
`apps.processos` ou similar depois, se o volume/complexidade crescer, e uma
migration de `db_table`, nao uma reescrita).

### O que NAO faz parte desta ADR

- **Sem sincronizacao automatica** dos campos `setor_re`/`setor_ri`,
  `parceiro_re`/`parceiro_ri`, `custo_re_*`/`custo_ri_*` da API do
  DashboardEACE para `RedeExterna`/`RedeInterna`. O usuario confirmou que
  esses processos sao geridos pelo sistema, nao espelhados da API. Os
  campos `*_re`/`*_ri` continuam disponiveis em `Escola.dados_api`,
  intocados, para consulta manual se necessario;
- **sem tela dedicada** de gestao do processo (abrir, avancar status,
  atribuir parceiro). Nao foi pedido; nesta ADR entram apenas os models e o
  cadastro basico via Django Admin, para que o dado possa ser criado e
  editado desde ja. Uma UI dedicada (fora do Admin) e decisao futura, se o
  usuario pedir;
- **sem workflow/maquina de estados** para o campo `status` (transicoes
  permitidas, quem pode mudar, etc.) — vocabulario e regras de transicao
  nao foram definidos; `status` e texto livre por agora.

## Consequencias positivas

- RE e RI podem ter setor, status e parceiro totalmente independentes entre
  si, incluindo status diferentes ao mesmo tempo — exatamente como
  descrito;
- reaproveita `apps.partners.Partner` em vez de duplicar cadastro de
  parceiro;
- nao inventa vocabulario de setor/status nem workflow — campos abertos,
  promovidos a `choices=`/maquina de estados quando o usuario definir;
- baixo acoplamento: nao altera `Escola`, `Cliente`, `Endereco` ou
  `Proposal`; migration puramente aditiva.

## Consequencias negativas / riscos

- sem historico: se um processo for reaberto/refeito, o registro atual e
  sobrescrito, nao ha rastro do ciclo anterior — aceito pelo usuario por
  agora;
- `status`/`setor` como texto livre nao impede valores inconsistentes
  (ex.: "Concluido" vs "concluido") — aceitavel enquanto o vocabulario nao
  e definido; e o preco de nao inventar uma lista de valores sem
  confirmacao;
- Django Admin como unica interface de edicao por agora pode nao ser
  suficiente para o uso diario de quem administra o processo — sinalizar
  se isso for um problema na pratica.

## Alternativas consideradas

### Uma tabela unica `ProcessoEscola` com campo `tipo` (RE/RI)

Rejeitada. Ver "Por que duas tabelas" acima — RE e RI ja sao tratados como
conceitos separados no dominio (inclusive na API), e a divergencia futura de
campos especificos e mais provavel do que a unificacao.

### Espelhar automaticamente os campos `*_re`/`*_ri` da API a cada sincronizacao

Rejeitada. O usuario confirmou explicitamente que quer um processo gerido
pelo sistema, nao um espelho read-only da API.

### Historico de ciclos (1 Escola : N RE, N RI)

Rejeitada por agora — usuario confirmou 1 RE + 1 RI por escola. Registrada
como extensao aditiva futura, se necessario.

### Criacao do registro comeca em branco, sem pre-preencher a partir da API

`RedeExterna`/`RedeInterna` **nao** sao pre-preenchidos com `setor_re`/
`setor_ri`/`parceiro_re`/`parceiro_ri` (que ja existem em `Escola.dados_api`)
no momento da criacao. Decisao tecnica reversivel e de baixo risco (secao 9
do `CLAUDE.md`): comecar em branco evita assumir que o formato/vocabulario
desses campos da API bate com o que o sistema vai usar em `setor`/`parceiro`
proprios — assumir isso sem confirmar seria inventar uma regra de mapeamento.
Pre-preencher depois, se o usuario pedir, e mudanca aditiva simples.

## Pendencias

- Vocabulario de `setor` e `status` (lista fixa de valores) — quando o
  usuario definir, migrar de texto livre para `choices=`;
- decidir se havera workflow/maquina de estados para transicao de status;
- decidir se havera tela dedicada (fora do Admin) para operar RE/RI no
  dia a dia.

## Gatilho de regeneracao

Nenhum diagrama documenta esta arquitetura ainda.
