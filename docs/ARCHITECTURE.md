# Architecture

## Objetivo

Consolidar as decisoes arquiteturais principais do projeto.

## Dominio e camadas (arquitetura-alvo — ADR-005)

O centro do sistema e o dominio persistido no banco MySQL (`speed_prod`), nao a
API publica. As demais camadas orbitam esse dominio.

### Dominio (banco)

- `partners`: `Partner`, `PartnerPlan`, `Proposal` (proposta/cotacao e a entidade
  central), `ProposalMotivoInviavel`;
- `leads`: `LeadEmpresa`, `LeadEndereco`, `Lead` (prospeccao e estruturacao por IA)
  — alimenta `Proposal`;
- `core`: `User` custom, `RegistroHistorico` (historico generico), auditoria de
  integracao (`IntegrationAudit`/`IntegrationAuditItem`), sync de e-mail de
  cotacao, `AutomacaoMenu` (registro de menu/permissao de automacoes),
  `RestoreBackupAuditoria` e `CotacaoStatusAuditoria` (movidos de
  `core_admin` e `auditoria` pela PO-036, aguardando QA — ver ADR-007 item 8);
- `core_admin`: configuracao (`AcessoBancoDados`, `ConfiguracaoEmailEnvio`,
  `TesteConexaoIXC`);
- `auditoria`: modelos proxy de leitura sobre auditoria/historico (inclui
  proxies para `RestoreBackupAuditoria`/`CotacaoStatusAuditoria`, agora reais
  em `core`);
- `clientes`: `Cliente`, `Endereco`, `HistoricoSincronizacao`, `ClienteExcluido`
  (dominio sincronizado do IXC — cliente/login/endereco; app com o maior numero
  de migrations do projeto). Nao constava neste levantamento original da ADR-005;
  adicionado em 2026-07-29 (auditoria de organizacao do repositorio).
- `escolas`: `Escola` (sincronizada do DashboardEACE, ADR-010), `RedeExterna`/
  `RedeInterna` (processos 1:1 com Escola, ADR-012), catalogo `Processo`/`Setor`/
  `SetorStatus` (ADR-014) e `Campo`/`CampoValor` (campos personalizados por
  Setor, ADR-019); tambem `SetorEscopo`, ainda pendente de rework (PO-062,
  ADR-023). Sem relacao com `Cliente`/`Endereco`/`Proposal`. Nao constava no
  levantamento original da ADR-005; adicionado em 2026-08-11 (Epic 14/15,
  auditoria de diagramas).

### Camadas (alvo)

Conforme ADR-005, o projeto evolui para um monolito modular em tres camadas, sem
microservicos, API Gateway dedicado ou message broker nesta fase:

1. `Entrada` — views Django finas e API REST (`integracoes_api`): apenas
   entrada/saida, sem regra de negocio;
2. `Servicos / Dominio` — toda regra de negocio, por app; views e serializers
   chamam servicos;
3. `Integracao` — um adaptador ("gateway") unico por sistema externo (IXC,
   Active Directory, e-mail de cotacao, Google/lastmile, Busca Parceiro, Correios
   [consulta de CEP], IA), com timeout, tratamento de erro, log e auditoria
   padronizados.

A auditoria (`IntegrationAudit`) e o barramento transversal por onde toda escrita
externa e registrada.

Estado atual x alvo: a regra de negocio ainda vive parcialmente em views e em
`scripts/`, e o acesso ao IXC tem implementacoes paralelas. A migracao e
incremental (Epic 13 no backlog): `apps/backoffice` tem `services.py` desde a
PO-023 (concluida); a PO-011 estende o padrao aos demais apps, fatiado por
app e, quando necessario, por grupo/sub-fatia de telas dentro do app —
`leads` e `core` entregues (aguardando QA); `partners` sub-fatiado em 3
grupos: `Parceiro` e `Relatorios de Gestao` entregues, `Proposta` por sua
vez sub-fatiado em 3 (CRUD e navegacao entregue; Lote e Fechamento de
O.S./edicao financeira pendentes — esta ultima de risco alto por
concentrar RN-017/RN-018, integracao IXC e calculo financeiro) — tudo
aguardando QA; `core_admin` ainda nao iniciado. `scripts/` -> management
command (PO-034) ainda nao decidido quando/como migrar. O Hub de Integracao
(`apps/integracoes/`, PO-033) foi entregue pelo Dev em 2026-08-03 — subpastas
`ixc/`, `ad/`, `email/` e `google/` — e aguarda QA; `apps/integracoes/correios/`
segue como gap (ver abaixo).

Divergencia fechada em codigo (2026-07-27, PO-026, aprovada pelo QA): o
`IXCGateway` (`IXCClient`) foi movido de `scripts/integracoes/ixc_client.py`
para `apps/core/ixc_client.py`, dentro da estrutura de apps Django, fechando a
divergencia com a regra geral da ADR-005 de que codigo de integracao de
producao deve residir dentro dos apps.

Nova movimentacao (2026-08-03, PO-033 — aguardando QA): o `IXCGateway`
(`IXCClient`) saiu de `apps/core/ixc_client.py` para
`apps/integracoes/ixc/client.py`, junto com as funcoes de integracao IXC
(`apps/core/integracoes_ixc/` -> `apps/integracoes/ixc/services/`), o
`ad_sync.py` (`apps/core/` -> `apps/integracoes/ad/`) e as buscas de
fornecedor via Google (`scripts/integracoes/Lastmile/APIGoogle_BuscaFornecedores.py`
e `scripts/automacoes/API_BuscaParceiro/buscaParceiro.py` ->
`apps/integracoes/google/`), formando o Hub de Integracao alvo da ADR-007
item 4. `apps/integracoes/correios/` segue sem criar (gap do CEP abaixo).

Nova subpasta (2026-08-07, ADR-009): `apps/integracoes/dashboard_eace/` —
cliente HTTP dedicado (`DashboardEACEClient`), autenticacao via `X-API-Key`
(contrato confirmado em `API_EXTERNA.md`, raiz do projeto). Endpoint de
leitura de escolas (`/escolas[/{jira_key}]`) ja implementado
(`services/escolas.py`). Ainda sem credenciais reais configuradas.

Os dados de `/escolas` **nao** vao para `apps.clientes.Cliente`/`Endereco`
(mudanca de direcao em relacao ao desenho original da ADR-009) — vao para
um model novo e dedicado, `apps.escolas.Escola` (ADR-010), com um campo
JSON guardando o payload bruto completo ate o schema de `EscolaOut` ser
confirmado. `Cliente`/`Endereco` continuam existindo, independentes.

Cada `Escola` tera, no maximo, um processo de Rede Externa (RE) e um de
Rede Interna (RI) — `apps.escolas.RedeExterna`/`RedeInterna` (ADR-012,
PO-048), cada um 1-para-1 com `Escola`, com setor/status/parceiro proprios,
geridos pelo sistema (nao um espelho dos campos `*_re`/`*_ri` da API).

Planejado (2026-08-11, RN-043/PO-067, ainda nao implementado): terceira
subatividade fixa `apps.escolas.MapaCalor`, no mesmo molde hardcoded de
RE/RI (mesma classe abstrata `ProcessoRedeBase`). Generalizar isso para um
catalogo administravel de subatividades — e suportar mais de uma atividade
principal alem de `Escola` — foi avaliado e **adiado** por decisao do
usuario (ADR-025): nenhum trabalho de catalogo dinamico deve ser feito sem
nova decisao explicita.

Planejado (2026-08-12, RN-052/PO-073, ainda nao implementado):
`ProcessoRedeBase` ganha um campo `responsavel` (FK `core.User`,
`SET_NULL`), atribuivel/reatribuivel manualmente, herdado por RE/RI/Mapa
Calor. Setor, Status e Responsavel passam a ser exigidos pela camada de
negocio/UI, mas continuam opcionais no schema (sem migracao de dados
legados) — decisao registrada na ADR-027.

Gap conhecido (achado em 2026-07-29): a consulta de CEP (`apps/clientes/views.py::buscar_cep`)
chama uma API terceirizada (Hub do Desenvolvedor) direto na view, sem um
gateway proprio isolado — unico dos sistemas externos listados acima ainda sem
adaptador dedicado. Vira candidato a `CorreiosGateway` (mesmo padrao de
timeout/erro/log dos demais) quando houver necessidade real (ex.: trocar de
fornecedor de CEP, reaproveitar a consulta em mais de uma automacao); nenhuma
feature aberta para isso ainda.

Divergencia fechada (PO-029, aprovada pelo QA em 2026-07-30): o app
`clientes` (ver lista de dominio acima) foi movido de `clientes/` (raiz do
repositorio) para `apps/clientes/`, alinhado a convencao ja seguida por
`core`, `core_admin`, `auditoria`, `backoffice`, `leads`, `partners` e
`integracoes_api`.

## Conjunto de diagramas e ordem de leitura

Os diagramas do projeto formam um conjunto complementar, no espirito do modelo
C4: cada um da um nivel de zoom a mais sobre o mesmo sistema. Leia nesta ordem;
todos ficam em `docs/diagrams/` e sao servidos pelo portal `/docs/`.

| # | Arquivo | Pergunta que responde | Publico |
|---|---|---|---|
| `01` | `contexto-sistema` | Quem usa o sistema e com quais sistemas externos ele fala? | qualquer pessoa, inclusive fora da equipe |
| `02` | `ciclo-vida-cotacao` | Qual e o processo de negocio, do endereco ao desfecho da proposta? | qualquer pessoa; e o "por que o sistema existe" |
| `03` | `modelo-dominio` | Quais entidades existem e como se relacionam? | quem vai mexer em model, migration ou consulta |
| `04` | `gerenciador-provedores` | Como o sistema se organiza por dentro (camadas, gateways, estrutura de pastas)? | quem vai desenvolver ou revisar |
| `05` | `modulos-dependencias` | Quais apps existem e quem chama quem? | quem vai mexer em mais de um app |
| `06` | `adr-006-expansao-modular` | Como os dados entram, saem e se recuperam de falha no Modulo 1 (sistema atual)? | quem vai implementar as automacoes de fila |
| `07` | `processos` | Quais automacoes e rotinas existem, quando rodam e por qual caminho? | operacao e quem vai mexer em rotina |
| `ANEXO A` | `integration-hub-conceitual` | Por que **nao** adotamos um Integration Hub generico? | anexo de decisao; nao faz parte da sequencia |

A sequencia vai do **negocio para o tecnico**: contexto, processo de negocio e
as entidades que o sustentam (01-03), depois como o software se organiza para
atende-lo (04-06), e por fim a operacao do dia a dia (07).

Sete pranchas e o teto pratico do que um time mantem vivo. Antes de acrescentar
a oitava, verificar se o assunto nao cabe como card em uma existente ou como
tabela neste documento — foi o criterio usado para deixar de fora o catalogo de
processos, a matriz de permissoes e o diagrama de deploy (este ultimo tambem
por ser escopo do DevOps, ver `docs/devops/CONTAINERS.md`).

O Modulo 2 ainda nao tem diagrama: a `ADR-006` decidiu o padrao (kill switch,
dependencia em uma via so, pacote `apps/modulo2/<setor>/`), mas nenhum setor
ou automacao concreta foi definida. No diagrama `06` ele aparece apenas como
espaco reservado. Quando for desenhado, entra na sequencia como `08`.

### Achado do diagrama 05 — ciclos de importacao entre apps (2026-07-29)

O levantamento feito para o diagrama `modulos-dependencias` (grafo real de
imports entre apps, codigo de producao, testes excluidos) encontrou **cinco
ciclos** envolvendo seis dos oito apps:

- `core` <-> `core_admin`, `core` <-> `leads`, `core` <-> `partners`;
- `core_admin` <-> `backoffice`;
- `core_admin` -> `auditoria` -> `backoffice` -> `core_admin`.

Todos sao imports de nivel de modulo (nao sao imports tardios dentro de
funcao). Os tres primeiros nascem de um unico arquivo: `apps/core/views.py`
linhas 27-29, onde o app base importa de `leads`, `partners` e `core_admin`.

Causa raiz: **nao existe regra de dependencia entre os apps atuais**. A
ADR-006 define dependencia em uma via so apenas para o futuro Modulo 2, e a
ADR-007 define estrutura de pastas, mas nenhuma das duas estabelece ordem de
camada entre `core`, `clientes`, `leads`, `partners`, `backoffice`,
`core_admin`, `auditoria` e `integracoes_api`. Sem essa regra, nenhuma revisao
consegue apontar violacao de forma objetiva.

`clientes` e hoje o unico app-folha limpo (nao importa nenhum outro app).

Registrado como **item 7 da ADR-007** (emenda de 2026-07-29), que generaliza
para os apps atuais a regra de dependencia em uma via so que a ADR-006 ja
aplicava ao Modulo 2. Ordem de camada proposta: `core`/`integracoes` (base) ->
`clientes`/`partners`/`leads` (dominio) -> `backoffice`/`core_admin`/
`auditoria` (aplicacao) -> `integracoes_api` (entrada) -> `modulo2` (expansao),
com `leads -> partners` como unica excecao aprovada de mesma camada.

Confirmado pelo usuario em 2026-07-29: a tabela acima passa a valer como
criterio de reprovacao em code review. A correcao do codigo (eliminar os
cinco ciclos e aplicar a ordem de camada) e o escopo da PO-032 no backlog.

Regras do conjunto:

- cada diagrama tem um nivel de zoom proprio — nao duplicar assunto entre eles;
- **o numero da prancha fica no proprio documento**: o titulo comeca com
  `01 ·` a `07 ·` ou `ANEXO A ·`, o subtitulo repete a posicao
  (`Leitura 2 de 3`) e cada diagrama traz um card "Sequencia de leitura" com o
  conjunto inteiro e a marcacao de onde o leitor esta — quem abre um documento
  solto descobre a ordem sem sair dele;
- ao acrescentar ou remover um diagrama da sequencia, atualizar o numero e o
  "de N" nos quatro lugares: titulo, subtitulo, card de sequencia de cada
  documento e esta tabela;
- diagrama que documenta uma ADR deve ser regenerado quando a decisao mudar (a
  ADR-006 registra explicitamente esse gatilho);
- alternativa descartada vira anexo, nao passo da sequencia.

Aposentado em 2026-07-29: `arquitetura-geral` cobria o mesmo assunto do
diagrama 3 em uma versao menos completa (sem kill switch, sem legenda, sem
agendamentos). O que ele modelava melhor — as rotinas de busca como caixas
proprias, separadas do gateway — foi absorvido pelo diagrama 3 antes da
remocao. Recuperavel pelo historico do git, se necessario.

### Achado da auditoria de diagramas — dominio Escola/DashboardEACE ausente (2026-08-11)

Auditoria do Orquestrador (2026-08-11), a pedido do usuario, enquanto o Dev
implementa a PO-067 (Mapa Calor) em paralelo. Escopo: conferir se o conjunto
de diagramas bate com este documento e com o codigo real. Nao alterou nenhum
diagrama (MODO 5 do Orquestrador nao gera diagrama sem comando explicito) nem
nenhum arquivo da PO-067 em andamento.

**Numeracao e sequencia — sem divergencia.** Conferido nos 8 arquivos
(`01` a `07` + `ANEXO A`): titulo `NN ·`, subtitulo "Leitura N de 7" e o card
"Sequencia de leitura" batem entre si e com a tabela acima, na mesma ordem,
com o marcador "voce esta em NN" correto em cada um. Unica variacao: o
diagrama `04` escreve o cabecalho desse card com acentuacao plena e travessao
("Sequência de leitura — você está em 04"), enquanto os demais usam texto sem
acento e hifen — inconsistencia cosmetica, nao numerica; nao corrigido aqui
por nao ser claro qual das duas convencoes e a pretendida.

**Achado principal: nenhum diagrama foi regenerado desde 2026-08-03**
(verificado pela data de modificacao dos 8 arquivos HTML/JSON), mas todo o
Epic 14 e o Epic 15 (`ADR-008` a `ADR-024`; `PO-044` a `PO-066`; `RN-017`
ampliada duas vezes; `RN-023` a `RN-042`) foi entregue entre 2026-08-07 e
2026-08-11 — o dominio `apps.escolas` (Escola, RedeExterna, RedeInterna,
Processo, Setor, SetorStatus, Campo, CampoValor) e a integracao
`apps.integracoes.dashboard_eace` nao aparecem em nenhum dos 8 diagramas.
Cada uma das 14 ADRs de `ADR-011` a `ADR-024` ja registra, na propria secao
"Gatilho de regeneracao", a nota "nenhum diagrama documenta esta tela/
arquitetura ainda" — este achado apenas consolida o que ja estava sinalizado,
disperso, ADR por ADR.

Pontos especificos verificados:

- diagrama `03 · Modelo de dominio` (proposito: "quais entidades existem e
  como se relacionam") nao lista nenhuma entidade de `apps.escolas`;
- diagrama `05 · Modulos e dependencias` nao lista `apps.escolas` como app do
  monolito — e o gatilho que a propria `ADR-010` registrou para isso
  ("quando a integracao real estiver funcionando, credenciais confirmadas")
  ja foi cumprido: a `PO-046` confirma 2622 escolas sincronizadas contra a
  API real do DashboardEACE;
- diagrama `01 · Contexto do sistema` nao lista o DashboardEACE entre os
  "Sistemas externos" (lista hoje: IXC, Active Directory, Servidor de
  E-mail, Google API, API de CEP), apesar de ser uma integracao real e
  credenciada (`ADR-009`/`ADR-010`, `API_EXTERNA.md`);
- diagrama `04 · Arquitetura-alvo` e a arvore ASCII de "Estrutura alvo do
  repositorio" (secao abaixo) nao incluem `apps/escolas/` nem
  `apps/integracoes/dashboard_eace/`, ambos ja existentes no codigo e
  `apps.escolas` ja registrado em `INSTALLED_APPS`;
- diagrama `02 · Ciclo de vida da cotacao` afirma, no titulo/subtitulo e nos
  cards, que o Endereco "vem sincronizado do IXC pelas rotinas agendadas" —
  desatualizado desde a `ADR-008` (2026-08-07), que desativou essas 4
  rotinas; a `RN-017` (ampliada duas vezes, 2026-08-07) ja registra que hoje
  nao ha nenhuma fonte automatica alimentando `Cliente`/`Endereco` (nem IXC,
  nem DashboardEACE, que alimenta a tabela separada `Escola`);
- diagrama `07 · Processos de automacoes e rotinas` e a tabela "Catalogo de
  automacoes e rotinas" (secao abaixo) nao incluem o management command
  `sincronizar_escolas_dashboard_eace` (`PO-046`) — ele nao se encaixa em
  nenhum dos tres tipos de gatilho hoje documentados (botao no Admin, loop
  de 60s, upload de planilha), sendo candidato a um quarto tipo ("comando
  manual via CLI/management command") ainda nao catalogado.

Relacionado, fora do escopo de diagrama: `docs/modules/` tem README para 8
apps (`auditoria`, `backoffice`, `clientes`, `core`, `core_admin`,
`integracoes_api`, `leads`, `partners`), sem entrada para `escolas`.

**Sobre a ADR-025 (generalizacao de subatividades adiada), especificamente
solicitado nesta auditoria:** nao exige diagrama proprio — e uma decisao de
adiamento, sem alvo tecnico desenhado (ver a propria ADR, secao "Gatilho de
regeneracao"). Nao introduz divergencia nova alem da ja registrada acima: o
diagrama `03` ja nao cobre o dominio Escola/RE/RI de forma alguma, antes e
independente da ADR-025. Quando o diagrama `03` for regenerado para incluir
esse dominio, a decisao adiada deve entrar como nota/gap explicito (mesmo
espirito do `ANEXO A`, alternativa descartada) — nunca desenhada como se a
generalizacao ja existisse ou estivesse resolvida.

**Nao corrigido nesta auditoria** (decisao de escopo/conteudo, nao ajuste
textual): regenerar os diagramas `01`, `02`, `03`, `04`, `05` e `07`, e
sincronizar a arvore ASCII e as tabelas de dominio/automacoes deste
documento, exige decisao do usuario (comando `atualizar diagrama`/`gerar
diagrama`, MODO 5) — inclusive se faz sentido esperar a `PO-067` (Mapa
Calor) terminar antes, para regenerar uma vez so em vez de duas.

**Resolvido em 2026-08-11 (mesmo dia):** usuario decidiu regenerar agora,
em duas rodadas (aceitando regenerar de novo quando a PO-067/Mapa Calor
terminar). Os 6 diagramas (`01`, `02`, `03`, `04`, `05`, `07`) foram
regenerados via `archify` (MODO 5), cobrindo o dominio `apps.escolas`/RE-RI/
Setor/Campo e a integracao `apps.integracoes.dashboard_eace` — **sem**
incluir Mapa Calor (PO-067 ainda em desenvolvimento pelo Dev nesta data).
A lista de dominio, a arvore ASCII e a tabela "Catalogo de automacoes e
rotinas" deste documento tambem foram atualizadas (ver secoes abaixo).
Validacao: os 6 JSON de origem passaram por `archify validate`/`deliver`
sem erro (avisos de composicao aceitos, perfil `standard`); revisao visual
em navegador **nao executada** nesta sessao (sem leitor de imagem/browser
disponivel) — recomenda-se abrir os 6 arquivos uma vez antes de divulgar
amplamente. `docs/modules/escolas/README.md` foi criado no mesmo padrao dos
demais apps.

## Modelo de dominio — vinculos reais entre entidades

Levantado dos models em 2026-07-29. Diagrama: `03 · Modelo de dominio`.

`Proposal` e a entidade central confirmada: concentra **sete** chaves
estrangeiras, mais que qualquer outra do sistema.

| Campo em `Proposal` | Aponta para | Obrigatorio no banco? |
|---|---|---|
| `partner` | `partners.Partner` | **sim** (NOT NULL, CASCADE) |
| `cliente` | `apps.clientes.Cliente` | nao (`null=True`) |
| `client_address` | `apps.clientes.Endereco` | nao (`null=True`) |
| `lead` | `leads.Lead` | nao (`null=True`) |
| `lead_endereco` | `leads.LeadEndereco` | nao (`null=True`) |
| `motivo_inviavel` | `partners.ProposalMotivoInviavel` | nao |
| `responsavel` | `core.User` | nao (`SET_NULL`) |

**Achado: a RN-017 nao e imposta pelo schema.** A regra diz que abrir a
medicao exige endereco (do IXC) **e** provedor. No banco, so `partner` e
NOT NULL — `cliente` e `client_address` aceitam nulo. Verificar se o
formulario ou a camada de servico impede; se nao impedir, a obrigatoriedade
existe apenas no procedimento da equipe. Nenhuma alteracao feita.

Duas origens paralelas alimentam a mesma cotacao: o caminho do cliente real
(`Cliente` -> `Endereco`, sincronizados do IXC) e o da prospeccao (`Lead`
bruto, estruturado por IA em `LeadEmpresa`/`LeadEndereco`). Como os quatro
campos sao opcionais, uma cotacao pode citar so um caminho, os dois ou nenhum
— vale confirmar com o negocio se e mesmo assim que deve ser.

`RegistroHistorico` usa `GenericForeignKey` (ContentType): pendura em qualquer
entidade, por isso nao aparece com seta para cada uma no diagrama.

## Ciclo de vida da cotacao (processo de negocio)

Status reais de `Proposal.STATUS_CHOICES` (`apps/partners/models.py`),
verificados em 2026-07-29. Diagrama: `02 · Ciclo de vida da cotacao`.

| Chave no codigo | Rotulo exibido | Papel |
|---|---|---|
| `analise` | Em Negociacao | valor padrao ao criar a cotacao |
| `ativa` | **Viavel** | medicao aprovada |
| `encerrada` | **Inviavel** | exige `motivo_inviavel` (FK) + `observacao_inviavel` |
| `aguardando_contratacao` | Aguardando Contratacao | proposta enviada ao cliente |
| `contratado` | Contratado | desfecho positivo |
| `declinado` | Declinado | desfecho negativo |

Requisitos de abertura e transicoes validas confirmados pelo dono do produto em
2026-07-29 e registrados como **RN-017** e **RN-018** em
`docs/business_rules.md`:

- abrir a medicao exige **dois** requisitos obrigatorios e paralelos: o endereco
  (login) sincronizado do IXC e o provedor (`Partner`) cadastrado no sistema;
- `analise` so vai para `ativa` ou `encerrada`; declinar so e possivel **depois**
  de Viavel, a partir de `aguardando_contratacao`; `encerrada` (Inviavel) e
  terminal e nao reabre no momento.

Dois achados tecnicos do mesmo levantamento:

- **nao existe maquina de estado.** As views validam apenas se o status
  pertence a lista (`status_validos = {choice[0] for choice in
  Proposal.STATUS_CHOICES}`, `apps/partners/views.py`); nenhuma transicao e
  impedida. Na pratica, hoje qualquer status pode ir para qualquer outro,
  inclusive pular etapas ou sair de um terminal — RN-018 e regra de negocio
  confirmada, **nao** restricao implementada. Nenhuma feature aberta para
  impor a validacao;
- **a chave nao bate com o rotulo**: `ativa` significa *Viavel* e `encerrada`
  significa *Inviavel*. Quem le `status='ativa'` no codigo tende a entender o
  oposto do que o negocio quer dizer. Renomear as chaves exigiria migration de
  dados — nao avaliado.

## Catalogo de automacoes e rotinas

Levantado do `docker-compose.yml` (servico `speed_sincronizador`), do cadastro
`AutomacaoMenu` e dos admins, em 2026-07-29. O diagrama
`07 · Processos de automacoes e rotinas` mostra os **caminhos de execucao**;
esta tabela e o **catalogo** — mantenha os dois em sincronia quando uma rotina
entrar, sair ou mudar de horario.

### Agendados (loop de 60s no container)

| Processo | Frequencia | O que faz |
|---|---|---|
| `sincronizar_respostas_email_cotacao.py` | a cada 10 min | le respostas de cotacao na caixa de e-mail (IMAP) |
| `ixc_api_incremental.py` | **desativado** (ADR-008) | sync incremental de cliente/login do IXC |
| `ixc_os_comercial_lastmile.py` | **desativado** (ADR-008) | atualiza O.S. comercial/LastMile |
| `ixc_faxina.py` | **desativado** (ADR-008) | faxina de dados do IXC |
| `ixc_api.py` | **desativado** (ADR-008) | carga total de cliente/login |
| `backup_manual.py` | servico proprio | backup do banco |

As 4 rotinas de Cliente/Endereco do IXC foram desativadas em 2026-08-07
(ADR-008). O código permanece intacto — apenas os disparos (agendamento e
botões do Admin) foram comentados, reversível sem reescrever nada. Efeito
colateral conhecido: `apps/leads`/`apps/partners` deixam de receber
atualização automática de `em_os_comercial_lastmile`/`os_atual_aberta` (ver
ADR-008, consequências negativas). A fonte que substitui o IXC não é
importação manual: é a integração com o DashboardEACE (ADR-009) — mas os
dados dela vão para um model novo e independente (`apps.escolas.Escola`,
ADR-010), não para `Cliente`/`Endereco`. Ou seja, hoje não existe nenhuma
fonte automática alimentando `Cliente`/`Endereco`.

### Por upload de planilha (registradas em `AutomacaoMenu`)

`import_prospects` · `cotacao_import` · `atendimento_import` ·
`cadastrar_clientes_ixc` · `desativar_atendimentos_ixc` ·
`editar_atendimentos_ixc` · `editar_logins_ixc` ·
`resolver_os_atendimento_ixc` · `testar_api_ixc`

O menu onde cada uma aparece e a permissao de grupo sao configuraveis sem
deploy (RN-011).

### Por disparo manual no Admin

As mesmas seis rotinas agendadas, mais `parar_sincronizacao`. Os botões das
4 rotinas desativadas por ADR-008 tambem foram comentados (nao aparecem
mais no Admin enquanto a ADR estiver em vigor).

### Por comando manual (CLI, sem Admin nem agendamento)

Quarto tipo de gatilho, registrado em 2026-08-11 (auditoria de diagramas):

| Processo | Frequencia | O que faz |
|---|---|---|
| `sincronizar_escolas_dashboard_eace` (`apps/escolas/management/commands/`) | manual — `python manage.py <comando>`, sem agendamento nem botao no Admin (decisao da PO-046) | le `/escolas` da API real do DashboardEACE (X-API-Key) e grava `Escola` via `update_or_create` por chave, idempotente — 2622 escolas sincronizadas na validacao |

Diferente dos tres tipos acima: nao ha disparo automatico nem manual pela
tela — só quem tem acesso ao servidor consegue rodar. Candidato natural para
qualquer comando manual futuro que ainda nao precise de agendamento nem de
botao no Admin.

### Ressalvas conhecidas (diagnostico, nao corrigidas)

- **o agendador nao e cron**: e um `while true; sleep 60` dentro do bloco
  `command` do `docker-compose.yml`. O controle de "ja rodei neste slot" vive
  em variavel de shell (`ULTIMO_SLOT_*`), entao **reiniciar o container perde
  esse estado** e pode repetir ou pular uma execucao;
- **os disparos manuais estao duplicados** em `apps/clientes/admin.py` e
  `apps/auditoria/admin.py`, com os mesmos nomes de metodo
  (`btn_rodar_carga_total`, `btn_rodar_incremental`, `btn_rodar_faxina`,
  `btn_rodar_os_comercial_lastmile`, `btn_rodar_backup`,
  `btn_rodar_respostas_email_cotacao`);
- alvo da ADR-007 para todas elas: virar management command do app dono,
  eliminando os dez bootstraps manuais de Django em `scripts/`. Quando e como
  migrar **nao foi decidido** (exige alterar o `docker-compose.yml`).

## Estrutura alvo do repositorio (ADR-007)

Decisao registrada em `docs/adr/ADR-007_ESTRUTURA_ALVO_DO_REPOSITORIO.md`
(2026-07-29). E o **desenho do alvo**: nenhuma execucao foi autorizada por
ela — serve como referencia de onde cada coisa deve morar quando for mexida,
e como padrao obrigatorio para o primeiro app do Modulo 2.

```text
manage.py
config/                     settings, urls, wsgi, asgi
apps/
  __init__.py               pacote real - habilita o namespace unico
  core/                     User, RegistroHistorico, IntegrationAudit
  clientes/  leads/  partners/  backoffice/  core_admin/  auditoria/
  escolas/                  Escola, RedeExterna/Interna, Processo/Setor/Campo (Epic 14/15, ja real)
  integracoes_api/          API publica v1 (JWT)
  integracoes/              camada de integracao unificada
    ixc/  google/  email/  ad/  correios/  dashboard_eace/
  modulo2/<setor>/          expansao futura (ADR-006)
docs/                       documentacao, ADRs, diagramas
ops/                        infraestrutura: backup, setup, deploy
scripts/                    SOMENTE ferramentas de desenvolvimento
```

Decisoes principais:

- **namespace unico `apps.*`**: `apps/` vira pacote Python (`__init__.py`), o
  `sys.path.insert(0, .../apps)` de `config/settings.py` (linha 34) e
  removido e `INSTALLED_APPS` passa a listar `apps.core`, `apps.clientes`,
  etc. Corrige um defeito latente encontrado em 2026-07-29: hoje cada app e
  importavel como `core` **e** como `apps.core` (76 imports usam a primeira
  forma, 49 a segunda), e o dia em que um model for importado pelo caminho
  com prefixo o Django passa a ter duas copias da mesma classe. O
  `app_label` nao muda (o Django usa o ultimo componente do caminho), entao
  tabelas e migrations permanecem intactas;
- **padrao interno de app**: `models · views (fina) · services/ · forms ·
  urls · admin · management/commands/ · tests/`. View nao chama integracao
  direto — o caminho e sempre `view -> service -> gateway`;
- **camada de integracao**: pacote unico `apps/integracoes/` com uma
  subpasta por sistema externo. Sem Manager, Registry ou `BaseProvider` —
  cada servico importa diretamente o gateway de que precisa (mantem o item
  10 da ADR-006). A subpasta separa responsabilidades dentro de cada
  sistema, nao habilita troca dinamica de provider;
- **`scripts/` deixa de conter codigo de producao**: rotina agendada e
  automacao pertencem a um app (com management command como entrypoint);
  infraestrutura vai para `ops/`; `scripts/` fica so com ferramenta de
  investigacao manual (`ixc_explorador.py`, `debug_*`). Hoje seis rotinas de
  producao sao chamadas por caminho de arquivo no `docker-compose.yml` e dez
  scripts fazem bootstrap manual do Django. **Quando/como migrar nao foi
  decidido** — exige alterar `docker-compose.yml` e validar cron em
  producao (DevOps).

O mapa completo de origem -> destino de cada modulo esta na propria ADR-007.
Nenhuma feature de execucao foi criada no backlog por essa decisao.

## Objetivo (API publica)

Consolidar as decisoes arquiteturais da camada publica de API do projeto.

## Estado atual

O sistema ja possui:

- modulo dedicado `integracoes_api`;
- namespace `/api/v1/`;
- endpoints publicos de leitura;
- schema OpenAPI;
- Swagger UI.

Neste estado, a API foi entregue como fundacao tecnica e ainda nao possui autenticacao de producao.

## Decisao arquitetural atual

### API publica v1 com JWT e contas tecnicas

A API publica deve adotar autenticacao baseada em `JWT`, emitida somente para `contas tecnicas`.

Essa decisao existe para separar:

- usuarios humanos do sistema web interno;
- consumidores de integracao sistema-a-sistema.

## Principios da arquitetura

- toda rota de negocio da API deve exigir autenticacao;
- tokens so podem ser emitidos para contas tecnicas autorizadas;
- Swagger e schema nao devem permanecer publicos em producao;
- a API publica nao deve reutilizar sessao web como mecanismo principal de integracao;
- o modulo `integracoes_api` continua sendo a unica fronteira de integracao externa.

## Fronteira de acesso

### Rotas publicas permitidas

- `POST /api/v1/auth/token/`
- `POST /api/v1/auth/token/refresh/`
- `GET /api/v1/health/`

### Rotas protegidas por JWT

- `GET /api/v1/`
- `GET /api/v1/clientes/`
- `GET /api/v1/clientes/<id>/`
- `GET /api/v1/clientes/<cliente_pk>/enderecos/`
- `GET /api/v1/parceiros/`
- `GET /api/v1/propostas/`
- `GET /api/v1/propostas/<id>/`

### Rotas protegidas ou desabilitadas em producao

- `GET /api/v1/schema/`
- `GET /api/v1/swagger/`

Diretriz:
- em desenvolvimento e homologacao, podem existir para usuarios autenticados;
- em producao, devem ficar restritas a administradores internos ou desabilitadas por configuracao.

## Modelo de identidade

### Conta tecnica

A conta tecnica deve reutilizar o model `core.User` existente, sem criar novo model nesta fase.

Padrao recomendado:

- username com prefixo `svc_` ou `int_`;
- `is_active = True`;
- sem uso operacional humano;
- senha forte gerada e armazenada de forma segura;
- vinculacao a grupo dedicado de integracao.

### Grupo tecnico recomendado

Criar um grupo dedicado:

- `api_integracao_publica`

Somente usuarios deste grupo podem:

- obter token da API publica;
- consumir endpoints protegidos da API publica.

## Fluxo de autenticacao

### Fluxo de emissao

1. Sistema integrador envia usuario tecnico e senha para `POST /api/v1/auth/token/`
2. API valida:
   - usuario ativo;
   - pertencimento ao grupo `api_integracao_publica`
3. API retorna:
   - `access`
   - `refresh`

### Fluxo de consumo

1. Sistema integrador envia header `Authorization: Bearer <access_token>`
2. API valida o JWT
3. API libera apenas endpoints protegidos e documentados

### Fluxo de renovacao

1. Sistema integrador chama `POST /api/v1/auth/token/refresh/`
2. API retorna novo `access`

## Politica de tokens

Configuracao recomendada:

- `access token`: 30 minutos
- `refresh token`: 7 dias
- rotacao de refresh: habilitada
- blacklist/revogacao: habilitada se a dependencia escolhida suportar com custo aceitavel

Motivo:
- reduz risco de exposicao prolongada;
- continua viavel para integracao automatizada;
- permite revogacao operacional mais clara.

## Permissoes

### Regra padrao

Toda view de negocio da API deve usar:

- autenticacao JWT
- permissao de usuario autenticado
- validacao adicional de conta tecnica autorizada

### Validacao adicional recomendada

Criar permissao customizada equivalente a:

- usuario autenticado
- usuario ativo
- pertencente ao grupo `api_integracao_publica`

Isso evita:

- uso de contas humanas comuns para integracao;
- emissao de token para qualquer usuario do sistema.

## Swagger e schema

### Decisao

Swagger e schema nao devem ficar publicos em producao.

Comportamento recomendado:

- dev/hml: disponivel somente para usuario autenticado interno;
- prod: desabilitado ou restrito a administradores internos.

## Dependencia recomendada

Nome:
- `djangorestframework-simplejwt`

Motivo:
- implementa JWT de forma padronizada no ecossistema Django/DRF;
- reduz codigo customizado de seguranca;
- oferece rotas e classes prontas para emissao e refresh.

Alternativa sem dependencia:
- implementar JWT manualmente no projeto.

Por que nao recomendo a alternativa:
- aumenta risco de seguranca;
- aumenta custo de manutencao;
- adiciona responsabilidade criptografica sem necessidade.

Impacto em deploy:

- adicionar dependencia Python;
- configurar settings de JWT;
- validar ambiente Docker/imagem;
- eventualmente habilitar blacklist se adotada.

Agente recomendado para executar:
- `backend_django`

## Impactos tecnicos esperados

- alteracao de configuracao global do DRF;
- criacao de rotas de autenticacao;
- mudanca de permissao nas views da API;
- possivel ajuste do Swagger para suportar Bearer token;
- inclusao de testes de autenticacao e autorizacao.

## Fora desta fase

- OAuth2 client credentials;
- multi-tenant de credenciais por parceiro com model dedicado;
- rate limiting por chave;
- escopos finos por recurso;
- portal de autoatendimento para emissores de credenciais.

## Evolucao futura recomendada

Fase posterior possivel:

- criar entidade propria de cliente de integracao;
- mapear cada integracao a parceiro/sistema;
- incluir expiracao administrativa e rotacao de segredo;
- auditar consumo por cliente tecnico.

## Configuracao de menu de automacoes

### Estado atual

Cada automacao tem seu link de menu fixo no template (`core/templates/core/base.html`), apontando para a URL especifica do app que a implementa (ex.: `core_admin`, `backoffice`). Mover uma automacao de um menu para outro exige editar o template (e possivelmente `urls.py`) e fazer novo deploy.

### Decisao

Toda automacao passa a ter um registro de configuracao de menu, com **Administrador como padrao**, permitindo realocar a automacao para outro menu (Backoffice, LastMile, Parceiro) sem alterar template ou fazer deploy.

### Modelo

Novo model, originalmente criado em `core_admin` (nome sugerido: `AutomacaoMenu`;
movido para `apps/core` pela PO-036 em 2026-07-29, aguardando QA — ver ADR-007
item 8, registro de menu/permissao e considerado camada 0):

- `slug`: identificador unico da automacao (ex.: `resolucao_os_atendimento`);
- `nome_exibicao`: rotulo mostrado no menu;
- `menu`: choices (`administrador`, `backoffice`, `lastmile`, `parceiro`), padrao `administrador`;
- `url_name`: nome da rota Django da automacao;
- `ativo`: booleano, permite ocultar sem remover o registro;
- `ordem`: inteiro opcional, para ordenacao dentro do menu.

### Renderizacao do menu

`core/templates/core/base.html` deixa de ter `<a>` fixo por automacao. Cada bloco de menu (Administrador, Backoffice, LastMile, Parceiro) passa a iterar a lista de `AutomacaoMenu` ativos daquele menu, resolvida via `url_name`, respeitando a mesma verificacao de grupo/permissao ja existente no template.

### Alteracao da configuracao

Somente usuario com permissao de Administrador pode alterar o `menu` de uma automacao existente. Recomenda-se uma tela simples dentro do proprio `core_admin` (ou Django Admin, se suficiente para o volume atual) para essa alteracao, sem exigir nova decisao de arquitetura para o CRUD basico.

### Impactos tecnicos esperados

- nova migration para o model `AutomacaoMenu`;
- migracao de dados (data migration ou seed) para registrar as automacoes ja existentes (import de prospects, automacoes de Backoffice IXC) com seus menus atuais;
- refatoracao de `core/templates/core/base.html` para renderizar automacoes a partir do model em vez de links fixos;
- possivel view/action de configuracao restrita a Administrador.

### Fora desta fase

- reordenacao visual arrastavel (drag-and-drop) do menu;
- multiplos menus simultaneos para a mesma automacao;
- historico/auditoria de mudanca de menu.

## Integracoes IXC — Backoffice

### Estado atual

O Backoffice concentra um conjunto de automacoes que integram com o sistema externo IXC via API. Cada automacao segue o mesmo padrao arquitetural:

- **Cliente HTTP compartilhado**: `apps/integracoes/ixc/client.py` (`IXCClient`) centraliza a comunicacao com a API do IXC (PO-033, aguardando QA; antes em `apps/core/ixc_client.py` pela PO-026);
- **Modulo de regras por automacao**: `apps/integracoes/ixc/services/` contem um arquivo por automacao (ex.: `cadastrar_cliente_ixc.py`, `cria_atendimento_ixc.py`, `cria_login_atendimento.py`), com validacao, normalizacao de dados e montagem de payload isoladas da camada web (PO-033, aguardando QA; antes em `apps/core/integracoes_ixc/` pela PO-036);
- **Views Django**: `apps/backoffice/views.py` orquestra upload de planilha, validacao previa ("tudo ou nada"), chamada ao modulo de regras, geracao do relatorio Excel de retorno e registro de auditoria;
- **Auditoria compartilhada**: `apps/core/integration_audit.py` e os models `core.IntegrationAudit`/`IntegrationAuditItem` (`apps/core/models.py`) registram toda execucao (usuario, arquivo, totais de sucesso/erro) e o detalhe por linha, consultavel na tela de Central de Automacoes;
- **Controle de acesso por automacao**: `apps.core.automacoes_registry` (`permissao_automacao`) resolve a permissao de grupo por automacao, reutilizando o model `AutomacaoMenu` ja documentado acima (movido de `core_admin` para `apps/core` pela PO-036, aguardando QA — ver ADR-007 item 8);
- **Credenciais via variavel de ambiente**: `IXC_PANEL_EMAIL`, `IXC_PANEL_PASSWORD`, `IXC_URL`, `IXC_TOKEN`, configuradas em `docker-compose.yml`/`.env`, nunca hardcoded.

### Exemplo de fluxo — Cadastro de Cliente IXC

1. Upload da planilha em `cadastrar_clientes_ixc` (`apps/backoffice/views.py`);
2. validacao previa linha a linha em `validar_linha_pre_envio`, incluindo deteccao de CNPJ/CPF duplicado dentro da planilha (`detectar_cnpj_duplicado_na_planilha`) e contra o IXC (`verificar_duplicidade_ixc`) — ver RN-015/RN-016 em `business_rules.md`;
3. planilha reprovada por completo se qualquer linha falhar (padrao "tudo ou nada"), sem chamada de escrita ao IXC;
4. envio linha a linha via `executar_cadastro_cliente_ixc`, com registro em `IntegrationAudit`/`IntegrationAuditItem`;
5. retorno de relatorio Excel com status, mensagem e `ID_IXC` por linha.

### Riscos e decisoes conhecidas

- a validacao previa faz uma chamada ao IXC por linha para checar duplicidade, tornando a validacao mais lenta — aceito deliberadamente para antecipar erros antes do envio (RN-016);
- duplicidade e verificada por CNPJ/CPF e, no fallback, por razao social; o bloqueio por padrao e mantido mesmo em casos de CNPJ compartilhado entre entidades distintas (ex.: orgaos publicos), cabendo a `Permitir_Duplicidade = Sim` liberar o cadastro intencional (RN-015).

### Fora desta fase

- client IXC assincrono ou com retry/circuit breaker dedicado;
- cache de consultas de duplicidade entre execucoes;
- desacoplamento do `IXCClient` em servico HTTP proprio fora do monolito Django.

## Expansao modular - modulo 2, kill switch e fila (ADR-006)

Decisao registrada em `docs/adr/ADR-006_EXPANSAO_MODULAR_MODULO_2.md`:

- novos setores da empresa entram como um pacote de apps Django agrupado
  (`apps/modulo2/<setor>/`), dentro do mesmo monolito - sem novo deploy;
- dependencia em uma via so: apps do modulo 2 podem importar de apps do
  sistema atual, nunca o contrario;
- kill switch (`MODULO2_ATIVO`) bloqueia interface e jobs de fundo do modulo
  2 quando desligado, sem afetar o sistema atual;
- envio de dados ao IXC usa uma tabela de fila intermediaria sem message broker:
  Servicos grava -> Rotina de envio le e chama o IXCGateway - mantem a
  decisao da ADR-005 de nao introduzir broker nesta fase;
- webhook do IXC para atendimento/O.S./cliente foi avaliado e **descartado**
  em 2026-07-28: documentacao publica, teste de leitura na API real e
  navegacao direta no painel da conta convergiram para a mesma conclusao -
  nao existe (o unico gatilho/webhook do IXC e do modulo financeiro,
  pagamento);
- entrada de O.S. (sem webhook) segue por polling agendado
  (`ixc_primeira_os.py` - rotina separada do sync de cliente/login, em
  ritmo proprio), mas passa a gravar em tabela de fila intermediaria de entrada
  em vez de consumir direto - rotina de consumo separada aplica a regra de
  dominio (emenda 2026-07-28, item 7 da ADR-006), espelhando o padrao ja
  usado na saida. Chama a API do IXC diretamente via `IXCClient`
  (`apps/core/ixc_client.py`). **Agendamento hoje: nenhum** - o script
  existe mas nao ha cron/loop configurado no `docker-compose.yml` nem
  gatilho no Admin; roda somente sob execucao manual. **Agendamento
  proposto para esta fase** (valor-alvo, a validar quando a automacao for
  construida): reaproveitar o mesmo loop de polling do servico
  `speed_sincronizador` (`docker-compose.yml`, servico que ja rotaciona os
  demais scripts IXC por hora), no mesmo ritmo do incremental de
  cliente/login - a cada 4h (00/04/08/12/16/20) - por ser o padrao
  operacional ja usado nesta fase para entradas via polling, mantendo uma
  unica cadencia previsivel entre as integracoes IXC. Pendencia: confirmar
  esse valor com o time quando a automacao concreta for desenhada;
- entrada de cliente/login (`ixc_api_incremental.py`/`ixc_sync_clientes.py`),
  que hoje grava direto no dominio, passa pelo mesmo padrao: rotina de
  busca grava em tabela de fila intermediaria propria, rotina de consumo separada
  aplica `salvar_clientes_no_django` (decisao ampliada 2026-07-28, item 7).
  Chama a API do IXC diretamente via `IXCClient`. **Agendamento hoje**
  (real, ja em produção via `docker-compose.yml`, servico
  `speed_sincronizador`): sincronizacao incremental a cada 4h
  (00/04/08/12/16/20) e carga total 1x/dia as 23h; tambem acionavel
  manualmente pelo Admin Django (`apps/clientes/admin.py`);
- fechamento de O.S. no IXC tenta um fast path sincrono (timeout curto)
  e, se falhar, cai para a mesma tabela de fila intermediaria de saida
  (idempotente, com status de sincronizacao visivel na O.S.) para
  reprocessamento pela rotina agendada - sem bloquear o fechamento local
  e sem introduzir Celery/Redis (item 8 da ADR-006). Fast path e
  reprocessamento chamam a API do IXC diretamente via `IXCClient` (nao ha
  API propria do sistema nessa etapa). **Automacao ainda nao construida**
  nesta fase - nao ha script/rotina hoje; agendamento proposto (valor-alvo):
  mesmo padrao dos demais reprocessamentos de fila intermediaria desta fase, com
  intervalo curto (ex.: a cada 5-10 minutos, dado que e reprocessamento de
  falha e nao carga completa) - pendencia a confirmar quando a automacao
  concreta for desenhada;
- as tres tabelas de fila intermediaria (entrada O.S., entrada cliente/login,
  saida O.S.) compartilham o mesmo formato de status/erro (`pendente` /
  `processando` / `concluido` / `erro`, com mensagem de erro e contador de
  tentativas na propria linha, via classe abstrata Django comum - sem
  tabela de log separada nesta fase) (item 9 da ADR-006);
- escopo funcional confirmado nesta fase: entrada de O.S., entrada de
  cliente/login e fechamento de O.S.; demais automacoes de Backoffice/
  Modulo 2 ficam para quando houver escopo concreto;
- avaliadas em 2026-07-29 as ideias de "Integration Hub" propostas pelo
  usuario (`melhorias_arquitetura.md`, item 10 da ADR-006): aceito adicionar
  `correlation_id` (opcional) na classe abstrata comum das tres tabelas de
  fila intermediaria (item 9), ligando cada linha ao `IntegrationAudit`/
  requisicao de origem; descartados message broker/fila dedicada,
  `Integration Manager`/`Registry` genericos, scaffolding de `providers/`
  para sistemas sem automacao real (Correios/OpenAI/WhatsApp), interface
  `BaseProvider` comum e camada formal de Mapper/DTO - todos contradizem
  decisao ja aprovada (ADR-005/ADR-006) ou sao abstracao prematura para o
  estagio atual (um unico gateway real maduro, o IXC); painel de
  reprocessamento manual das linhas em `erro` registrado como pendencia
  futura.

Pendente: setores do modulo 2; nome e campos especificos de cada tabela
de fila intermediaria (alem do formato comum de status/erro e do
`correlation_id` ja decididos); modelo do status de sincronizacao/idempotencia
do fechamento; painel de reprocessamento manual. Ver
`docs/adr/ADR-006_EXPANSAO_MODULAR_MODULO_2.md`.

## Portal de documentacao interna (rota publica de documentos)

### Decisao

Criar uma rota HTML dentro do sistema (ex.: `/docs/`) que lista links para os
documentos tecnicos do projeto (diagramas de arquitetura, ADRs em HTML etc.),
comecando pelo diagrama `docs/diagrams/adr-006-expansao-modular.html`.

- rota sem autenticacao/permissao — decisao explicita do usuario em
  2026-07-28, por se tratar apenas de documentacao tecnica interna, sem dado
  de negocio, credencial ou informacao de cliente;
- pagina unica com lista de links, estruturada para receber novos documentos
  no futuro sem redesenho da pagina;
- primeiro documento listado: diagrama da ADR-006.

### Fora desta fase

- controle de acesso/autenticacao;
- geracao automatica da lista a partir do sistema de arquivos (definir na
  implementacao se a lista sera mantida manualmente pelo Dev ou lida do
  diretorio `docs/diagrams/`);
- versionamento/historico de documentos.

### Legenda das setas no diagrama (`docs/diagrams/adr-006-expansao-modular.html`)

- **Verde solido**: a chamada toca o IXC - atravessa a fronteira externa via
  `IXCGateway` (ex.: `IXCGateway -> IXC`, `Servicos -> IXCGateway`);
- **Cinza solido**: chamada interna, fica dentro do proprio sistema, nunca
  sai para o IXC (ex.: `Consumo -> Servicos`, `Modulo 2 -> Servicos`);
- **Vermelho tracejado**: nao e uma chamada normal - e caminho de
  falha/fallback (`Servicos -> fila intermediaria de saida`, so quando a chamada
  sincrona falha) ou uma relacao de controle/gate (`Kill switch -> Modulo 2`).
