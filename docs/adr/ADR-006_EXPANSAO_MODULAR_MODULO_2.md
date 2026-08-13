# ADR-006 - Expansao modular: modulo 2, kill switch e padrao de fila para IXC

## Status

`Aprovado`

## Contexto

O sistema vai crescer para atender novos setores da empresa e novas
integracoes com o IXC, alem do escopo atual (Backoffice/LastMile). O usuario
levantou seis ideias para essa proxima fase; esta ADR registra as decisoes
que ja podem ser tomadas agora, antes de qualquer setor novo estar definido.

A `ADR-005` ja aprovou a evolucao para monolito modular em camadas, sem
microsservicos, API Gateway dedicado ou message broker nesta fase. Esta ADR
nao contradiz a ADR-005; detalha como a proxima fase de crescimento se encaixa
nela.

## Decisao

### 1. Gateway unico por sistema externo (ja em execucao, sem decisao nova)

A unificacao do acesso ao IXC em um unico `IXCClient` ja e o padrao aprovado
pela ADR-005 e esta quase concluida (PO-022, PO-025, PO-026). Nao ha decisao
nova aqui; ver secao "Integracoes IXC - Backoffice" em `docs/ARCHITECTURE.md`.

### 2. "Modulo 2" como pacote de apps Django agrupado, dentro do mesmo monolito

Novos setores nao geram um projeto/deploy separado (isso seria microsservico,
descartado pela mesma razao da ADR-005). Passam a viver em um pacote de apps
Django dedicado, agrupado sob um diretorio proprio (ex.: `apps/modulo2/<setor>/`),
seguindo a mesma convencao de app Django ja usada por `core`, `backoffice`,
`partners`, etc.

A escolha de quais setores entram fica para quando a primeira automacao do
modulo 2 for definida. A **estrutura interna** de cada app deixou de ser
questao em aberto: a `ADR-007` (2026-07-29) define o padrao obrigatorio
(`models · views finas · services/ · management/commands/ · tests/`, sob o
namespace unico `apps.*`). O primeiro app do Modulo 2 deve nascer ja nesse
padrao, sem copiar as excecoes atuais do sistema.

### 3. Dependencia em uma via so: modulo 2 depende do sistema atual, nunca o contrario

Regra: apps dentro de `apps/modulo2/` podem importar de apps do sistema atual
(`core`, `core_admin`, `backoffice`, `partners`, `leads`, `integracoes_api`).
Nenhum app do sistema atual pode importar de `apps/modulo2/`.

Isso garante que o sistema atual continue funcionando de forma independente,
mesmo que o modulo 2 seja removido ou desligado.

Aplicacao da regra:
- nesta fase, verificacao manual em code review (buscar imports de
  `apps.modulo2` fora do proprio pacote);
- se o volume de apps no modulo 2 crescer o suficiente para tornar a
  verificacao manual arriscada, avaliar com o DevOps uma ferramenta de lint
  de import (ex.: `import-linter`) no CI. Fora do escopo desta ADR.

### 4. Kill switch do modulo 2: bloqueia interface e jobs de fundo

Decisao do usuario: desligar o modulo 2 deve bloquear tanto a interface
quanto qualquer automacao/job de fundo dele, sem afetar o sistema atual.

Mecanismo recomendado:
- uma flag mestre (`MODULO2_ATIVO`, variavel de ambiente lida em
  `settings.py`), independente do padrao existente `AutomacaoMenu.ativo`
  (que continua valendo para ligar/desligar automacoes individuais dentro de
  um modulo ja ativo);
- quando `MODULO2_ATIVO = False`:
  - menus e URLs do modulo 2 nao sao registrados/renderizados;
  - toda rotina de fundo (management command, tarefa agendada) do modulo 2
    verifica a flag no inicio e encerra sem executar, com log claro do motivo;
- o sistema atual (modulo 1) nao le nem depende dessa flag - continua
  funcionando normalmente com o modulo 2 desligado, por construcao (ver
  secao 3).

### 5. Padrao de "fila" para envio ao IXC: tabela de fila intermediaria no banco, sem broker nesta fase

Correcao de desenho registrada em 2026-07-28: a primeira versao desta ADR
tratava a chegada de dados do IXC como polling (uma rotina buscando dados via
`IXCClient`) e propunha, para a direcao de entrada, um fluxo por webhook. O
item 6 abaixo confirma que o IXC nao oferece webhook para atendimento/O.S.
/cliente nesta conta - por isso o padrao de fila desta ADR cobre somente a
direcao de **saida** (sistema -> IXC), que nao depende dessa confirmacao:

```text
SAIDA (sistema -> IXC)
  Servicos/Dominio grava em tabela de saida (status = pendente)
        |
  Rotina de envio (agendada) le pendentes e chama IXCGateway (IXCClient)
        |
  IXCGateway -> IXC (webservice/v1)
```

- as rotinas nao se chamam diretamente; toda comunicacao passa pela tabela
  de fila intermediaria com campo de status;
- falha na gravacao (quem enfileira) nao impede a rotina de envio de
  processar o que ja esta gravado, e vice-versa;
- cada integracao de saida que precisar desse padrao cria sua propria
  tabela de fila intermediaria (nome e campos a definir por feature, quando a
  automacao concreta for desenhada) - nao ha um "barramento" generico nesta
  fase;
- mantem a decisao da ADR-005 de nao introduzir message broker nesta fase.
- **entrada de dados do IXC continua pelo sync incremental agendado**
  (`ixc_api_incremental.py`), sem tabela de fila intermediaria de entrada - ver
  item 6 para o motivo.

Fora desta fase (reavaliar somente se aparecer necessidade real):
- Celery/RQ/Redis ou qualquer message broker dedicado;
- retry automatico granular por item (a tabela de fila intermediaria permite retry
  manual/por reprocessamento do lote, nao retry automatico com backoff);
- fan-out para multiplos consumidores concorrentes do mesmo lote.

### 6. Webhook do IXC: confirmado que nao existe para atendimento/O.S./cliente - fila de entrada descartada

A hipotese original (item 5) era ter uma direcao de entrada via webhook do
IXC (IXC -> API -> tabela de entrada -> rotina de consumo). Essa hipotese
foi verificada e **descartada** em 2026-07-28, com tres fontes
independentes convergindo para a mesma conclusao:

1. **Documentacao publica do IXC**: o unico cadastro de "Webhook" descrito
   nos guias oficiais (central de ajuda e wiki do IXC) e vinculado a
   convenio de cobranca (integracoes bancarias Sicoob, Sicredi, Banco do
   Brasil, Asaas, BTG - notificacao de boleto/Pix pago). Nenhuma pagina
   publica descreve webhook para atendimento, O.S. ou cliente.
2. **Teste de leitura na API real do projeto** (`apps/core/ixc_client.py`,
   `IXCClient().listar(...)`, somente leitura): os nove nomes de tabela
   candidatos a uma configuracao de webhook (`webhook`, `cadastro_webhook`,
   `webhook_evento`, `evento_webhook`, `su_webhook`, `notificacao_webhook`,
   `webhook_assunto`, `assunto_webhook`, `webhook_evento_tipo`) retornaram
   todos o mesmo erro de recurso inexistente que uma tabela deliberadamente
   invalida usada como controle; a chamada de controle a tabela `cliente`
   (existente) retornou dados reais, confirmando que a API respondia
   normalmente.
3. **Navegacao direta no painel web da conta IXC do usuario** (menu de
   engrenagem > Rotinas): nao existe nenhum item de menu chamado
   "Webhook". O unico conceito equivalente encontrado e "Reenviar gatilhos
   lugu", dentro de **Rotinas gateway** (Rotinas financeiro) - reenvio de
   notificacao de pagamento do gateway Lugu/Cel Payments, escopo
   estritamente financeiro. **Rotinas atendimento|OS** (o modulo que mais
   se aproximaria do dominio que as automacoes de Backoffice tocam) so
   tem dois utilitarios de preenchimento de campo ("Preencher cidade (OS)",
   "Preencher Data de Emissao Pedido de OS") - nenhuma feature de
   notificacao, callback ou integracao externa.

Conclusao: **confirmado que o IXC nao oferece webhook para atendimento,
O.S. ou cliente nesta conta.** O unico mecanismo de "gatilho"/webhook
existente e exclusivo do modulo financeiro (gateways de pagamento).

Decisao: a fila de entrada via webhook descrita na primeira versao desta
ADR e **descartada**. Reabrir a hipotese de webhook somente se o IXC
lancar suporte para esses eventos no futuro (ex.: nova versao da API,
anuncio oficial) - nao reavaliar por especulacao.

**Emenda 2026-07-28 (mesmo dia, apos revisao com o usuario):** a frase
acima "sem tabela de entrada... nada muda em relacao ao que ja existe" e
**substituida** pelo item 7 abaixo. O que fica mantido desta secao e
somente a confirmacao de que nao ha webhook do IXC para atendimento/O.S.
/cliente - o mecanismo de entrada (polling agendado) continua o mesmo,
mas passa a gravar em tabela de fila intermediaria em vez de consumir direto.

### 7. Entrada de O.S. tambem usa tabela de fila intermediaria - simetria com a saida

Correcao de desenho, mesmo dia da aprovacao original desta ADR: **correcao
de referencia em 2026-07-28** - a rotina de busca de O.S. e
`scripts/integracoes/ixc_primeira_os.py` (enriquece o login/endereco ja
sincronizado com ticket/primeira O.S., em ritmo proprio), **nao**
`ixc_api_incremental.py` (esse e o sync de cliente/login via
`ixc_sync_clientes.py`, escopo diferente - ver Pendencia abaixo).

A rotina de busca de O.S. continua fazendo polling agendado (sem webhook,
conforme item 6), mas deixa de consumir/processar os dados no mesmo passo.
Passa a gravar o que buscou em uma tabela de fila intermediaria de entrada
(status `pendente`), e uma rotina de consumo separada le essa tabela e
aplica a regra de dominio:

```text
ENTRADA (IXC -> sistema)
  Rotina de busca (agendada, polling) le o IXC via IXCGateway
        |
  Grava em tabela de fila intermediaria de entrada (status = pendente)
        |
  Rotina de consumo (agendada) le pendentes e aplica regra de dominio
```

Motivo: falha ou lentidao na etapa de consumo (regra de dominio) nao deve
impedir a proxima busca agendada de rodar, e vice-versa - o mesmo
principio ja aplicado a saida (item 5), agora espelhado na entrada. Nao
reabre a decisao do item 6: continua sem webhook, continua sem broker.

Fora desta fase: nome e campos exclusivos da tabela de fila intermediaria de
entrada de O.S. ficam para quando a automacao concreta de consumo for
desenhada (o formato comum de status/erro esta decidido no item 9).

**Decisao (2026-07-28, escopo ampliado a pedido do usuario):** o sync de
cliente/login (`ixc_api_incremental.py` / `ixc_sync_clientes.py`), hoje
gravando direto no dominio (`salvar_clientes_no_django`), passa a seguir
o mesmo padrao: a rotina de busca grava em tabela de fila intermediaria de
entrada de cliente/login (status `pendente`), e uma rotina de consumo
separada aplica `salvar_clientes_no_django`. Motivo do usuario: cliente/
login e um dado de entrada tao fundamental quanto O.S. (input basico do
sistema), e merece o mesmo isolamento de falha entre busca e gravacao.
Escopo desta fase passa a ser: entrada de O.S., entrada de cliente/login
e fechamento de O.S. - nenhuma outra automacao de Backoffice/Modulo 2
entra ainda.

### 8. Fechamento de O.S. no IXC: tentativa sincrona com fallback pela fila intermediaria de saida ja aprovado

O fechamento de O.S. deve refletir no IXC o mais proximo possivel de
instantaneo, mas sem que uma falha ou indisponibilidade do IXC quebre o
fechamento no sistema. Desenho aprovado:

1. **Fast path sincrono**: ao fechar a O.S. no sistema, tenta chamar o
   `IXCGateway` na hora, com timeout curto (poucos segundos). Se
   responder OK, fechado nos dois lados - percebido como instantaneo.
2. **Fallback assincrono**: se a chamada falhar (timeout, erro, IXC fora
   do ar), grava na mesma tabela de fila intermediaria de saida do item 5
   (status `pendente`/`falha`), sem bloquear nem reverter o fechamento
   local. A rotina de envio agendada (ja existente) reprocessa depois -
   nao e necessaria nova infraestrutura.
3. **Idempotencia**: a chamada de fechamento (tanto no fast path quanto
   no reprocessamento) deve ser identificada por uma chave estavel (ex.:
   ID da O.S.), para que um reprocessamento tardio nao feche a mesma O.S.
   duas vezes no IXC.
4. **Status de sincronizacao visivel**: a O.S. local ganha um campo de
   status de sincronizacao com o IXC (ex.: sincronizado / pendente /
   falha), consultavel - evita que a operacao presuma uma sincronizacao
   que ainda nao aconteceu.

Isso reaproveita integralmente o padrao ja aprovado no item 5 (tabela de
fila intermediaria + rotina agendada), sem reabrir a alternativa descartada de
introduzir Celery/Redis nesta fase.

### 9. Formato comum de status/erro nas tabelas de fila intermediaria

Com a decisao do item 7 (ampliada), esta fase passa a ter tres tabelas de
fila intermediaria: entrada de O.S., entrada de cliente/login e saida de O.S.
As tres precisam responder a mesma pergunta operacional: "isso ja chegou/
foi enviado? ja foi processado? deu erro? qual foi o erro?". Decisao: as
tres compartilham o mesmo formato de campos, para que o sistema saiba,
por item, se a informacao chegou no IXC (saida) ou do IXC (entrada) e se
a rotina de consumo/envio ja passou por ela ou nao:

- `status`: `pendente` | `processando` | `concluido` | `erro`;
- `mensagem_erro`: texto do ultimo erro, preenchido somente quando
  `status = erro`;
- `tentativas`: contador de tentativas de processamento/envio;
- `criado_em` / `atualizado_em`: quando o item entrou na fila e quando o
  status mudou pela ultima vez.

O erro fica **na propria tabela de fila intermediaria** (campo `mensagem_erro`
+ `tentativas`), nao em uma tabela de log separada. Motivo: cada linha ja
mostra o estado atual e o ultimo erro de forma consultavel, sem exigir
join; criar uma tabela de log separada so se justifica se for necessario
o historico completo de todas as tentativas (nao so a ultima) - isso fica
fora desta fase, retomar somente se aparecer necessidade real de auditoria
tentativa-a-tentativa.

Como as tres tabelas compartilham o mesmo formato, evitar copiar as
quatro colunas acima em cada uma: usar uma classe abstrata Django comum
(ex.: `StagingBase`, `abstract = True`) com esses campos, e cada
tabela concreta (entrada O.S., entrada cliente/login, saida O.S.) herda
dela e adiciona so os campos especificos do seu dominio (payload, chave
de idempotencia, etc.). Isso nao cria um "barramento" generico nem uma
tabela polimorfica unica - continuam sendo tres tabelas fisicas
separadas, so compartilhando a definicao dos campos comuns em codigo.

Fora desta fase: tabela de log de tentativas historicas; alertas
automaticos por volume de `erro` (fica com o DevOps, se necessario).

### 10. Avaliacao do "Integration Hub" (`melhorias_arquitetura.md`) - aceito em parte

O usuario registrou em 2026-07-29 uma proposta mais ampla de arquitetura de
integracoes ("Integration Hub"): pacote `integration/` com `manager/`,
`registry/`, `queue/` com broker dedicado, um `providers/` por sistema externo
(IXC, Google, Correios, e-mail, OpenAI, WhatsApp) com `client`/`auth`/
`endpoints`/`mapper`/`services`/`dto`/`tasks`, interface comum `BaseProvider`
e uma tabela unica `integration_jobs` para historico. Avaliada item a item
contra o que ja esta decidido (ADR-005 e itens 1-9 desta ADR) e o codigo real.

**Aceito (adicionado nesta emenda):**
- campo `correlation_id` (opcional) na classe abstrata comum `StagingBase`
  do item 9 - permite ligar uma linha de fila intermediaria (entrada ou
  saida) ao registro de `IntegrationAudit` ou a requisicao que a originou,
  sem exigir nova infraestrutura de observabilidade.

**Registrado como pendencia futura (nao decidido nem construido agora):**
- painel de reprocessamento manual para linhas em status `erro` das tabelas
  de fila intermediaria - depende de as automacoes concretas dos itens 7 e 8
  (entrada de O.S., entrada de cliente/login, fechamento de O.S.) estarem
  construidas primeiro; reavaliar quando isso acontecer.

**Descartado (contradiz decisao ja aprovada ou e prematuro para o estagio
atual):**
- `Integration Manager` + `Registry` genericos para localizar provider por
  string: com 3-4 sistemas externos reais conhecidos hoje (IXC, Active
  Directory, e-mail, Google/lastmile), um import direto do gateway
  especifico e mais simples que uma camada de indirecao dinamica - mesma
  razao da ADR-005 contra microservicos/API Gateway dedicado;
- pacote `queue/` com broker dedicado (publisher/consumer/dispatcher,
  Celery/Redis/RabbitMQ): contradiz diretamente a decisao ja tomada no item 5
  desta ADR e na ADR-005 de nao introduzir message broker nesta fase;
- tabela unica `integration_jobs` (polimorfica, compartilhada entre
  providers): contradiz a decisao do item 9 desta mesma ADR de manter
  tabelas fisicas separadas por integracao com uma classe abstrata comum,
  exatamente para evitar um modelo generico/polimorfico unico;
- `providers/` com estrutura completa (client/auth/endpoints/mapper/
  services/dto/tasks) para sistemas sem nenhuma automacao concreta hoje
  (Correios, OpenAI, WhatsApp): desenho para requisito hipotetico, sem setor
  do Modulo 2 ou automacao real que precise deles (CLAUDE.md - nao inventar
  requisito); revisitar somente quando um desses sistemas tiver automacao
  real definida;
- interface `BaseProvider` (`authenticate`/`execute`/`validate`) comum a
  todos os gateways: abstracao prematura com um unico gateway real maduro
  (IXC); reavaliar quando um segundo ou terceiro gateway real compartilhar
  contrato suficiente para justificar uma interface comum;
- camada formal de `Mapper`/`DTO` por provider: a normalizacao equivalente
  ja existe de forma pontual (ex.: normalizacao de UF/cidade/filial em
  `ixc_sync_clientes.py`); formalizar como camada separada somente se a
  duplicacao reaparecer entre integracoes;
- Prometheus/Grafana/OpenTelemetry/dashboard de integracoes: infraestrutura
  de observabilidade fica fora do escopo de arquitetura de dominio desta
  ADR; cabe ao DevOps avaliar quando houver necessidade real (CLAUDE.md -
  fronteira de responsabilidade);
- healthcheck dedicado ao Integration Hub: ja existe equivalente
  (`GET /api/v1/health/`, ver `docs/ARCHITECTURE.md`), sem necessidade de
  duplicar.

Diagrama exploratorio (2026-07-29, **nao e decisao aprovada**, apenas
visualizacao a pedido do usuario): `docs/diagrams/integration-hub-conceitual.html`
mostra como ficaria SE este Hub generico fosse construido, com os provedores
reais do sistema (IXC, Correios, E-mail, Google) no lugar dos hipoteticos de
`melhorias_arquitetura.md`. Achado durante a montagem: a integracao de
Correios hoje e apenas uma chamada de CEP a uma API terceirizada
(`clientes/views.py::buscar_cep`, Hub do Desenvolvedor - nao a API oficial dos
Correios), sem gateway/provider isolado - vira candidato a `CorreiosGateway`
somente se houver necessidade real (trocar de fornecedor de CEP, reuso em
mais de uma automacao).

## Consequencias positivas

- Mantem o sistema atual isolado e funcional independente do modulo 2, por
  construcao (dependencia em uma via so + kill switch);
- nao introduz infraestrutura nova (sem broker, sem segundo deploy) nesta
  fase - evolucao incremental e reversivel, no mesmo espirito da ADR-005;
- resolve o problema real de acoplamento entre extracao e consumo de dados do
  IXC com uma solucao que o projeto ja sabe operar (banco MySQL, rotinas
  agendadas), sem nova dependencia operacional.

## Consequencias negativas / riscos

- verificacao manual da regra de dependencia (item 3) pode falhar por
  descuido em revisões futuras se o numero de apps crescer sem uma ferramenta
  de lint;
- tabela de fila intermediaria por integracao pode duplicar estrutura semelhante
  entre features diferentes - com a decisao ampliada do item 7, ja temos
  os 2-3 casos reais previstos aqui (entrada O.S., entrada cliente/login,
  saida O.S.); resolvido no item 9 com uma classe abstrata Django comum
  para os campos de status/erro, sem virar um modelo generico/polimorfico
  unico;
- sem broker, nao ha retry automatico com backoff nem processamento em tempo
  quase real - aceitavel enquanto a integracao IXC for baseada em lotes
  agendados, nao em eventos.

## Alternativas consideradas

### 1. Modulo 2 como projeto/servico Django separado (rumo a microsservico)

Descartada pela mesma razao da ADR-005: custo desproporcional ao estagio
atual da equipe e do volume; feature de dependencia unidirecional e kill
switch e mais simples de garantir dentro do mesmo monolito.

### 2. Introduzir Celery/Redis agora para a integracao IXC

Descartada nesta fase. O problema descrito pelo usuario (evitar que falha em
uma rotina quebre a outra) e resolvido pela tabela de fila intermediaria sem nova
infraestrutura. Fica como opcao futura se aparecer necessidade real de retry
granular por item ou de reduzir a latencia entre extracao e consumo para
quase tempo real.

### 3. Fila de entrada via webhook do IXC

Descartada em 2026-07-28, apos confirmacao em tres fontes independentes
(documentacao publica, teste de leitura na API real e navegacao direta no
painel da conta) de que o IXC nao oferece webhook para atendimento, O.S. ou
cliente - ver item 6. A entrada de dados continua pelo sync incremental
agendado, sem mudanca em relacao ao que ja existia antes desta ADR.

### 4. "Integration Hub" generico (Manager/Registry/queue com broker/providers para sistemas sem automacao real)

Descartada em 2026-07-29, ver item 10 (avaliacao completa da proposta em
`melhorias_arquitetura.md`). Resumo: contradiz decisoes ja aprovadas (sem
broker/fila dedicada, sem tabela polimorfica unica) ou e abstracao/scaffolding
prematuro para sistemas sem automacao real (Correios, OpenAI, WhatsApp) ou
sem um segundo gateway maduro que justifique interface comum (`BaseProvider`).

## Pendencias

- quais setores entram no modulo 2 e a ordem de prioridade (decisao do
  usuario, quando houver a primeira automacao concreta);
- nome e campos da tabela de fila intermediaria de saida ficam para quando a
  automacao concreta que a usar for desenhada;
- nome e campos da tabela de fila intermediaria de entrada (item 7) ficam para
  quando a automacao de ingestao de O.S. for desenhada;
- modelo/campo do status de sincronizacao e da chave de idempotencia do
  fechamento de O.S. (item 8) ficam para quando essa automacao concreta
  for desenhada;
- painel de reprocessamento manual das linhas em status `erro` (item 10, ideia
  de `melhorias_arquitetura.md`) fica para quando as automacoes concretas de
  entrada/saida estiverem construidas.

Nesta fase, o escopo funcional confirmado com o usuario e apenas duas
automacoes: entrada de O.S. (ingestao) e fechamento de O.S.. Nenhuma outra
automacao de Backoffice/Modulo 2 entra neste momento.

## Diagrama

`docs/diagrams/adr-006-expansao-modular.html` (fonte:
`adr-006-expansao-modular.architecture.json`) mostra a arquitetura alvo desta
ADR: Modulo 2 com kill switch e dependencia em uma via so, as tres tabelas de
fila intermediaria (entrada de O.S., entrada de cliente/login e saida de O.S.) e o
fechamento de O.S. sincrono com fallback. Regenerar sempre que um dos itens 2 a
10 mudar (item 10 apenas adiciona `correlation_id` ao `StagingBase` do item 9 -
regenerar somente se o diagrama passar a detalhar campos da tabela).

## Proxima acao

Orquestrador atualizou `docs/ARCHITECTURE.md` com um ponteiro curto para esta
ADR (2026-07-29, inclui o resumo da avaliacao do item 10). Nenhuma feature
nova e criada em `docs/BACKLOG.md`/`docs/checklist.md` ainda, por faltar o
escopo concreto (setores do modulo 2, automacao que primeiro precisar do
padrao de fila ou do campo `correlation_id`).
