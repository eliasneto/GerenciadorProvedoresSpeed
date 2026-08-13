# Backlog

## Visao geral

Este documento contem **somente o que esta aberto**: features planejadas, em
execucao, aguardando QA ou bloqueadas. Tudo que ja foi concluido e aprovado
vive em `docs/BACKLOG_ARCHIVE.md`, com o historico completo de entrega e
validacao.

Status utilizados neste documento:

- `Planejada`
- `Em execucao`
- `Aguardando QA`
- `Bloqueada`

Ao concluir uma feature (QA aprovado), mova o bloco inteiro para o arquivo em
vez de deixa-lo aqui — e o que mantem este documento legivel.

Metodo de trabalho: este backlog nao e organizado por sprint (ciclo fixo de
tempo). Cada PO e sequenciada pelo que ela realmente depende para ser
entregue como artefato - ver a ordem de execucao dentro de cada epico quando
houver dependencia entre POs.

## Epic 13 - Nova Infraestrutura (ADR-005/006/007) — PRIORIDADE

Decisao do usuario em 2026-07-29: antes do primeiro app do Modulo 2, o Modulo
1 precisa estar reorganizado o suficiente para crescer de forma escalavel,
estavel e facil de manter. Este epico e a prioridade sobre os demais deste
documento — nao bloqueia os outros, mas deve ser tratado primeiro.

**Metodo de trabalho:** este epico nao e organizado por sprint. Cada PO e uma
fatia entregavel, sequenciada por dependencia real entre artefatos, nao por
tempo. A ordem abaixo e a ordem de execucao recomendada:

```text
PO-031 (namespace unico)
   |
   +--> PO-029 (mover clientes/)
   |        |
   +--> PO-032 (quebrar 3 dos 5 ciclos de importacao)
            |
            +--> PO-011 (camada de servicos nos demais apps)
            |
            +--> PO-036 (decisao de ownership + os 2 ciclos restantes)

PO-026 (mover IXCClient - ja aguardando QA, sem dependencia)
   |
   +--> PO-033 (Hub de Integracao: apps/integracoes/)
            |
            +--> PO-034 (scripts/ -> management commands)

PO-030 (limpar raiz - independente, roda a qualquer momento)

Todas concluidas --> PO-035 (verificacao de regressao end-to-end - gate para o Modulo 2)
```

`PO-011`, `PO-026`, `PO-029` e `PO-030` ja existiam no backlog e foram trazidas
para este epico por pertencerem ao mesmo esforco; mantem o numero original.

### PO-026 - Mover ixc_client.py (IXCGateway) para dentro de um app Django

Status: `Concluída`

Validação do QA (2026-07-30):
- Comparado `apps/core/ixc_client.py` com o conteudo anterior (`git show
  HEAD:scripts/integracoes/ixc_client.py`): identico byte a byte (fora quebra
  de linha LF/CRLF) — nenhuma alteracao de comportamento no `IXCClient`.
- Busca ampla no codigo versionado: nenhuma referencia restante a
  `scripts.integracoes.ixc_client`; `manage.py check` sem erro.
- Suite de `scripts.integracoes`, `apps.backoffice` e `apps.core_admin`
  executada contra o MySQL real: 156 testes, 1 falha (`AutomacaoMenuTests`,
  ja registrada como pre-existente desde a entrega da PO-031/PO-029, sem
  relacao com este gateway) — nenhuma regressao introduzida pela mudanca.
- **Problema:** nenhum.
- **Resultado:** aprovado.

Entrega do Dev (2026-07-27):
- `ixc_client.py` (`IXCClient`) movido via `git mv` (historico preservado) para
  `apps/core/ixc_client.py`, seguindo o mesmo padrao ja usado por `ad_sync.py`
  (integracao AD tambem compartilhada em `apps/core`).
- Atualizados os 18 pontos de import (`from scripts.integracoes.ixc_client`
  para `from apps.core.ixc_client`) encontrados em `apps/backoffice`,
  `apps/core_admin`, `scripts/integracoes/*` e `_checar_ixc_hoje.py`; nenhuma
  referencia antiga restou no codigo versionado.
- Nenhuma alteracao de comportamento no `IXCClient` (mesmo HTTP, timeout,
  headers e tratamento de erro).
- **Pendencia:** suíte de testes não pôde ser executada neste ambiente (Docker
  Desktop indisponível e Python local sem `mysqlclient`); validado apenas
  verificação estática — compilação de todos os arquivos alterados sem erro de
  sintaxe, importação isolada de `apps.core.ixc_client` bem-sucedida, e busca
  ampla confirmando ausência de referências ao caminho antigo. Recomenda-se ao
  QA rodar a suíte completa no container `speed_sistema` antes de aprovar.
- `docs/architecture.md` **não foi alterado por mim** (fora do escopo do Dev,
  conforme CLAUDE.md); a nota de exceção sobre o gateway e a linha "Cliente
  HTTP compartilhado: `scripts/integracoes/ixc_client.py`" ficaram
  desatualizadas com esta entrega e precisam de atualização pelo Orquestrador.

Nota do Orquestrador (2026-07-29): esta PO fecha a divergencia original da
ADR-005 (gateway fora de qualquer app). Com a ADR-007 (item 4), o destino
final do `IXCClient` deixou de ser `apps/core/` e passou a ser
`apps/integracoes/ixc/client.py` — mas isso **nao invalida** a entrega desta
PO, que cumpriu exatamente o que foi pedido na epoca. O passo seguinte (mover
de `apps/core/` para `apps/integracoes/ixc/`) e a PO-033, nao uma reabertura
desta.

Objetivo:
Fechar a ultima divergencia conhecida entre a ADR-005 e o estado real do
codigo: `scripts/integracoes/ixc_client.py` (`IXCClient`) e o gateway unico do
IXC (ja documentado como tal em `architecture.md` e no diagrama de
arquitetura), mas ainda reside em `scripts/integracoes/`, fora da estrutura de
apps Django exigida pela decisao da ADR-005 ("codigo de integracao de producao
deve residir dentro dos apps Django; scripts/ fica reservado a ferramentas
operacionais e management commands").

Contexto:
PO-024 ja registrou esta pendencia explicitamente ("candidato a uma fatia
futura") e justificou o adiamento porque `apps/backoffice` importar de
`scripts/integracoes/` nao quebra nada tecnicamente. A divergencia e apenas
documental/arquitetural: a excecao nunca foi formalizada na propria ADR-005,
apenas mencionada como nota lateral no backlog. Diferente dos arquivos listados
em "Fora desta feature" de PO-024 (`ixc_api.py`, `ixc_faxina.py`, etc.),
`ixc_client.py` nao tem acoplamento a cron/subprocess do `docker-compose.yml`,
entao esta fatia nao depende de coordenacao com o DevOps.

Fora desta feature:
- mover `ixc_finalizacao_service.py` e `ixc_ticket_arquivo_service.py`
  (dependencias proprias mais amplas, permanecem candidatos a fatia futura
  separada, conforme ja registrado em PO-024);
- mover qualquer script com acoplamento a cron/subprocess do
  `docker-compose.yml` (lista completa em PO-024).

Criterios de aceite:
- `ixc_client.py` (`IXCClient`) passa a residir dentro de um app Django (ex.:
  `apps/backoffice/integracoes_ixc/` ou um modulo compartilhado, a criterio do
  Dev, desde que multiplos apps consigam importar sem acoplamento indevido);
  a decisao de onde deve ser breve e registrada no proprio checklist da
  feature;
- todos os pontos de import atualizados; nenhuma referencia antiga a
  `scripts.integracoes.ixc_client` restante no codigo versionado;
  testes existentes de `IXCClient` preservados e passando;
- nenhuma alteracao de comportamento HTTP/timeout/auditoria do client;
- `docs/architecture.md` atualizado para remover a nota de excecao, refletindo
  que o gateway agora cumpre integralmente a regra da ADR-005.

Regras relacionadas: nenhuma nova.

Tipo de feature: `backend-only` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-038 - Remover as telas mortas de Logs de Integracao (gestao)

Status: `Planejada`

Origem: achado do Dev durante a fatia `core` da PO-011 (2026-07-30). Decisao
do usuario (2026-07-30): remover, em vez de reativar.

Contexto:
`gestao_logs_integracoes` e `gestao_log_integracao_detail`
(`apps/core/views.py`) tem view, template e logica de filtro
(`apps/core/services.py::filtrar_logs_integracao`) prontos, mas nunca tiveram
rota registrada em nenhum `urls.py` do projeto. Os dois templates
(`gestao_logs_integracoes.html`, `gestao_log_integracao_detail.html`) fazem
`{% url 'gestao_logs_integracoes' %}` para essa rota inexistente — a pagina
quebra mesmo ao chamar a view diretamente, sem relacao com a PO-011. Nunca
foi ao ar; nao ha usuario dependendo da tela hoje.

Criterios de aceite:
- removidos `gestao_logs_integracoes`, `gestao_log_integracao_detail` e
  `filtrar_logs_integracao` (`apps/core/views.py`/`services.py`) e os dois
  templates associados;
- removidos os testes que cobrem exclusivamente esse codigo
  (`FiltrarLogsIntegracaoServiceTests`,
  `GestaoLogsIntegracoesPermissaoTests` em `apps/core/tests.py`);
- busca ampla por referencia residual (template, `{% url %}`, import,
  menu) antes de remover, para nao deixar link morto para uma rota que ja
  nao existia;
- `manage.py check` e suite completa sem regressao.

Regras relacionadas: nenhuma.

Tipo de feature: `backend-only` (QA obrigatorio, focado em ausencia de
referencia quebrada — nao ha regra de negocio envolvida).

Agente recomendado para executar:
- `dev`.

### PO-039 - Exibir historico do parceiro (comentarios/anexos) na tela de detalhe

Status: `Planejada`

Origem: achado do Dev durante a fatia `partners` (grupo Parceiro) da PO-011
(2026-07-30). Decisao do usuario (2026-07-30): construir a tela, em vez de
remover o codigo.

Contexto:
`partner_detail` (`apps/partners/views.py`) e
`services.listar_historico_partner`/`contar_historico_arquivado_partner`
(`apps/partners/services.py`) ja calculam o historico ativo, a contagem de
arquivados e o parametro `ver_antigos`, e passam tudo para o template. Mas
`partners/templates/partners/partner_detail.html` nunca usa `historico`,
`qtd_antigo` nem `ver_antigos` — a tela nao mostra nenhum comentario/anexo
do parceiro nem o botao para ver o historico arquivado. O botao de adicionar
historico (`partner_add_historico`) existe e funciona (grava no banco), so a
listagem que falta. Pre-existente, nao criado por esta PO.

Referencia de padrao ja implementado: `core/templates/core/timeline_global.html`
(`apps/core/views.py::timeline_global`) resolve o mesmo problema — lista de
historico por periodo, com o mesmo modelo `RegistroHistorico` via
`GenericForeignKey` — e pode servir de base visual para esta tela.

Criterios de aceite:
- a tela de detalhe do parceiro (`/parceiros/<id>/`) exibe a lista de
  historico (comentarios e anexos), mais recente primeiro;
- por padrao mostra somente os itens ativos (`arquivado=False`);
- existe um controle visivel (botao/link) para alternar para "ver antigos"
  (`?ver_antigos=true`), mostrando também os arquivados, com contagem
  (`qtd_antigo`) visivel antes de clicar;
- anexo do historico (`arquivo`), quando existir, tem link para download;
- responsivo (celular e desktop) e aderente ao padrao visual já usado nas
  demais telas do parceiro.

Regras relacionadas: nenhuma nova.

Tipo de feature: `frontend-functional` (envolve toggle/HTMX e leitura de
dados já calculados pela view; QA obrigatorio).

Agente recomendado para executar:
- `dev`.

### PO-037 - Corrigir AttributeError ao mover lead para negociacao

Status: `Aguardando QA`

Prioridade: Alta — decisao do usuario em 2026-07-29. Entra na frente das
fatias `core`, `core_admin` e `partners` da PO-011, por afetar usuario em
producao (erro 500) e deixar a auditoria da transicao de status incompleta.

Entrega do Dev (2026-07-29):
- `mover_lead_para_negociacao` (`apps/leads/services.py`) passou a usar
  `LEAD_STATUS_CHOICES` em vez do inexistente `Lead.STATUS_CHOICES`.
- Teste que documentava o bug reescrito para validar o comportamento
  correto: status muda para "negociacao", `RegistroHistorico` e criado e a
  resposta redireciona com sucesso, sem erro 500.
- Suite de `leads` (29 testes) e suite completa do projeto (140 testes)
  executadas; sem regressao. As mesmas 2 falhas pre-existentes e sem relacao
  com este bug continuam registradas (dependencia `tqdm` ausente; teste de
  menu do `core_admin`).

Objetivo:
Corrigir `mover_lead_para_negociacao` (`apps/leads/services.py:271`), que
referencia `Lead.STATUS_CHOICES` — atributo inexistente no model; a constante
correta e `LEAD_STATUS_CHOICES`, definida no modulo `apps/leads/models.py`.

Contexto (achado pelo Dev em 2026-07-29, durante a extracao de servicos da
PO-011, fatia `leads`):
O metodo primeiro salva `lead.status = 'negociacao'` e so depois monta o
texto do historico com `Lead.STATUS_CHOICES`. Ou seja, toda vez que um lead
muda de fato de status para "negociacao" a partir de outro status, a mudanca
de status e persistida, mas o `AttributeError` interrompe a execucao antes de
criar o `RegistroHistorico` da transicao e antes de responder ao usuario —
request quebra com erro 500 em vez de mostrar a mensagem de sucesso, e o
historico de auditoria fica sem o registro dessa mudanca. Reproduzido em
teste (`test_update_status_negociacao_a_partir_de_outro_status_bug_conhecido`,
`apps/leads/tests.py`).

Criterios de aceite:
- `mover_lead_para_negociacao` usa `LEAD_STATUS_CHOICES`;
- transicao de status para "negociacao" a partir de qualquer outro status
  gera o `RegistroHistorico` correspondente e responde com a mensagem de
  sucesso, sem erro 500;
- teste que hoje documenta o bug passa a validar o comportamento correto.

Regras relacionadas: nenhuma nova.

Tipo de feature: `backend-only` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-035 - Verificacao de regressao funcional end-to-end (gate antes do Modulo 2)

Status: `Bloqueada` (regressao automatizada e smoke test aprovados pelo QA;
falta so a confirmacao final do usuario)

Validação do QA — regressao automatizada + smoke test HTTP (2026-08-03):
- Suite completa (309 testes) reexecutada de forma independente: mesmo
  resultado do Dev (1 falha + 2 erros, todos pre-existentes e ja
  documentados em entregas anteriores).
- Subida real do servidor local contra o MySQL real (fora da suite de
  testes) e checagem via HTTP de 11 rotas nos apps reorganizados nesta
  sessao (`leads`, `partners`, `clientes`, `core_admin`, `backoffice`,
  `health`, `docs`): todas resolveram corretamente — sem 404/500, com
  redirecionamento/bloqueio (302/403/401) correto para acesso nao
  autenticado, confirmando que roteamento e permissao sobrevivem a
  reestruturacao fora do ambiente de teste automatizado.
- RN-017/RN-018: cobertura automatizada ja extensa e aprovada na PO-011
  (22 testes na sub-fatia Fechamento de O.S./edicao financeira, incluindo
  cenarios de erro do IXC e calculo financeiro) — reconfirmada nesta suite
  completa, sem regressao.
- **Nao verificavel nesta sessao:** as 9 automacoes de planilha do
  Backoffice via navegador real, as 6 rotinas agendadas comparadas com
  historico real de producao, e login via AD real — exigem ambiente com
  credenciais IXC/AD reais e/ou uma sessao de navegador, indisponiveis
  aqui.
- **Resultado:** regressao automatizada e smoke test HTTP aprovados, sem
  achado impeditivo. A validacao manual completa (navegador, IXC, AD) e a
  confirmacao final continuam pendentes — nao e papel do QA nem do Dev
  fechar essa parte.

Entrega do Dev (2026-08-03):
- `manage.py check` e `makemigrations --check --dry-run` limpos.
- Suite de testes completa do projeto executada de uma unica vez (nao por
  app): 309 testes, 1 falha + 2 erros — os mesmos 3 problemas pre-existentes
  ja documentados em entregas anteriores (`AutomacaoMenuTests`; encoding de
  emoji em `ixc_explorador.py`), nenhuma regressao nova.
- Revisao do `BACKLOG.md` em busca de POs fora do Epic 13 afetadas
  silenciosamente: achado 1 caso — a entrega registrada da PO-021 cita
  `cadastrar_cliente_ixc.py` no caminho antigo (pre-PO-033); as funcoes
  (`detectar_cnpj_duplicado_na_planilha`, `verificar_duplicidade_ixc`)
  existem e estao corretamente importadas no caminho novo
  (`apps/integracoes/ixc/services/`) — sem impacto funcional, so a
  narrativa historica da PO ficou desatualizada. Nao corrigi (fora do meu
  escopo alterar o texto de outra PO) — sinalizado ao Orquestrador.
- Observacao adicional (pre-existente, nao e achado desta PO): a PO-026
  esta marcada `Concluída` com QA ja aprovado, mas nunca foi movida para
  `BACKLOG_ARCHIVE.md` — inconsistencia de arquivamento anterior a esta
  sessao, sinalizada ao Orquestrador.
- **Pendencia:** os demais criterios de aceite (9 automacoes de planilha
  testadas manualmente, 6 rotinas agendadas comparadas com historico
  recente, login AD/local, reconferencia manual de RN-017/RN-018) sao
  validacao funcional (QA) e confirmacao final (usuario), conforme a
  propria PO ja determinava; nao ha ambiente com IXC/AD reais nesta sessao
  para executa-los.

Dependencias: PO-031, PO-029, PO-032, PO-036, PO-026, PO-033, PO-034 e PO-011
concluidas.

Objetivo:
Ser o portao de saida deste epico: confirmar, com o sistema ja reestruturado,
que nenhuma tela, automacao ou regra de negocio quebrou, antes de autorizar o
inicio do primeiro app do Modulo 2.

Contexto:
Decisao do usuario em 2026-07-29: "caso por conta da nova arquitetura, alguma
tela, regra de negocio possa quebrar, o Dev ja deve ter uma atividade de
verificacao desses componentes do sistema." As POs 031 a 034 e 011 ja carregam
verificacao de regressao local (por fatia); esta PO e a verificacao **de
conjunto**, depois que todas as fatias estiverem prontas.

Criterios de aceite:
- suite de testes completa do projeto executada de uma vez (nao por app
  isolado), sem regressao;
- as 9 automacoes de planilha do Backoffice (ver diagrama `07`) testadas
  manualmente uma a uma: cadastro de cliente, atendimento, cotacao,
  resolucao/edicao/desativacao de O.S., importacao de prospects, teste de API
  IXC;
- as 6 rotinas agendadas confirmadas rodando com o novo agendamento
  (management command) sem diferenca de resultado frente ao historico
  recente;
- login via AD e via conta local testado depois da unificacao de namespace
  (`apps/core/models.py::User` e ponto sensivel, tocado por PO-031 e
  potencialmente por PO-032);
- RN-017 e RN-018 (ciclo de vida da cotacao) reconferidas manualmente: abrir
  uma cotacao sem endereco, sem provedor, e testar cada transicao de status;
- checklist de features abertas (`docs/BACKLOG.md`) revisado: se alguma PO
  fora deste epico foi afetada silenciosamente pela reestruturacao, registrar
  achado novo — nao corrigir sem avisar o Orquestrador.

Regras relacionadas: RN-017, RN-018.

Tipo de feature: `backend-only` (QA obrigatorio — o QA participa desta PO
desde o inicio, nao entra so depois do Dev terminar).

Agente recomendado para executar:
- `dev` (regressao automatizada); `qa` (validacao funcional e das RN);
  usuario (confirmacao final de que o Modulo 1 esta pronto para o Modulo 2).

## Epic 3 - Swagger e contratos externos

### PO-010 - Definir autenticacao da API

Status: `Planejada`

Objetivo:
Definir modelo de acesso seguro para integracoes externas.

Observacao:
Nao bloquear a fundacao da API e do Swagger em ambiente interno, mas deve anteceder publicacao externa produtiva.

Agentes recomendados:
- `software_architect`
- `backend_django`

Observacao arquitetural:
- decisao recomendada: JWT com contas tecnicas reutilizando `core.User` e grupo `api_integracao_publica`.

## Epic 5 - Automacoes de Backoffice IXC

### PO-014 - Corrigir possivel fechamento incompleto na Desativacao de Atendimento (IXC)

Status: `Risco identificado, nao validado`

Objetivo:
Verificar se `executar_desativacao_atendimento` (`desativar_atendimento_ixc.py`)
finaliza o atendimento com base em uma lista fixa de O.S. obtida uma unica
vez, e corrigir se o mesmo problema de RN-010 se confirmar: fechar uma O.S.
pode criar a proxima tarefa do workflow do IXC como uma nova O.S. aberta,
que a lista fixa nao conhece.

Criterios de aceite (a confirmar apos investigacao):
- reproduzir em ambiente de homologacao um atendimento cujo workflow tenha
  mais de uma tarefa, e confirmar se finalizar a primeira O.S. cria uma
  nova O.S. aberta no mesmo atendimento;
- se confirmado, aplicar o mesmo padrao de loop-até-esgotar de RN-010,
  ajustando o criterio de "ultima O.S. finaliza o atendimento" para so
  finalizar quando nao houver mais nenhuma O.S. aberta.

Regras relacionadas: RN-010 (docs/business_rules.md).

Decisao arquitetural: docs/adr/ADR-004_FECHAMENTO_OS_EM_LOOP_ATE_ESGOTAR.md
(risco relacionado, correcao fora do escopo direto da ADR).

Tipo de feature: `backend-only` (QA obrigatorio, apos confirmacao do risco).

Agente recomendado para executar:
- investigacao: `dev`; correcao, se confirmada: `dev`.

### PO-040 - Informar proxima tarefa do workflow ao fechar O.S. de decisao (IXC)

Status: `✅ Concluida`

**Validacao do QA:**
- **Rota/tela:** `montar_payload_fechamento_real`/`finalizar_os_existente` (`ixc_finalizacao_service.py`), acionados via `executar_resolucao_os_atendimento_ixc`.
- **Cenarios testados:** Proxima_Tarefa_ID preenchido (envia `eh_tarefa_decisao="S"` e o ID) e vazio (mantem `eh_tarefa_decisao="N"` e `id_proxima_tarefa="0"`); valor nao numerico bloqueia a linha antes de tocar o IXC.
- **Regras verificadas:** RN-019.
- **Problema:** nenhum impeditivo. Observacao nao bloqueante: quando `Fechar_Todas_OS = SIM` fecha mais de uma O.S. do mesmo atendimento, o mesmo `Proxima_Tarefa_ID` da planilha e reenviado para todas elas; se um atendimento tiver mais de uma tela de decisao com tarefas diferentes no mesmo lote, isso pode direcionar O.S. subsequentes para o ramo errado. RN-019 nao cobre esse caso e a hipotese de multiplas decisoes por atendimento nao foi validada em homologacao (mesmo risco geral ja registrado em ADR-004). Recomenda-se validar com um atendimento real antes de uso intenso com as duas opcoes combinadas.
- **Resultado:** aprovado.

Objetivo:
Hoje `montar_payload_fechamento_real` (`ixc_finalizacao_service.py`) fixa
`eh_tarefa_decisao="N"` e `id_proxima_tarefa="0"` para toda O.S. fechada pela
automacao de resolucao em massa. O usuario identificou, operando o IXC
manualmente, que a tarefa atual de uma O.S. pode ser uma tarefa de decisao
com tela obrigatoria de "Proxima tarefa" (ex.: Realizar Implantacao,
Realizar Implantacao EACE, Nao Atende Requisitos Tecnicos). Sem informar
esse valor a automacao provavelmente falha ou fecha a O.S. no ramo errado
do workflow.

Criterios de aceite:
- nova coluna obrigatoria na planilha de `resolver_os_atendimento_ixc.py`
  para o ID da proxima tarefa, usada apenas quando a O.S. exigir decisao;
- quando informada, o valor e enviado em `id_proxima_tarefa` e
  `eh_tarefa_decisao="S"` no payload de fechamento;
- quando a O.S. atual nao exigir decisao, o comportamento atual (sem exigir
  o campo) permanece sem alteracao;
- Dev define, no levantamento tecnico, como detectar se a tarefa atual
  exige decisao (campo do IXC a consultar) antes de decidir se o campo na
  planilha e sempre obrigatorio ou condicional.

Regras relacionadas: RN-019 (docs/business_rules.md).

Decisao arquitetural: docs/adr/ADR-004_FECHAMENTO_OS_EM_LOOP_ATE_ESGOTAR.md
(mesma raiz: fechar O.S. e avanco de workflow BPM, nao marcacao simples de
status).

Tipo de feature: `backend-only` (QA obrigatorio).

Agente recomendado para executar:
- `dev`.

### PO-041 - Suportar mais de um anexo por atendimento (Mais_de_um_anexo)

Status: `✅ Concluida`

**Validacao do QA:**
- **Rota/tela:** `executar_resolucao_os_atendimento_ixc` (`resolver_os_atendimento_ixc.py`), planilha modelo em `montar_template_resolucao_os_atendimento_bytes`.
- **Cenarios testados:** Mais_de_um_anexo = SIM com os 3 nomes preenchidos (anexa em sequencia, nessa ordem); Mais_de_um_anexo = NAO com Nome_Anexo_2 preenchido (ignorado, so o primeiro e enviado); segundo anexo nao encontrado no ZIP (interrompe a linha, nenhuma O.S. fechada, nenhum atendimento vinculado indevidamente); Mais_de_um_anexo com valor invalido quando Tem_Anexo = NAO (nao bloqueia a linha, campo ignorado como previsto).
- **Regras verificadas:** RN-002, RN-006, RN-008, RN-020.
- **Problema:** nenhum.
- **Resultado:** aprovado.

Objetivo:
Hoje a automacao de resolucao de O.S. em massa (`resolver_os_atendimento_ixc.py`)
so aceita um documento por atendimento (`Nome_Anexo`). O usuario identificou
que um atendimento pode ter mais de um documento a anexar antes do
fechamento das O.S. (ex.: contrato + aditivos), e confirmou que a solucao e
3 colunas de nome de arquivo mais uma coluna de controle explicita, em vez
de lista separada por virgula em uma unica coluna.

Criterios de aceite:
- novas colunas opcionais na planilha: `Mais_de_um_anexo` (Sim/Nao),
  `Nome_Anexo_2` e `Nome_Anexo_3`;
- `Mais_de_um_anexo` so e avaliado quando `Tem_Anexo = SIM`;
- quando `Mais_de_um_anexo = SIM`, a automacao anexa cada nome preenchido
  entre `Nome_Anexo`, `Nome_Anexo_2` e `Nome_Anexo_3`, em sequencia, cada um
  reaproveitando a correspondencia por nome dentro do ZIP (RN-008);
- quando `Mais_de_um_anexo = NAO` ou vazio, comportamento atual sem alteracao
  (so `Nome_Anexo` e usado);
- mantido o comportamento tudo-ou-nada (RN-002): qualquer anexo preenchido
  que falhar interrompe a linha antes de qualquer O.S. ser finalizada;
- aba de ajuda da planilha modelo atualizada com as novas colunas.

Regras relacionadas: RN-002, RN-006, RN-008, RN-009, RN-020 (docs/business_rules.md).

Tipo de feature: `backend-only` (QA obrigatorio).

Agente recomendado para executar:
- `dev`.

### PO-042 - Informar colaborador do fechamento por e-mail (Informar_Colaborador)

Status: `✅ Concluida`

**Validacao do QA:**
- **Rota/tela:** `executar_resolucao_os_atendimento_ixc` (`resolver_os_atendimento_ixc.py`), planilha modelo em `montar_template_resolucao_os_atendimento_bytes`.
- **Cenarios testados:** Informar_Colaborador = SIM sem Email_Colaborador (bloqueia antes de qualquer consulta ao IXC); e-mail informado nao encontrado no cadastro do IXC (bloqueia, nao usa fallback generico); e-mail valido (usado em `email_ixc` na finalizacao); Informar_Colaborador = NAO com Email_Colaborador preenchido (ignorado, mantem usuario logado).
- **Regras verificadas:** RN-002, RN-006, RN-020, RN-021.
- **Problema:** nenhum.
- **Resultado:** aprovado.

Objetivo:
Hoje a automacao de resolucao de O.S. em massa (`resolver_os_atendimento_ixc.py`)
sempre atribui o fechamento ao usuario do sistema logado, resolvido para um
usuario do IXC por e-mail/nome/usuario (`resolver_usuario_ixc_por_usuario_sistema`,
em `ixc_finalizacao_service.py`). O usuario identificou que isso faz o nome
dele aparecer no IXC mesmo quando a acao deveria ser atribuida a outra
pessoa, e confirmou que a automacao deve permitir informar o e-mail de outro
colaborador por linha — nao o ID do IXC, que nao tem visibilidade facil de
qual numero corresponde a qual pessoa.

Criterios de aceite:
- novas colunas opcionais na planilha: `Informar_Colaborador` (Sim/Nao) e
  `Email_Colaborador`;
- `Informar_Colaborador = SIM` exige `Email_Colaborador` preenchido; vazio
  bloqueia a linha antes de qualquer O.S. ser tocada;
- `Informar_Colaborador = SIM` com e-mail que nao corresponde a nenhum
  usuario cadastrado no IXC bloqueia a linha (nao cair silenciosamente no
  usuario/tecnico padrao generico que `resolver_usuario_ixc_por_email` usa
  como fallback interno quando nao encontra o e-mail);
- `Informar_Colaborador = NAO` ou vazio: `Email_Colaborador`, mesmo se
  preenchido, e ignorado; usa o e-mail do usuario logado (comportamento
  atual);
- reaproveitar `resolver_usuario_ixc_por_email` (ja existente) e o parametro
  `email_ixc` de `finalizar_os_existente`, sem duplicar logica de resolucao
  de usuario;
- aba de ajuda da planilha modelo atualizada com as novas colunas.

Regras relacionadas: RN-002, RN-006, RN-020, RN-021 (docs/business_rules.md).

Tipo de feature: `backend-only` (QA obrigatorio).

Agente recomendado para executar:
- `dev`.

### PO-043 - Mostrar linha atual em execucao na resolucao de O.S. em massa

Status: `✅ Concluida`

**Validacao do QA:**
- **Rota/tela:** `resolver_os_atendimento_ixc` + novo endpoint `progresso_resolucao_os_atendimento` (`/ferramentas/atendimentos/resolucao-os/progresso/`).
- **Cenarios testados:** progresso gravado a cada linha durante o processamento (verificado consultando o registro no meio da execucao, nao so no final); consulta de execucao concluida retorna totais corretos; consulta de execucao inexistente retorna `nao_encontrado`; usuario sem permissao bloqueado (403); pagina renderiza com o JS de polling e a URL correta.
- **Regras verificadas:** RN-022.
- **Problema:** nenhum impeditivo. Observacao nao bloqueante: o endpoint de progresso nao filtra por usuario (qualquer um com a permissao da automacao pode consultar qualquer execucao_id) — consistente com o padrao ja existente na tela (auditoria/ultima execucao tambem e compartilhada, nao por usuario), entao nao tratei como divergencia.
- **Resultado:** aprovado.

Objetivo:
Hoje a automacao de resolucao de O.S. em massa (`resolver_os_atendimento_ixc.py`)
roda inteira dentro de um unico request HTTP sincrono, sem nenhuma indicacao
de progresso na tela alem de um spinner estatico. O usuario relatou nao ter
visibilidade de quanto falta durante execucoes longas (ex.: 148 linhas,
~18 minutos) e confirmou que a automacao deve continuar sincrona — a
melhoria e so de visibilidade, via consulta periodica (polling) da tela.

Criterios de aceite:
- durante o processamento, o sistema grava o progresso atual (numero da
  linha, total de linhas, Atendimento_ID sendo processado) em um registro
  consultavel, atualizado a cada linha ou a cada N linhas (decisao tecnica
  do Dev, priorizando nao atrasar o processamento);
- novo endpoint leve (somente leitura, mesma permissao da automacao) que
  retorna o progresso atual dessa execucao;
- o template `resolver_os_atendimento_ixc.html` passa a fazer polling
  desse endpoint durante o estado de carregamento, exibindo "Processando
  linha X de Y (Atendimento Z)" em vez do spinner estatico atual;
- ao concluir (sucesso, erro ou falha), o indicador de progresso e
  finalizado normalmente, sem interferir no download do relatorio ja
  existente;
- fora de escopo: nao precisa resolver a perda do relatorio se o processo
  for interrompido no meio (risco separado, ja registrado em 2026-08-06
  junto do ajuste do timeout do Gunicorn).

Regras relacionadas: RN-002, RN-022 (docs/business_rules.md).

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`.

## Epic 7 - Seguranca de credenciais

### PO-027 - Impedir login com senha antiga do AD via fallback do ModelBackend

Status: `Planejada`

Objetivo:
Corrigir falha de seguranca encontrada em 2026-07-27: com `USE_AD_AUTH` ativo,
`AUTHENTICATION_BACKENDS` (`config/settings.py`) lista `LDAPBackend` e
`ModelBackend`, nesta ordem. Todo usuario local recebe senha utilizavel via
`set_password` (`apps/core/models.py`), e nada sincroniza esse hash quando a
senha e trocada no AD — por isso o `ModelBackend` continua autenticando com a
senha antiga mesmo depois de trocada no AD.

Criterios de aceite (a confirmar com o usuario antes da implementacao, por
alterar regra de autenticacao/seguranca):
- decisao entre remover o fallback `ModelBackend` para usuarios autenticados
  via AD, ou invalidar a senha local (`set_unusable_password`) desses
  usuarios, mantendo `ModelBackend` restrito a contas administrativas locais
  explicitas;
- apos a correcao, trocar a senha no AD invalida imediatamente a senha antiga
  no login do sistema;
- login de contas administrativas locais (sem conta no AD), se existirem,
  continua funcionando.

Regras relacionadas: nenhuma registrada ainda; RN a criar pelo Orquestrador
junto com a decisao de abordagem acima.

Tipo de feature: `backend-only` (QA obrigatorio).

Agente recomendado para executar:
- decisao de abordagem: usuario/Orquestrador; implementacao: `dev`.

## Epic 8 - Observabilidade e mapeamento de erros das automacoes

### PO-018 - Cadastrar `cadastro_cliente_ixc` em `IntegrationAudit.INTEGRATION_CHOICES`

Status: `Planejada`

Objetivo:
Corrigir divergencia encontrada no mapeamento de 2026-07-21: a automacao de
cadastro de cliente IXC (`apps/backoffice/views.py`, constante
`CADASTRO_CLIENTE_IXC_INTEGRATION = "cadastro_cliente_ixc"`) grava auditoria
via `registrar_auditoria_integracao`, mas o valor `"cadastro_cliente_ixc"`
nao consta em `IntegrationAudit.INTEGRATION_CHOICES` (`apps/core/models.py`).
O registro e salvo mesmo assim (Django nao valida `choices` no banco), porem
sem rotulo de exibicao correto e sem opcao de filtro na tela
`gestao_logs_integracoes.html`.

Criterios de aceite:
- `"cadastro_cliente_ixc"` adicionado a `IntegrationAudit.INTEGRATION_CHOICES`
  com rotulo de exibicao adequado;
- migration gerada para a alteracao do `choices`;
- tela de gestao de logs de integracao passa a exibir e filtrar corretamente
  os registros dessa integracao, incluindo os ja gravados antes da correcao.

Tipo de feature: `backend-only` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-019 - Ampliar `LOGGING` para cobrir exceções das views de integracao/automacao

Status: `Planejada`

Objetivo:
Corrigir lacuna encontrada no mapeamento de 2026-07-21: o `LOGGING` em
`config/settings.py` so cobre os loggers `django.security`, `core.middleware`
e `apps.core.middleware`, em nivel `WARNING`, com saida somente em console.
Excecoes lancadas nas views de integracao/automacao (`apps/core_admin/`,
`apps/backoffice/`) nao tem logger dedicado nem persistencia fora do que cada
view grava manualmente em `messages.error`/auditoria funcional
(`IntegrationAudit`, `apps/auditoria/`) — nao ha registro central de stack
trace.

Criterios de aceite:
- logger dedicado (ou nivel `ERROR` explicito) para as views de
  integracao/automacao, capturando excecao com stack trace;
- decisao registrada sobre destino do log (arquivo, servico externo ou
  manter console) — nao inventar ferramenta nao aprovada pelo usuario;
- nenhuma credencial ou dado sensivel exposto no log (CLAUDE.md secao 6).

Tipo de feature: `devops` com impacto tecnico em `backend-only` (validacao
tecnica conforme criterios da tarefa; QA se houver mudanca de comportamento
funcional percebida).

Agente recomendado para executar:
- `dev` / `devops` (decisao de destino do log)

## Epic 9 - Qualidade das mensagens de erro do Cadastro de Cliente IXC

### PO-021 - Detectar CNPJ/CPF duplicado na validacao previa do Cadastro de Cliente IXC (dentro da planilha e contra o IXC)

Status: `Em execucao` (implementado pelo Dev; aguardando QA)

Entrega do Dev (2026-07-24):
- Nova funcao `detectar_cnpj_duplicado_na_planilha` (`cadastrar_cliente_ixc.py`)
  compara o CNPJ/CPF de todas as linhas da planilha e sinaliza as que se
  repetem, respeitando `Permitir_Duplicidade = Sim` por linha.
- Logica de duplicidade contra o IXC foi extraida para a funcao reutilizavel
  `verificar_duplicidade_ixc` (mesmo formato de mensagem de RN-015), usada
  tanto na execucao (`executar_cadastro_cliente_ixc`) quanto na nova
  validacao previa.
- Fase 1 de `cadastrar_clientes_ixc` (`apps/backoffice/views.py`) passou a
  chamar as duas verificacoes antes de liberar o envio; qualquer uma delas
  reprova a planilha inteira (tudo ou nada), como os demais erros.
- Guia de uso do cadastro de clientes atualizado na epoca da entrega
  (`docs/manuais/` foi removido em 2026-07-29, por decisao do dono do produto).
- Testes adicionados: 2 unitarios das novas funcoes (`CadastroClienteIXCTests`)
  e 3 de view (`CoreAdminViewsTests`) cobrindo duplicidade interna, duplicidade
  contra o IXC e liberacao via `Permitir_Duplicidade`.
- **Testes executados** (container isolado, mesma imagem de `speed_sistema`,
  sem afetar o container em producao): `CadastroClienteIXCTests` e
  `CoreAdminViewsTests` (26/26); suite completa `apps.backoffice.tests` +
  `apps.core_admin.tests` (54/55) — a 1 falha e a mesma pre-existente e sem
  relacao ja registrada na entrega de PO-020
  (`AutomacaoMenuTests.test_migracao_de_dados_preservou_automacoes_existentes_em_administrador`).

Objetivo:
Antecipar para a fase de validacao previa ("tudo ou nada", em
`cadastrar_clientes_ixc`, `apps/backoffice/views.py`) a deteccao de CNPJ/CPF
duplicado, hoje descoberta somente durante o envio efetivo ao IXC
(`executar_cadastro_cliente_ixc`, RN-015). Usuario percebeu no
`log_integracao_274` que o mesmo CNPJ se repetia em varias linhas da
planilha e que o erro so aparecia depois do envio, linha a linha.

Criterios de aceite (RN-016):
- validacao previa compara CNPJ/CPF entre todas as linhas da planilha e
  reprova a linha (ou linhas) com repeticao interna, indicando quais linhas
  colidem;
- validacao previa tambem consulta o IXC (mesma logica de
  `buscar_cliente_por_cnpj_cpf`/`buscar_cliente_por_razao_social`) e reprova
  a linha cujo CNPJ/CPF (ou razao social) ja exista, com mensagem no mesmo
  formato de RN-015 (campo, valor comparado e ID do cliente existente);
- qualquer uma das duas ocorrencias reprova a planilha inteira (tudo ou
  nada), a menos que a linha tenha `Permitir_Duplicidade = Sim`;
- planilha `Validacao_Cadastro_Clientes_IXC.xlsx` retornada ao usuario passa
  a exibir esses dois novos tipos de erro em `Erros_Validacao`.

Regras relacionadas: RN-015, RN-016 (docs/business_rules.md).

Tipo de feature: `backend-only` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

## Epic 14 - Saida do IXC como fonte de Cliente/Endereco e nova integracao DashboardEACE (Escola)

### PO-044 - Desativar (comentar) a sincronizacao automatica de Cliente/Endereco com o IXC

Status: `🔍 Aguardando QA` (implementado pelo Dev em 2026-08-07)

Objetivo:
Usuario decidiu que, para o uso atual do projeto, os enderecos vao ser
importados manualmente em vez de sincronizados automaticamente do IXC.
Confirmado desligar as 4 rotinas agendadas que hoje populam/atualizam
`Cliente`/`Endereco` a partir do IXC, mantendo o codigo intacto (comentado,
nao apagado) para eventual reativacao futura.

Criterios de aceite (ADR-008):
- comentar, no `docker-compose.yml` (servico `speed_sincronizador`), os 4
  blocos `if` que chamam `ixc_sincronizacao_incremental`, `ixc_carga_total`,
  `ixc_os_comercial_lastmile` e `ixc_faxina` dentro do loop `while true`,
  com uma linha de comentario indicando a ADR-008 e como reativar;
- comentar, em `apps/clientes/admin.py` e `apps/auditoria/admin.py` (botoes
  duplicados), os `path(...)` e os metodos `btn_rodar_carga_total`,
  `btn_rodar_incremental`, `btn_rodar_faxina`, `btn_rodar_os_comercial_lastmile`
  e `btn_parar_os_comercial_lastmile`; nao remover `btn_rodar_backup` nem
  `btn_rodar_respostas_email_cotacao` (nao fazem parte desta ADR);
- nao alterar os management commands nem os scripts equivalentes em
  `scripts/integracoes/` — devem continuar executaveis manualmente via
  `python manage.py <comando>` para quem precisar rodar uma sincronizacao
  pontual durante a transicao;
- nao apagar nem alterar dados de `Cliente`/`Endereco` ja existentes;
- confirmar que as automacoes de escrita no IXC (Backoffice: resolucao de
  O.S., desativacao de atendimento, cadastro de cliente, edicao de login/
  atendimento etc.) continuam funcionando normalmente (nao dependem destas
  4 rotinas).

Risco aceito (ver ADR-008): `apps/leads` e `apps/partners` deixam de
receber atualizacao automatica de `em_os_comercial_lastmile`/
`os_atual_aberta` — usuario confirmou ciente do impacto.

Fora de escopo: mecanismo de importacao manual de enderecos (planilha,
Admin padrao ou outro) — decisao futura, nao definida nesta feature.

Regras relacionadas: RN-017 (docs/business_rules.md).

Decisao arquitetural: docs/adr/ADR-008_DESATIVACAO_SINCRONIZACAO_ENDERECO_IXC.md

Tipo de feature: `devops` (toca `docker-compose.yml`, normalmente arquivo do
DevOps; incluido nesta feature de Dev a pedido explicito do usuario — avaliar
com o usuario se prefere separar essa parte para o DevOps).

Agente recomendado para executar:
- `dev`

### PO-045 - Estrutura preparatoria da integracao com o DashboardEACE

Status: `🔍 Aguardando QA` (implementado pelo Dev em 2026-08-07, incluindo a
correcao de autenticacao para `X-API-Key` e os wrappers de `/escolas` apos
o usuario entregar `API_EXTERNA.md`)

Objetivo:
A pendencia deixada pela PO-044/ADR-008 (mecanismo de importacao de
Cliente/Endereco) foi resolvida pelo usuario: em vez de importacao manual,
um novo sistema externo — o DashboardEACE — vai fornecer os enderecos/
logins via API, que o SGP consome. O usuario pediu para a estrutura ficar
pronta antes mesmo dos dados reais da API chegarem.

Criterios de aceite (ADR-009 — somente scaffolding, sem integracao real):
- criar `apps/integracoes/dashboard_eace/__init__.py` e
  `apps/integracoes/dashboard_eace/client.py`, com uma classe
  `DashboardEACEClient` que le `DASHBOARD_EACE_URL`/`DASHBOARD_EACE_TOKEN`
  de variavel de ambiente, expoe `timeout`/`verify_ssl` configuraveis
  (padrao seguro: `verify_ssl=True`) e um metodo generico de leitura HTTP
  com tratamento de timeout/erro de conexao, no mesmo espirito de
  `apps/integracoes/ixc/client.py` — sem copiar a convencao propria do IXC
  (`qtype`/`query`/`oper`) nem chumbar nenhum endpoint real;
- criar `apps/integracoes/dashboard_eace/services/__init__.py` vazio,
  pronto para receber a logica de sincronizacao quando o contrato da API
  chegar;
- adicionar `DASHBOARD_EACE_URL=` e `DASHBOARD_EACE_TOKEN=` (vazios, com
  comentario) em `.env.example` e nos servicos relevantes do
  `docker-compose.yml`;
- testes cobrindo somente a estrutura do client (inicializa com variavel
  de ambiente; erro claro se `DASHBOARD_EACE_TOKEN` nao estiver definido;
  headers de autenticacao montados corretamente) — sem endpoint real;
- **nao** implementar endpoint real, mapeamento de campos para
  `Cliente`/`Endereco`, nem qualquer logica de sincronizacao — isso
  depende do contrato da API que o usuario ainda vai enviar (ADR-009,
  "explicitamente fora de escopo agora").

Regras relacionadas: RN-017 (docs/business_rules.md).

Decisao arquitetural: docs/adr/ADR-009_INTEGRACAO_DASHBOARD_EACE_ESTRUTURA_PREPARATORIA.md

Tipo de feature: `backend-only` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-046 - Model dedicado Escola e sincronizacao manual a partir do DashboardEACE

Status: `🔍 Aguardando QA` (implementado pelo Dev em 2026-08-07; validado
contra a API real do DashboardEACE — 2622 escolas sincronizadas, comando
roda idempotente. Corrigido no caminho: campo identificador real da API e
`key`, nao `jira_key` como o criterio abaixo supunha)

Objetivo:
Usuario decidiu (ADR-010) que os dados de `GET /escolas` do DashboardEACE
nao devem mapear para `apps.clientes.Cliente`/`Endereco` — devem ir para
uma tabela nova e independente, "comecando do zero". O banco atual
(`Cliente`/`Endereco`) continua existindo, sem alteracao, disponivel para
consulta futura "conforme a necessidade" (fora do escopo desta feature).

Criterios de aceite (ADR-010):
- novo app `apps.escolas`, registrado em `INSTALLED_APPS`
  (`config/settings.py`), seguindo o padrao de app-por-dominio ja usado
  por `apps.clientes`/`apps.leads`/`apps.partners`;
- model `Escola` (`apps/escolas/models.py`) com os campos: `jira_key`
  (`CharField`, unico), `uf` (`CharField`, opcional), `status_escola`
  (`CharField`, opcional), `dados_api` (`JSONField`, payload bruto
  completo retornado pela API para aquela escola) e `atualizado_em`
  (`DateTimeField(auto_now=True)`);
- migration criada e aplicada;
- funcao de sincronizacao (`apps/escolas/services.py`) que chama
  `listar_escolas()` (ja existente em
  `apps/integracoes/dashboard_eace/services/escolas.py`) e grava um
  `Escola` por item via `update_or_create` (chave: `jira_key`), guardando
  o item inteiro em `dados_api`;
- management command simples para disparo manual (ex.: `python manage.py
  sincronizar_escolas_dashboard_eace`), no mesmo espirito dos demais
  comandos de sincronizacao do projeto — **sem** agendamento automatico
  (nao esta em escopo; se quiser agendar depois, e nova decisao);
- testes cobrindo a funcao de sincronizacao com a API mockada (sem
  depender de credenciais reais — elas ainda nao existem);
- **nao** alterar `apps.clientes.Cliente`/`Endereco` nem `RN-017` — sem
  relacao entre `Escola` e esses models nesta feature.

Regras relacionadas: RN-017 (docs/business_rules.md) — apenas referenciada, nao alterada por esta feature.

Decisao arquitetural: docs/adr/ADR-010_MODELO_ESCOLA_DEDICADO_DASHBOARD_EACE.md

Tipo de feature: `backend-only` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-047 - Tela de Enderecos Lastmile passa a exibir Escola (INEP, Nome, UF, Municipio, Endereco)

Status: `Aguardando QA` (implementado pelo Dev em 2026-08-07)

Objetivo:
A tela global "Enderecos / Lastmile" (`leads:enderecos_lastmile`) esta
vazia desde a ADR-008 (dependia dos campos que a sincronizacao do IXC
parou de atualizar). Usuario decidiu trocar a fonte dessa tela para
`Escola` (DashboardEACE), mostrando INEP, Nome da escola, Estado,
Municipio e Endereco. Confirmado que, por agora, a acao de criar cotacao
fica indisponivel nessas linhas (`Escola` nao tem vinculo com `Cliente`/
`Endereco` — ver ADR-011).

Criterios de aceite (ADR-011):
- promover em `apps.escolas.Escola` os campos `inep`, `nome`, `municipio`
  (`CharField`) e `endereco_descricao` (`TextField`, mapeado do campo
  `descricao` da API) de dentro de `dados_api` para colunas tipadas;
  migration com backfill dos registros ja sincronizados a partir do
  `dados_api` existente (nao exigir rodar a sincronizacao de novo);
  atualizar `apps/escolas/services.py::sincronizar_escolas` para gravar
  esses campos tambem nas proximas sincronizacoes;
- `enderecos_lastmile_view` (`apps/leads/views.py`) passa a consultar
  `Escola.objects.all()` (sem filtro de elegibilidade — usuario pediu
  "todos"); busca textual (`q`) passa a considerar `nome`/`inep`/
  `municipio`/`uf`/`jira_key`;
- `enderecos_lastmile.html`: colunas da grade viram INEP, Nome da escola,
  Estado, Municipio, Endereco; contador "Enderecos elegiveis" reescrito
  para o novo significado (ex.: "Total de escolas");
  icone de Acoes que abria o modal de criar cotacao (e o de detalhe
  tecnico, especifico de `Endereco`) sao removidos desta tela;
- endpoints AJAX do modal de cotacao (`endereco_lastmile_lead_address_grid`,
  `endereco_lastmile_partner_search`, `endereco_lastmile_batch_proposal_create`)
  **nao sao removidos nem alterados** — so deixam de ser referenciados
  por esta tela;
- **fora de escopo**: `enderecos_lastmile_cliente_view`/template (variante
  por cliente) — nao alterar nesta feature;
- **investigar e reportar** (nao assumir): existe algum outro caminho no
  sistema para abrir `Proposal` vinculada a `Endereco`/`Cliente` fora
  desta tela? Se esta for a unica porta de entrada, reportar como achado
  antes do QA aprovar — nao e bloqueio automatico, e informacao que o
  usuario precisa ter.

Regras relacionadas: RN-017 (docs/business_rules.md) — nao alterada; a tela deixa de ser um caminho de entrada, a regra em si continua igual.

Decisao arquitetural: docs/adr/ADR-011_TELA_ENDERECOS_LASTMILE_PASSA_A_EXIBIR_ESCOLA.md

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

## Epic 15 - Processos de Rede Externa (RE) e Rede Interna (RI) por Escola

### PO-048 - Models RedeExterna e RedeInterna vinculados a Escola

Status: `Aguardando QA` (implementado pelo Dev em 2026-08-07)

Objetivo:
Usuario decidiu (ADR-012) que cada `Escola` tem dois processos
independentes de conectividade — Rede Externa (RE) e Rede Interna (RI) —
geridos pelo proprio sistema (nao um espelho dos campos `*_re`/`*_ri` ja
existentes em `Escola.dados_api`, vindos da API do DashboardEACE). Cada
processo tem seu proprio setor, status e parceiro, podendo estar em
setores/status diferentes e com o mesmo parceiro ou parceiros diferentes.

Criterios de aceite (ADR-012, RN-023):
- em `apps/escolas/models.py`, criar uma classe abstrata `ProcessoRedeBase`
  com os campos comuns: `setor` (`CharField`, opcional, sem `choices=`),
  `status` (`CharField`, opcional, sem `choices=`), `parceiro`
  (`ForeignKey("partners.Partner", null=True, blank=True,
  on_delete=models.SET_NULL)`), `dados_adicionais` (`JSONField`,
  `default=dict`, opcional), `criado_em`
  (`DateTimeField(auto_now_add=True)`), `atualizado_em`
  (`DateTimeField(auto_now=True)`);
- criar `RedeExterna(ProcessoRedeBase)` e `RedeInterna(ProcessoRedeBase)`,
  cada um com `escola = models.OneToOneField(Escola, on_delete=models.CASCADE,
  related_name="rede_externa"/"rede_interna")`;
- migration aditiva (sem alterar `Escola`, `Cliente`, `Endereco` ou
  `Proposal`);
- registrar os dois models no Django Admin (`apps/escolas/admin.py`),
  permitindo criar/editar setor, status e parceiro — sem exigir tela
  dedicada fora do Admin nesta feature;
- **nao** pre-preencher `setor`/`parceiro` a partir de
  `Escola.dados_api` (`setor_re`/`setor_ri`/`parceiro_re`/`parceiro_ri`) —
  criacao comeca em branco (ver ADR-012);
- **nao** criar sincronizacao automatica entre esses models e a API do
  DashboardEACE;
- testes cobrindo: criacao de RE/RI vinculados a uma Escola, independencia
  de status entre RE e RI da mesma Escola, e que remover a Escola remove
  (cascade) o RE/RI associado.

Regras relacionadas: RN-023 (docs/business_rules.md).

Decisao arquitetural: docs/adr/ADR-012_PROCESSOS_REDE_EXTERNA_E_REDE_INTERNA_POR_ESCOLA.md

Tipo de feature: `backend-only` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-049 - Expandir linha da Escola na tela de Enderecos Lastmile para mostrar referencia de RE e RI

Status: `Aguardando QA` (implementado pelo Dev em 2026-08-07)

Objetivo:
Usuario pediu para ver, na tela de Enderecos Lastmile, os dados de Rede
Externa (RE) e Rede Interna (RI) que ja vem da API do DashboardEACE.
Confirmado (ADR-013): por agora, so a referencia somente-leitura que ja
esta em `Escola.dados_api`, sem editar e sem envolver os models
`RedeExterna`/`RedeInterna` (PO-048), que continuam vazios.

Criterios de aceite (ADR-013, RN-024):
- na tabela de `enderecos_lastmile.html`, cada linha de escola ganha uma
  acao de expandir (clique na linha); ao expandir, revela duas linhas
  logo abaixo, somente leitura: uma de RE, outra de RI;
- linha de RE mostra: Setor (`dados_api.setor_re`), Parceiro
  (`dados_api.parceiro_re`), Custo de implantacao
  (`dados_api.custo_re_implantacao`), Custo recorrente
  (`dados_api.custo_re_recorrente`);
- linha de RI mostra os mesmos 4 campos com sufixo `_ri`;
- campo ausente/vazio exibe "Nao informado", no mesmo padrao das demais
  colunas da tela;
- comportamento de expandir/recolher client-side (JavaScript simples, sem
  nova biblioteca — tecnologia ja usada no projeto), sem nova requisicao ao
  servidor — os dados de `dados_api` ja vem no queryset atual da view;
- **fora de escopo**: promover os campos para coluna tipada; editar
  setor/parceiro/custo; criar, ler ou exibir `RedeExterna`/`RedeInterna`
  nesta tela.

Ajuste visual (2026-08-07, sem mudanca funcional, `frontend-layout`):
usuario pediu grid com aparencia de planilha — aplicado pelo Dev
diretamente sobre a tabela desta tela (linhas mais finas, borda visivel em
volta de cada celula, cabecalho com fundo solido). Sem novo PO/ADR. Aguarda
validacao visual do usuario (nao passa por QA).

Ajuste visual adicional (2026-08-07, mesmo escopo, sem mudanca funcional):
usuario trouxe referencia visual (print do dashboard Jira da EACE, tema
escuro e grade densa) e confirmou que quer **so o estilo visual** dessa
referencia — tema escuro + grade — mantendo as colunas e o comportamento
atuais (RE/RI continua expandindo ao clicar). Elementos funcionais da
referencia (checkbox de selecao, Status editavel em dropdown, Parceiro
R.E/R.I como colunas fixas) foram explicitamente descartados por agora —
mudariam comportamento e exigiriam nova rodada de escopo com o
Orquestrador. Aplicado pelo Dev reaproveitando as cores da propria
identidade do projeto (`ageis-black`/`ageis-yellow`, ja usadas na barra
lateral), sem introduzir paleta nova.

Correcao de rota (2026-08-07): usuario reprovou o tema escuro ("ficou
horrivel a cor preta") mas confirmou que a densidade/grade ("o modelo")
ficou boa. Revertido para a paleta clara padrao do sistema (fundo branco,
texto escuro, bordas cinza — a mesma usada nas demais telas), mantendo
linhas finas e grade visivel em todas as celulas.

Regras relacionadas: RN-024, RN-023 (docs/business_rules.md).

Decisao arquitetural: docs/adr/ADR-013_EXIBICAO_REFERENCIA_RE_RI_NA_TELA_ENDERECOS_LASTMILE.md

Tipo de feature: `frontend-functional` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-050 - Catalogo de Processos (Setor/Status) e vinculo com RedeExterna/RedeInterna

Status: `Aguardando QA` (implementado pelo Dev em 2026-08-07)

Objetivo:
Usuario pediu uma tela nova, "Processos", na aba Administracao, para
cadastrar Processos e, dentro de cada um, os Setores que o compoem e os
Status de cada Setor. Resolve a pendencia de vocabulario de setor/status
deixada pela RN-023/ADR-012. Confirmado: Processo e generico (sem campo
tipo RE/RI); `RedeExterna`/`RedeInterna` se vinculam a um Processo.

Criterios de aceite (ADR-014, RN-025):
- novos models em `apps/escolas/models.py`: `Processo` (`nome` unico),
  `Setor` (`nome`, FK `processo`, unico por processo+nome), `SetorStatus`
  (`nome`, FK `setor`, unico por setor+nome);
- `RedeExterna` e `RedeInterna` ganham campo `processo` (`ForeignKey`
  para `Processo`, `null=True`, `blank=True`, `on_delete=SET_NULL`);
- migration aditiva; migration de dados (`RunPython`) semeando 2
  Processos ("Rede Externa (RE)", "Rede Interna (RI)"), cada um com os
  Setores Lastmile/Suprimentos/Implantacao/Pos venda/Suporte, cada Setor
  com os Status A fazer/Em andamento/Concluido (dados de teste,
  explicitamente nao-definitivos);
- tela nova em `apps.core_admin`, restrita ao grupo `Administrador`
  (`grupo_Administrador_required`, mesmo padrao de Teste SMTP/Restaurar
  Backup):
  - `/ferramentas/processos/`: lista os Processos (nome, qtde de
    setores) e formulario de criacao (so nome);
  - `/ferramentas/processos/<id>/`: detalhe do Processo — Setores e seus
    Status, formulario para adicionar Setor (so nome);
  - endpoint para adicionar Status a um Setor (so nome), redireciona de
    volta ao detalhe;
- **nesta versao, so listar e criar** — sem editar nem excluir Processo,
  Setor ou Status;
- novo item no sidebar, dentro da secao "Administracao" ja existente;
- **fora de escopo**: `RedeExterna.setor`/`status` continuam texto livre
  (nao passam a ser FK para Setor/SetorStatus); validacao cruzada entre
  o texto livre e o Processo vinculado.

Regras relacionadas: RN-025, RN-023 (docs/business_rules.md).

Decisao arquitetural: docs/adr/ADR-014_CATALOGO_DE_PROCESSOS_SETOR_STATUS_PARA_RE_E_RI.md

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-051 - Setor e Status de RE/RI editaveis no grid de Enderecos Lastmile (cascata com Processo)

Status: `Aguardando QA` (implementado pelo Dev em 2026-08-07, com ajuste
de escopo pedido pelo usuario durante a implementacao — ver nota abaixo)

Objetivo:
Usuario precisa mudar o Setor e o Status do RE/RI direto no grid de
Enderecos Lastmile (mover entre setores, atualizar status), usando o
catalogo Processo/Setor/Status ja cadastrado na PO-050. Confirmado:
edicao em cascata (Processo -> Setor -> Status) na propria linha
expandida; se a escola nao tiver RedeExterna/RedeInterna ainda, criar ao
salvar.

Criterios de aceite (ADR-015, RN-026):
- migration convertendo `RedeExterna.setor`/`status` e
  `RedeInterna.setor`/`status` de `CharField` para `ForeignKey`
  (`escolas.Setor`/`escolas.SetorStatus`), `null=True`, `blank=True`,
  `on_delete=SET_NULL` — confirmado 0 registros reais hoje, sem dado a
  migrar/perder;
- atualizar `apps/escolas/admin.py`: `list_filter`/`search_fields` de
  `RedeExternaAdmin`/`RedeInternaAdmin` ajustados ao novo tipo de campo;
- na linha expandida de RE e na de RI (`enderecos_lastmile.html`), modo de
  edicao com 3 campos em cascata: Processo (todos cadastrados), Setor
  (somente do Processo escolhido, via HTMX), Status (somente do Setor
  escolhido, via HTMX);
- validacao de integridade na view/form (nao so na UI): setor deve
  pertencer ao processo escolhido; status deve pertencer ao setor
  escolhido; rejeitar combinacao invalida mesmo se a chamada nao vier da
  cascata da tela;
- salvar sem `RedeExterna`/`RedeInterna` existente para aquela escola cria
  o registro (`get_or_create` pela `Escola`);
- **fora de escopo**: editar `Parceiro`; referencia da API (RN-024) nao
  muda, continua somente leitura;
- permissao: mesma que ja protege a tela hoje (grupo `LastMile` ou
  superuser) — nenhuma permissao nova.

Ajuste de escopo pedido pelo usuario durante a implementacao (2026-08-07,
diverge do que a ADR-015 registra — **emenda pendente, papel do
Orquestrador**): o usuario decidiu que o Processo **nao** e escolhido na
tela — cada RE usa sempre o mesmo Processo fixo, e cada RI usa sempre outro
Processo fixo, "configurado no inicio do projeto". Implementado como
`RedeExterna.NOME_PROCESSO_PADRAO = "Rede Externa (RE)"` e
`RedeInterna.NOME_PROCESSO_PADRAO = "Rede Interna (RI)"` (busca por nome
exato do Processo cadastrado na PO-050) — o Dev auto-vincula esse Processo
ao salvar, sem exigir escolha do usuario. A tela ficou so com Setor e
Status (cascata Setor->Status, sem mais Processo->Setor). Usuario tambem
pediu para nao duplicar a linha de referencia da API com a linha de
edicao — as duas foram unificadas numa linha so por RE/RI (Parceiro e
Custos da API aparecem ao lado do Setor/Status editaveis).

Emenda (2026-08-10, RN-033) implementada pelo Dev:
- Status trava (campo desabilitado) na Tela de Setor quando o Setor
  selecionado deixa de ser o Setor atual.
- Ao salvar enviado a outro Setor, Status vira "Aguardando" do Setor de
  destino, ignorando o que veio no formulario.
- "Aguardando" e criado automaticamente no Setor de destino quando ainda
  nao existir.
- Grid global (sem Setor atual) nao muda: Status continua livremente
  editavel.
- Subatividade ja atribuida a um Setor deixa de mostrar a opcao em
  branco "Selecione" no Setor e no Status (so vai para outro Setor,
  nunca fica sem); a opcao em branco continua so para a primeira
  atribuicao (tela global, sem Setor ainda).
- **Pendência:** validação visual em navegador não executada (sem
  credencial de login disponível no ambiente); validado só por testes
  automatizados.

Emenda (2026-08-10, RN-035) implementada pelo Dev: no grid global de
Enderecos Lastmile (sem Setor atual — fora da Tela de Setor), Status
deixou de ser editavel. So Setor continua editavel nessa tela; o Status
exibido passa a ser sempre "Novo" (criado automaticamente no Setor
escolhido, mesmo padrao do "Aguardando" da RN-033), sem escolha manual e
ignorando qualquer Status enviado no formulario. A Tela de Setor nao foi
alterada, continua com a regra da RN-033.
- **Pendência:** validação visual em navegador não executada (sem
  credencial de login disponível no ambiente); validado só por testes
  automatizados (suíte completa de `apps.leads`, 98 testes, OK).

Regras relacionadas: RN-026, RN-023, RN-025, RN-033, RN-035 (docs/business_rules.md).

Decisao arquitetural: docs/adr/ADR-015_SETOR_E_STATUS_EDITAVEIS_PARA_RE_E_RI_NO_GRID.md

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-052 - Visao por Setor das atividades de RE e RI (menu dedicado)

Status: `Aguardando QA` (implementado pelo Dev em 2026-08-07)

Objetivo:
Usuario quer que cada Setor tenha sua propria tela (acessivel por um item
de menu chamado "Setores"), mostrando um grid com as atividades de RE e
RI que estao com aquele Setor. Inicialmente, somente visualizacao.

Criterios de aceite (ADR-016, RN-027):
- nova secao "Setores" no sidebar (`core/base.html`), com um link por
  nome de Setor cadastrado — lista dinamica (vem do banco), via context
  processor (mesmo padrao de `automacoes_realocadas`);
- `GET /prospeccao/setores/`: lista os nomes de Setor cadastrados;
- `GET /prospeccao/setores/<nome>/`: grid com todo `RedeExterna`/
  `RedeInterna` cujo Setor tenha aquele nome, **em qualquer Processo**
  (RE e RI compartilham o mesmo vocabulario de nomes de Setor, PO-050) —
  paginado no mesmo padrao das demais telas;
- colunas do grid: tipo (RE/RI), Escola (INEP + nome), Status atual,
  Parceiro (quando houver);
- **somente leitura** — nao editar Setor/Status nesta tela (continua em
  Enderecos Lastmile, RN-026);
- permissao: mesma que ja protege Enderecos Lastmile (`grupo_LastMile_required`)
  — sem restricao por time nesta versao;
- views/templates em `apps.leads` (mesmo app de `enderecos_lastmile`);
  nenhum model novo.

Regras relacionadas: RN-027, RN-023, RN-025, RN-026 (docs/business_rules.md).

Decisao arquitetural: docs/adr/ADR-016_VISAO_POR_SETOR_DAS_ATIVIDADES_RE_RI.md

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-053 - Tela de Setor reaproveita o grid de Enderecos Lastmile, com edicao habilitada

Status: `Aguardando QA` (implementado pelo Dev em 2026-08-07)

Objetivo:
A tela de Setor (PO-052) perdia informacao (INEP, Estado, Municipio,
Endereco) por usar uma lista propria em vez do grid de Escola ja existente.
Substituir por uma versao que reaproveita o mesmo grid/template de
Enderecos Lastmile, filtrado por Setor, com a edicao de Setor/Status
(RN-026) habilitada tambem aqui.

Criterios de aceite (ADR-017, RN-028):
- `filtrar_escolas_lastmile` (`apps/leads/services.py`) ganha parametro
  opcional `setor_nome`; quando informado, filtra
  `Escola.objects.filter(Q(rede_externa__setor__nome=setor_nome) |
  Q(rede_interna__setor__nome=setor_nome))`, mantendo busca/cidade/
  estado/ordenacao como hoje;
- view `setor_detail` passa a chamar `filtrar_escolas_lastmile` com esse
  filtro e renderizar `enderecos_lastmile.html` (em vez do template
  proprio da PO-052, que sai de uso);
- `enderecos_lastmile.html` recebe `setor_atual` (nome do Setor da tela,
  `None` no grid global) e ajusta titulo/subtitulo (ex.: "Setor /
  Suprimentos");
- linha de RE mostrada somente se `escola.rede_externa.setor.nome ==
  setor_atual`; linha de RI somente se `escola.rede_interna.setor.nome ==
  setor_atual` — quando `setor_atual` for `None` (grid global), continua
  mostrando as duas linhas sempre, como hoje;
- edicao de Setor/Status (RN-026, ja existente) fica habilitada tambem
  nesta tela — mesmo componente, mesma permissao
  (`grupo_LastMile_required`);
- remover `leads/setor_detail.html` (template da PO-052, sem uso).

Correcao (2026-08-07, mesmo dia, apos o usuario testar): ao mudar o Setor
de um RE/RI enquanto na tela de um Setor de origem (ex.: "Cotacao"), a
escola continuava aparecendo naquela tela ate um F5 — o JS so atualizava a
linha de RE/RI no lugar, sem remover a escola da lista quando ela deixava
de pertencer aquele Setor. Corrigido: a view `escola_rede_editar` agora
recebe `setor_atual` (a tela de origem) e informa se o RE/RI salvo ainda
pertence a ela; quando nao pertence mais, o JS remove a linha (e a escola
inteira, se nenhuma outra subatividade dela continuar naquele Setor) sem
precisar recarregar a pagina. Sem mudanca no banco — so correcao de tela.

Regras relacionadas: RN-028, RN-026, RN-027 (docs/business_rules.md).

Decisao arquitetural: docs/adr/ADR-017_TELA_DE_SETOR_REAPROVEITA_GRID_DE_ENDERECOS_LASTMILE.md

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-054 - Historico e anexo individual de RE e RI, com visao combinada na Escola

Status: `Aguardando QA` (implementado pelo Dev em 2026-08-10)

Entrega do Dev:
- Botao de historico no RE e no RI (grid de Enderecos Lastmile) abre modal vertical com comentario, anexo e alteracoes de setor/status daquele processo.
- Alterar Setor/Status pela tela (nao pelo Admin) agora grava historico automatico com valor anterior e novo.
- Botao de historico na linha da Escola abre modal combinado com as entradas de RE e RI, cada uma marcada com a origem (RE/RI).
- Anexo continua individual por processo: o que e anexado no RE nao aparece no historico do RI da mesma escola.
- Validado no navegador (login real, escola com RE existente): abrir modal, adicionar comentario sem fechar a lista, e ver o combinado da Escola. Sem erro no console.
- **Pendencia:** nenhuma.

Objetivo:
Usuario pediu, em 2026-08-10, que cada processo (RE e RI) tenha seu proprio
historico e anexo, contemplando alteracao de dados, comentarios, alteracao
de status e anexos — e que a Escola (registro "pai" dos dois processos)
possa ver o historico combinado.

Criterios de aceite (RN-029):
- RE e RI passam a ter historico proprio via `RegistroHistorico`
  (`apps.core.models`), usando `GenericForeignKey` — mesmo model generico
  ja usado por Partner/Proposal (PO-039), sem model novo;
- anexo (`RegistroHistorico.arquivo`) passa a ser individual por processo:
  um arquivo anexado ao RE nao aparece no historico do RI da mesma escola,
  e vice-versa;
- toda alteracao de `setor`, `status` ou `parceiro` feita pela tela
  (`escola_rede_editar`, `apps/leads/views.py:591`) passa a gerar um
  `RegistroHistorico` tipo `sistema`, registrando valor anterior e novo
  (mesmo padrao "Antes/Depois" ja usado em `apps/partners/services.py`);
  edicoes feitas direto no Django Admin **nao** geram esse log (RN-029);
- usuario tambem pode adicionar comentario manual (tipo `comentario`) e
  anexo (tipo `anexo`) pelo mesmo fluxo;
- no grid de Enderecos Lastmile, a linha expandida de RE e a de RI
  (RN-024/RN-026) ganham cada uma um botao "Historico", que abre um modal
  (layout vertical) mostrando somente o historico daquele processo —
  comentarios, anexos e alteracoes de status/dados, mais recente primeiro,
  com formulario para adicionar comentario/anexo;
- a linha da Escola ganha um botao proprio de historico, abrindo um modal
  combinado com as entradas de RE e RI juntas, identificando de qual
  processo (RE ou RI) cada entrada veio;
- permissao: mesma que ja protege a edicao de RE/RI no grid
  (`grupo_LastMile_required`);
- sem N+1 na consulta do historico combinado da Escola (uma consulta por
  processo, nao uma por entrada).

Regras relacionadas: RN-029, RN-023, RN-026 (docs/business_rules.md).

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-055 - Ajustes visuais no grid de Enderecos Lastmile/Setor: fonte dos filtros e cor do sub-grid de RE/RI

Status: `👤 Aguardando validação visual` (implementado pelo Dev em 2026-08-10)

Entrega do Dev:
- Campos da barra de filtros (busca, município, UF, ordenação) e o botão Filtrar passaram a usar a mesma fonte pequena já usada no resto do grid.
- Linha expandida de RE/RI ganhou um fundo âmbar clarinho, bem diferente do branco da linha da Escola, para não confundir ao expandir várias escolas juntas.
- Mudança só de classe visual (CSS) — nenhum dado, filtro, permissão ou comportamento alterado.
- Validado no navegador (grid global com 3 escolas expandidas ao mesmo tempo e a barra de filtros): sem erro no console, sem regressão nos 73 testes de `apps.leads`.
- **Pendência:** aguardando sua validação visual.

Objetivo:
Usuario apontou, em 2026-08-10, dois problemas visuais na tela de
Enderecos Lastmile e na tela de Setor (mesmo grid, PO-053): a barra de
filtros (busca, municipio, UF, ordenacao) usa uma fonte fora do padrao
do restante do grid, maior que o resto do sistema; e a linha expandida
de RE/RI (sub-grid) usa uma cor muito parecida com a das demais linhas
de escola, dificultando identificar visualmente a qual escola cada RE/RI
pertence quando ha varias escolas na tela.

Criterios de aceite:
- inputs/select da barra de filtros (busca, municipio, UF, ordenacao)
  passam a usar o mesmo padrao de fonte (tamanho/peso) ja usado no
  restante do grid e nas demais telas do sistema — sem introduzir um
  padrao novo;
- linha expandida de RE/RI ganha uma cor de fundo visualmente distinta
  da linha da Escola e do hover padrao, para o usuario identificar de
  forma clara qual RE/RI pertence a qual escola ao expandir varias
  escolas na mesma tela;
- ajuste aplicado ao template compartilhado (`enderecos_lastmile.html`),
  valendo tanto para a tela global quanto para a tela de Setor (PO-053);
- somente CSS/classes visuais — nenhuma mudanca de dado, comportamento,
  filtro ou permissao.

Regras relacionadas: nenhuma (ajuste exclusivamente visual).

Tipo de feature: `frontend-layout` (sem QA; validacao visual do usuario).

Agente recomendado para executar:
- `dev`

### PO-056 - Parceiro de RE/RI editavel somente no Setor Lastmile, via modal de selecao

Status: `Planejada`

Objetivo:
Usuario pediu, em 2026-08-10, que o campo Parceiro de RedeExterna/RedeInterna
(hoje editavel so pelo Django Admin, pendencia da PO-051/ADR-015) passe a ser
editavel pelo grid, restrito a quem trabalha no Setor "Lastmile", e que a
selecao do Parceiro abra um modal em vez de uma lista suspensa.

Criterios de aceite (RN-030):
- Parceiro fica editavel na linha expandida de RE/RI somente quando a tela
  atual for a do Setor de negocio "Lastmile" (`setor_atual == "Lastmile"`);
  no grid global e nas telas dos demais Setores, permanece somente leitura;
- edicao abre um modal (mesmo padrao visual dos modais ja existentes no
  grid) com busca de Parceiros por nome, cidade, UF e bairro, reaproveitando
  a logica de `endereco_lastmile_partner_search` (apps.leads);
- selecionar um Parceiro no modal preenche o campo na linha; salvar
  continua sendo o botao "Salvar" ja existente (mesmo fluxo de Setor/Status);
- salvar sem RedeExterna/RedeInterna existente para aquela escola cria o
  registro (mesmo comportamento da PO-051);
- alteracao de Parceiro pela tela gera RegistroHistorico com valor
  anterior/novo (mesmo padrao da PO-054); edicao pelo Django Admin nao gera
  log;
- permissao de acesso ao grid continua `grupo_LastMile_required` — a
  restricao por Setor "Lastmile" e adicional.

Regras relacionadas: RN-030, RN-023, RN-025, RN-026, RN-029 (docs/business_rules.md).

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-057 - Cadastro de Campos personalizados por Setor (Administracao > Campos)

Status: `Aguardando QA` (implementado pelo Dev em 2026-08-10)

Objetivo:
Usuario pediu, em 2026-08-10, uma tela nova "Campos" na Administracao para
cadastrar campos dinamicos (nome, tipo e Setor dono), preparando o terreno
para reduzir a quantidade de informacao direto no grid de Enderecos
Lastmile (PO-058 depende desta).

Criterios de aceite (RN-031):
- novo model `Campo` em `apps/escolas/models.py`: `nome`, `tipo` (texto,
  numero, data, sim_nao, lista), `setor_nome` (CharField, mesmo
  vocabulario de `Setor.nome` — nao FK para uma linha especifica de Setor
  de um Processo, ver ADR-019) e `opcoes` (lista de textos, usada so
  quando `tipo="lista"`);
- tela nova em `apps.core_admin`, secao Administracao, restrita ao grupo
  Administrador (mesma permissao de Processos, PO-050): lista os Campos
  cadastrados e formulario de criacao (nome, tipo, setor dono e, quando
  tipo=lista, campo para digitar as opcoes);
- validacao: tipo lista exige pelo menos uma opcao;
- nesta versao, so listar e criar — sem editar nem excluir;
- novo item no sidebar, dentro da secao "Administracao" ja existente.

Regras relacionadas: RN-031, RN-025 (docs/business_rules.md).

Decisao arquitetural: docs/adr/ADR-019_CAMPOS_PERSONALIZADOS_POR_SETOR_EM_RE_E_RI.md

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-058 - Modal de Campos personalizados no grid de Enderecos Lastmile

Status: `Aguardando QA` (implementado pelo Dev em 2026-08-10)

**Correcao do Dev (2026-08-10):**
- Usuario reportou que um Campo tipo Numero ("velocidade", Setor Lastmile) salvava o valor, mas ele "desaparecia" ao reabrir o modal.
- Causa: `LANGUAGE_CODE=pt-br` faz o Django exibir o numero com virgula (ex.: "150,0"); um `input type="number"` so aceita ponto, entao o navegador descartava o valor ja salvo.
- Corrigido o template do modal para exibir o numero sem formatacao regional (ponto decimal).
- Adicionado teste de regressao; suite de Campos (9 testes) roda verde.

Objetivo:
Usuario pediu, em 2026-08-10, um botao no grid de Enderecos Lastmile que
abra um modal com os Campos cadastrados na PO-057, agrupados por Setor,
com visibilidade cruzada entre Setores mas edicao restrita ao Setor dono
de cada campo — reduzindo a informacao direto na linha do grid.

Criterios de aceite (RN-032):
- novo model `CampoValor` (`GenericForeignKey` para `RedeExterna`/
  `RedeInterna`, mesmo padrao de `RegistroHistorico`): guarda o valor de
  um `Campo` (PO-057) para aquela instancia especifica;
- botao na linha expandida de RE e de RI (RN-024/RN-026) abre um modal com
  os Campos aplicaveis aquele tipo de processo, agrupados por Setor dono;
- grupo do Setor da tela atual (`setor_atual`) vem expandido; os demais
  grupos vem recolhidos, abrindo so se a pessoa clicar;
- edicao habilitada somente nos campos cujo Setor dono e igual a
  `setor_atual` (mesma regra ja usada no Parceiro, RN-030); os demais
  mostram o valor, somente leitura;
- no grid global (sem `setor_atual`) e nas telas de Setor diferentes do
  dono, todos os campos aparecem somente leitura;
- valor validado conforme o tipo do Campo (ex.: lista so aceita uma das
  opcoes cadastradas);
- Setor/Status (RN-026) e Parceiro (RN-030) continuam como estao hoje,
  direto na linha do grid — nao entram neste modal;
- mesma permissao que ja protege a edicao de RE/RI no grid
  (`grupo_LastMile_required`).

Regras relacionadas: RN-032, RN-023, RN-025, RN-030, RN-031 (docs/business_rules.md).

Decisao arquitetural: docs/adr/ADR-019_CAMPOS_PERSONALIZADOS_POR_SETOR_EM_RE_E_RI.md

Dependencias: PO-057.

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-059 - Excluir Status do catalogo de Processos, por Setor

Status: `🔍 Aguardando QA` (implementado pelo Dev em 2026-08-10)

Objetivo:
Usuario pediu, em 2026-08-10, uma rota para excluir Status cadastrados
dentro de um Setor (catalogo de Processos, PO-050), resolvendo
parcialmente a pendencia de exclusao deixada pela RN-025/ADR-014 —
somente para Status; Setor e Processo continuam sem exclusao.

Criterios de aceite (ADR-020, RN-034):
- rota de exclusao de um Status individual, a partir da tela de detalhe
  do Setor (`/ferramentas/processos/<processo_pk>/setores/<setor_pk>/status/<status_pk>/excluir/`,
  POST);
- exige confirmacao explicita antes de excluir;
- RedeExterna/RedeInterna que referenciavam aquele Status ficam com
  `status` em branco (usa o `on_delete=SET_NULL` ja existente, RN-026) —
  sem apagar RE/RI nem exigir migracao nova;
- Setor e Processo continuam sem exclusao nesta versao;
- mesma permissao da tela de Processos (`grupo_Administrador_required`).

Regras relacionadas: RN-034, RN-025, RN-026 (docs/business_rules.md).

Decisao arquitetural: docs/adr/ADR-020_EXCLUSAO_DE_STATUS_DO_CATALOGO_DE_PROCESSOS_POR_SETOR.md

Dependencias: PO-050.

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-061 - Editar e excluir Campos personalizados (Administracao > Campos)

Status: `🔍 Aguardando QA` (implementado pelo Dev em 2026-08-10)

**Entrega do Dev:**
- Criadas as rotas `/ferramentas/campos/<pk>/editar/` e `/ferramentas/campos/<pk>/excluir/`.
- Edicao reaproveita o form de criacao (nome, tipo, setor dono, opcoes); troca de tipo com valores ja gravados nao e bloqueada.
- Exclusao exige confirmacao do navegador informando quantos valores serao perdidos; Campo e CampoValor somem juntos.
- Lista de Campos ganhou icones de editar e excluir por linha; corrigido problema visual no celular (acoes cortadas pelo card ao quebrar linha).
- Validado no navegador (desktop 1366px e celular 390px): listar, editar com pre-preenchimento, excluir com confirmacao.
- **Pendencia:** achado bug pre-existente, sem relacao com esta feature — teste `test_migracao_de_dados_preservou_automacoes_existentes_em_administrador` falha (AutomacaoMenu). Fora do escopo da PO-061, nao corrigido aqui.

Objetivo:
Usuario pediu, em 2026-08-10, as rotas de editar e excluir para a tela
"Campos" (Administracao, PO-057), resolvendo a pendencia "fase 2" deixada
pela ADR-019/RN-031.

Criterios de aceite (ADR-021, RN-036):
- rota de edicao de um Campo (`/campos/<pk>/editar/`), reaproveitando o
  mesmo form da criacao (nome, tipo, setor dono e opcoes quando tipo=lista);
- troca de tipo permitida mesmo com `CampoValor` (PO-058) ja gravados para
  aquele Campo, sem bloqueio nem limpeza automatica dos valores existentes;
- rota de exclusao de um Campo (`/campos/<pk>/excluir/`, POST), exigindo
  confirmacao explicita que informe quantos `CampoValor` serao perdidos;
- confirmada a exclusao, Campo e os `CampoValor` vinculados sao apagados
  em cascata (o `on_delete=CASCADE` ja existe em `CampoValor.campo` — sem
  migracao nova);
- mesma permissao das demais operacoes da tela (`grupo_Administrador_required`).

Regras relacionadas: RN-036, RN-031, RN-032 (docs/business_rules.md).

Decisao arquitetural: docs/adr/ADR-021_EDICAO_E_EXCLUSAO_DE_CAMPOS_PERSONALIZADOS_POR_SETOR.md

Dependencias: PO-057.

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-062 - Tela "Setor": Setor informativo com Campos fixos, somente leitura em Escola e/ou RE/RI

Status: `Planejada`

> **Correcao (2026-08-10):** a primeira versao desta PO (baseada na RN-037/
> ADR-022) partiu de um entendimento errado — o Dev chegou a implementar
> essa primeira versao (model `SetorEscopo`, tela ligada ao catalogo de
> Processos, escopo exclusivo, valor por instancia) antes do usuario
> corrigir o pedido real. Ver "Rework necessario" no fim desta PO.

Objetivo:
Usuario pediu, em 2026-08-10, uma tela nova "Setor" na Administracao,
independente de "Processos" (PO-050) e "Campos" (PO-057): criar um Setor
informativo, adicionar Campos fixos (nome + valor) a ele, e escolher em
quais lugares esses campos aparecem — Escola, Rede Externa (RE), Rede
Interna (RI), podendo marcar mais de um ao mesmo tempo. Os campos aparecem
somente como visualizacao (nunca editaveis) dentro do modal de Campos ja
existente no grid de Enderecos Lastmile (PO-058), como mais um grupo.

Criterios de aceite (RN-038, ADR-023):
- dois models novos em `apps/escolas/models.py`, sem vinculo com `Setor`
  (RN-025) nem com `Campo`/`CampoValor` (RN-031/032): `SetorInformativo`
  (`nome`, unico; `aparece_escola`, `aparece_re`, `aparece_ri`, booleanos,
  pelo menos um marcado) e `CampoInformativo` (`setor_informativo` FK,
  `nome`, `valor` texto livre e fixo — nao varia por Escola/RE/RI);
- tela nova "Setor" em `apps.core_admin`, secao Administracao, mesma
  permissao das demais (`grupo_Administrador_required`): cria o Setor
  informativo (nome + onde aparece) e, na mesma tela, adiciona/edita/
  remove os Campos informativos dele (nome + valor);
- lista os Setores informativos cadastrados, com os Campos de cada um e
  onde aparecem;
- no modal de Campos ja existente no grid de Enderecos Lastmile (PO-058),
  a linha de RE ganha um grupo adicional por `SetorInformativo` com
  `aparece_re=True`; a linha de RI, por `aparece_ri=True` — cada grupo
  mostra `nome: valor` de cada Campo informativo como texto, nunca como
  campo de formulario editavel, independente de `setor_atual`;
- na linha da Escola (grid de Enderecos Lastmile), um botao equivalente
  abre um modal listando os Campos de todo `SetorInformativo` com
  `aparece_escola=True` — mesmo padrao visual, sem formulario nem botao
  "Salvar" (somente leitura);
- o unico lugar que edita `CampoInformativo.valor` e a propria tela
  "Setor" da Administracao.

Regras relacionadas: RN-038, RN-025, RN-031, RN-032 (docs/business_rules.md).

Decisao arquitetural: docs/adr/ADR-023_SETOR_INFORMATIVO_COM_CAMPOS_FIXOS_SOMENTE_LEITURA.md
(substitui a ADR-022, mantida no histórico só para registrar o entendimento errado).

Dependencias: PO-058 (modal de Campos ja existente, onde os grupos novos entram).

Rework necessario (achado do Dev ao implementar a versao errada, 2026-08-10):
- migration `apps/escolas/migrations/0010_setor_escopo.py` (ja aplicada no
  banco `speed_prod`) e o model `SetorEscopo` precisam ser revertidos/
  removidos e substituidos pelos models corretos desta PO;
- tela `core_admin/setor_escopo_list.html`, view `setor_escopo_list`/
  `setor_escopo_editar`, form `SetorEscopoForm` e as rotas
  `/ferramentas/setor-escopo/` precisam ser removidas e recriadas com o
  desenho correto;
- o filtro por escopo aplicado em `campos_grid_rede`/`salvar_campos_rede`
  (`apps/leads/services.py`) e o modal/rota `escola_campos` criados para a
  versao errada devem ser removidos (a exibicao correta usa grupos novos
  no modal existente, nao um modal separado com formulario);
- nenhuma tela ja em producao (Campos, Processos, Enderecos Lastmile) foi
  quebrada por esse trabalho — suite completa (260 testes) permanece
  passando; o rework e local aos arquivos acima.

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-063 - Campo condicionado a Status e Campo calculado (Inicio/Data Final Implantacao)

Status: `🔍 Aguardando QA` (implementado pelo Dev em 2026-08-11)

**Entrega do Dev:**
- Campo (Administracao > Campos), para qualquer Setor, ganhou o campo opcional "Status condicionante" e o novo tipo "Calculado" (com Campo base e Horas de prazo) — mecanismo generico, sem codigo novo para casos futuros parecidos.
- Modal de Campos (grid de Enderecos Lastmile e Escola) passa a esconder um Campo com Status condicionante quando o Status atual do RE/RI nao bate, e a mostrar o Campo Calculado somente leitura, com o valor derivado ao vivo (Campo base + Horas de prazo, em dias corridos, arredondado para cima).
- Excluir um Campo usado como base de um Campo Calculado agora e bloqueado, avisando quais campos dependem dele.
- Corrigido o erro 500 reportado ao abrir o modal de Campos (RE/RI e Escola): a causa foi a migration das colunas novas do Campo ainda nao aplicada no banco deste ambiente; aplicada agora (alteracao apenas aditiva, sem perda de dado) e reconferida sem erro nos tres modais, com e sem Campo condicionado/calculado configurado.
- Testes da RN-039 e regressao de Escolas/Leads (159 testes) executados e passando.
- **Pendencia:** configuracao de dados (Status "Agendando Parceiro" nos Processos de RE/RI do Setor "Implantacao"; Campos "Inicio Implantacao" e "Data Final Implantacao") fica para depois, fora do escopo do Dev; validacao visual em navegador continua nao executada neste ambiente (sem credencial disponivel), mas o fluxo real dos tres modais foi reproduzido via requisicoes autenticadas sem erro.

Objetivo:
Usuario pediu, em 2026-08-11, que o Setor "Implantacao" (RN-025), ao
receber o Status "Agendando Parceiro" em um RE/RI, mostre um campo "Inicio
Implantacao" (data combinada com o parceiro) e calcule automaticamente,
72 horas depois, um campo "Data Final Implantacao", somente visual e nao
editavel. Confirmado com o usuario que o mecanismo deve ser generico
(reutilizavel por qualquer Setor/Status no futuro, direto pela tela
"Campos") e que a precisao e somente de data (dia), sem horario.

Criterios de aceite (RN-039, ADR-024):
- tela "Campos" (PO-057/061) ganha campo opcional "Status condicionante"
  no cadastro de qualquer Campo — quando preenchido, o Campo so aparece no
  modal de Campos do grid (PO-058) quando o Status atual do RE/RI exibido
  tiver esse mesmo nome; sem preenchimento, comportamento atual;
- novo tipo de Campo "Calculado", exigindo no cadastro um "Campo base"
  (outro Campo do mesmo Setor, tipo Data) e "Horas de prazo" (inteiro
  positivo);
- valor de um Campo calculado nunca e digitado nem salvo — e derivado ao
  vivo a partir do valor atual do Campo base, somando os dias corridos
  equivalentes as Horas de prazo; aparece em branco se o Campo base ainda
  nao tiver valor; sempre somente leitura, em qualquer Setor/tela;
- configuracao de dados desta entrega (feita depois do Dev entregar, sem
  ser codigo): Status "Agendando Parceiro" criado nos Processos de RE e RI
  do Setor "Implantacao" (tela ja existente, PO-059); Campo "Inicio
  Implantacao" (Data, Status condicionante = "Agendando Parceiro") e Campo
  "Data Final Implantacao" (Calculado, Campo base = "Inicio Implantacao",
  Horas de prazo = 72), ambos no Setor "Implantacao", cadastrados pela
  tela "Campos".

Regras relacionadas: RN-039, RN-025, RN-026, RN-031, RN-032, RN-034, RN-036
(docs/business_rules.md).

Decisao arquitetural: docs/adr/ADR-024_CAMPO_CONDICIONADO_A_STATUS_E_CAMPO_CALCULADO.md

Dependencias: PO-057, PO-058, PO-059, PO-061.

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-064 - Historico de alteracao de Campo personalizado, com valor calculado embutido

Status: `🔍 Aguardando QA` (implementado pelo Dev em 2026-08-11)

**Entrega do Dev:**
- Toda alteracao de valor de Campo pela tela (RE/RI e Escola) passa a gerar um registro de historico do sistema, com valor anterior e novo.
- Primeiro valor de um Campo (sem valor anterior) registra "(vazio)"; reenviar o mesmo valor nao duplica o historico.
- Campo do tipo Calculado nunca gera historico proprio; ao alterar o Campo base dele, o mesmo registro tambem traz o valor calculado resultante daquele momento.
- Edicao direta pelo Django Admin continua sem gerar esse log, mesmo padrao ja usado para Setor/Status/Parceiro.
- Testes da RN-040 e regressao de Leads/Escolas (162 testes) executados e passando.
- **Pendencia:** sem alteracao visual nesta entrega — formato De/Para e largura do modal entram na PO-065.

Objetivo:
Usuario pediu, em 2026-08-11, que "Inicio Implantacao" e "Data Final
Implantacao" (PO-063) ficassem registrados no historico de RE/RI/Escola.
Confirmado com o usuario o alcance generico: qualquer Campo personalizado
(PO-057/058, qualquer Setor) passa a gerar historico, nao somente os de
Implantacao.

Criterios de aceite (RN-040):
- toda alteracao de valor de Campo (modal de Campos, RE/RI e Escola) gera
  `RegistroHistorico` com valor anterior/novo — mesmo padrao ja usado para
  Setor/Status/Parceiro (PO-054);
- edicao direta no Django Admin nao gera esse log (mesmo padrao existente);
- Campo do tipo Calculado (PO-063) nunca gera log proprio (nunca e salvo);
  quando o respectivo Campo base e alterado, o mesmo registro de historico
  tambem traz o valor calculado resultante daquele momento;
- entradas aparecem junto com as demais no historico de RE/RI/Escola,
  mesma ordem cronologica, sem modal separado.

Regras relacionadas: RN-040, RN-029, RN-031, RN-032, RN-039 (docs/business_rules.md).

Dependencias: PO-054, PO-058, PO-063.

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-065 - Historico com formato De/Para, Setor capturado, e modal mais largo e denso

Status: `🔍 Aguardando QA` (implementado pelo Dev em 2026-08-11; ajuste de RN-041 ampliada aplicado pelo Dev antes da revisao do QA)

**Entrega do Dev (2026-08-11):**
- Historico do sistema (Setor/Status, Parceiro e Campo) passa a guardar rotulo, valor anterior, valor novo e o Setor no momento do registro; quando mais de um campo muda no mesmo salvamento (ex.: cascata Setor→Status), cada campo agora gera seu proprio registro, no mesmo instante e Setor (ajuste RN-041 ampliada).
- Modal de historico mostra rotulo e "valor anterior → valor novo" na mesma linha quando cabe, com data/hora/usuario/Setor numa linha abaixo; registro antigo continua exibido como frase, e Setor nao capturado aparece como "—".
- Corrigido bug reportado pelo usuario: rotulo grande (ex.: nome extenso de Campo) ficava cortado no modal; agora, quando nao ha espaco na mesma linha, o bloco "valor anterior → valor novo" desce para a linha seguinte em vez de cortar o texto — testado ate com rotulo bem mais longo que o caso relatado, sem corte.
- Modal ficou cerca de 20% mais largo e com menos espaco vazio entre os blocos de informacao.
- Validacao visual em navegador executada (celular 390px, tablet 768px e desktop 1366px) e testes da RN-041 e regressao de Leads (135 testes) executados e passando.
- **Pendencia:** achado nesta rodada, fora do escopo do bug relatado — a linha de "adicionar comentario/anexo" do modal de RE/RI tem leve rolagem horizontal no celular (390px); fica registrado para tratamento em item futuro.

Objetivo:
Usuario pediu, em 2026-08-11, que a alteracao de Campo (PO-064) aparecesse
no historico em formato "De/Para" na mesma linha, com data/hora/usuario/
Setor numa linha abaixo, alem de aumentar a largura do modal em 20% e
reduzir o espaco vazio entre as informacoes. Como `RegistroHistorico` hoje
so guarda uma frase livre (sem Setor capturado), a estruturacao vale para
qualquer registro tipo sistema — Setor/Status (PO-051), Parceiro (PO-056)
e Campo (PO-064) — nao somente Campo.

Criterios de aceite (RN-041):
- `RegistroHistorico` ganha campos estruturados (rotulo, valor anterior,
  valor novo, Setor no momento do registro), usados so pelo tipo sistema;
- geracao de log das PO-051 (Setor/Status), PO-056 (Parceiro) e PO-064
  (Campo) passa a preencher esses campos, em vez de so uma frase livre;
- registros ja existentes continuam exibidos como estao, sem migracao
  retroativa;
- modal de historico (PO-054) exibe rotulo + "valor anterior → valor novo"
  na mesma linha (separado por uma coluna), com data/hora/usuario/Setor
  numa linha abaixo; Setor nao capturado mostra "—";
- modal com 20% mais de largura e espacamento reduzido entre os blocos de
  informacao (comentario/anexo e cada entrada do historico);
- quando mais de um campo mudar no mesmo salvamento (ex.: cascata
  Setor→Status), cria um registro estruturado por campo alterado — nao um
  unico registro com frase combinada.

Regras relacionadas: RN-041, RN-026, RN-029, RN-030, RN-040 (docs/business_rules.md).

Dependencias: PO-051, PO-054, PO-056, PO-064.

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-066 - Envio de e-mail pelo ticket principal (Escola) e pelos sub-tickets (RE/RI), com log conforme RN-029

Status: `🔍 Aguardando QA` (implementado pelo Dev em 2026-08-11; ajustes pontuais em 2026-08-11; nova correcao em 2026-08-11)

**Entrega do Dev:**
- Escola, RE e RI ganharam a opcao de enviar e-mail direto no modal de historico ja existente (RN-029) — sem tela nova.
- E-mail enviado (e a resposta) pelo RE fica so no historico do RE; pelo RI, so no historico do RI; pela Escola, no historico da Escola e visivel na visao combinada de RE e RI (mesmo modal).
- Reaproveitada a mesma caixa de e-mail (Microsoft Graph) ja usada para cotacao, com numero de rastreio proprio no assunto (data + INEP + RE/RI/Global).
- Correcao (2026-08-11): a exclusao mutua entre o anexo do comentario e o anexo do e-mail passou a ser ligada por script (nao mais por atributo solto no HTML), reaplicada toda vez que o modal e recarregado — antes disso, um novo carregamento do modal podia deixar os dois anexos ativos ao mesmo tempo.
- Correcao (2026-08-11): o formulario de "Enviar e-mail" ganhou rolagem propria dentro do modal — antes disso, com o formulario aberto, o botao de anexo e o botao de enviar ficavam fora da area visivel do modal (cortados), sem forma de rolar até eles.
- Validado em navegador (Chromium/Playwright) simulando clique real do usuario, nas larguras de celular, tablet e desktop: exclusao mutua confirmada (o anexo do comentario so aceita arquivo quando "Enviar e-mail" esta fechado) e os dois botoes do e-mail (anexo e enviar) aparecem completos apos rolar o modal, sem corte e sem rolagem horizontal indevida.

Objetivo:
Adequar a opcao de e-mail do sistema ao layout atual de Escola (ticket
principal, RN-023) e RE/RI (sub-tickets): permitir enviar e-mail a partir da
tela da Escola ou a partir da tela de RE/RI, com o envio e a resposta caindo
no historico do nivel correto, reaproveitando a mesma regra de visibilidade
individual/combinada ja usada pelo modal de historico (RN-029).

Contexto:
Usuario identificou, em 2026-08-11, que a opcao de e-mail hoje configurada no
sistema (`apps/core_admin` — `ConfiguracaoEmailEnvio`/`smtp_test_form.html`)
nao esta vinculada a nivel de Escola/RE/RI, e que o layout atual exige essa
distincao: log de RE e de RI individuais entre si; e-mail enviado pela Escola
visivel pelas duas sub-atividades. O sistema ja tem um mecanismo equivalente
em outro dominio — sincronizacao de respostas de e-mail via Microsoft Graph,
hoje restrita a cotacao/`Proposal` (correlaciona resposta a registro de
origem por um codigo no assunto e grava o resultado em `RegistroHistorico`,
`apps/integracoes/email/sincronizar_respostas_email_cotacao.py`).

Criterios de aceite (RN-042):
- tela da Escola, do RE e do RI ganham a opcao de enviar e-mail (reaproveitando
  o modal de historico ja existente, RN-029, ou local equivalente, a criterio
  do Dev);
- e-mail enviado a partir do RE (e a resposta correspondente) aparece somente
  no historico do RE; o mesmo vale para o RI — nunca aparecem um no outro;
- e-mail enviado a partir da Escola (e a resposta correspondente) aparece no
  historico da Escola e e visivel na visao combinada de RE e RI (mesmo modal
  combinado da RN-029);
- **decisao do usuario (2026-08-11):** a resposta recebida e correlacionada ao
  nivel de origem (Escola, RE ou RI) por um numero de rastreio unico composto
  por data do dia do envio + INEP da Escola + sufixo do nivel (`RE`, `RI` ou
  `Global`, sendo `Global` a Escola/ticket principal); formato exato de
  separadores/ordem no assunto do e-mail e a criterio do Dev, mantendo esses
  tres componentes — reaproveitando o mesmo mecanismo de extracao/correlacao
  por codigo no assunto ja usado para cotacao, sem inventar um mecanismo novo;
- **decisao do usuario (2026-08-11):** reaproveitar a mesma caixa de
  e-mail/credenciais do Microsoft Graph ja configuradas para cotacao — sem
  caixa/configuracao separada para Escola/RE/RI;
- por ser a mesma caixa compartilhada entre cotacao e Escola/RE/RI, o sistema
  precisa manter rastreio explicito de cada e-mail: o numero de rastreio
  (acima), a qual registro especifico ele pertence, remetente, destinatario,
  assunto e data — mesmo padrao de registro de correlacao ja usado para
  cotacao (`EmailCotacaoRespostaImportacao`), evitando que um e-mail de
  cotacao seja confundido com um de Escola/RE/RI ou vice-versa;
- mesma permissao que ja protege a tela de RE/RI no grid
  (`grupo_LastMile_required`, RN-029).

Regras relacionadas: RN-042, RN-023, RN-029 (docs/business_rules.md).

Dependencias: PO-054 (historico individual/combinado de RE/RI).

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-067 - Mapa Calor: terceira subatividade fixa da Escola, no mesmo molde de RE/RI

Status: `🔍 Aguardando QA` (implementado pelo Dev em 2026-08-11)

**Entrega do Dev:**
- Criado o Mapa Calor como terceiro processo da Escola, no mesmo molde de Rede Externa/Rede Interna (setor, status, parceiro, dados adicionais, histórico e Campos personalizados).
- Grid de Endereços Lastmile ganhou a terceira linha expansível (Mapa Calor), com cascata Setor→Status, trava de Status pelo Setor atual e Parceiro editável só na tela do Setor "Lastmile" — igual a RE/RI.
- Histórico individual do Mapa Calor e a visão combinada da Escola (agora com RE + RI + Mapa Calor) e envio de e-mail por sub-ticket (terceiro sufixo "MC") implementados.
- Tela "Setor" (Administração) ganhou a opção "Mapa Calor (MC)" no escopo por Setor.
- Testes das regras herdadas (RN-023 a RN-042) aplicadas ao Mapa Calor e regressão completa de Escolas/Leads/Core/Core Admin/Integrações de e-mail (380 testes) executados e passando.
- **Correção (2026-08-12):** faltava o Processo padrão "Mapa Calor (MC)" — a tela de Processos (Administração) já é genérica e funcionava para qualquer Processo, mas RE/RI têm esse registro semeado automaticamente desde a implementação original (RN-025/PO-050) e o equivalente do Mapa Calor não tinha sido criado. Adicionada migration de dados semeando o Processo "Mapa Calor (MC)" com os mesmos Setores/Status de teste que RE/RI já têm; ajustado um teste que colidia com esse novo dado. Testes de Escolas/Leads/Core Admin/Integrações de e-mail (344 testes) executados e passando.
- **Pendência:** validação visual em navegador não executada neste ambiente (sem acesso a browser); renderização das telas foi conferida via requisições HTTP autenticadas (grid, modais de histórico/campos e tela de Administração), sem erro. Encontrada, e não corrigida por estar fora do escopo desta feature, uma falha pré-existente e não relacionada em `apps.core_admin.tests.AutomacaoMenuTests`.

**Achado do Orquestrador (2026-08-12) — verificação documental, sem alterar código:**
usuário relatou que RE e RI têm um Processo onde é possível criar Status, e
isso não aparece para Mapa Calor. Conferido: RN-043 e os critérios de
aceite desta PO (acima) já exigiam explicitamente que "Mapa Calor tenha seu
próprio Processo, com Setores e Status cadastráveis como qualquer outro" —
a regra e o critério **cobrem** o caso; não é lacuna de especificação. A
"Entrega do Dev" registrada acima (2026-08-11) não menciona a criação/
semeadura de um Processo "Mapa Calor" nem qualquer alteração na tela
Processos (PO-050) — os dois Processos hoje existentes (Rede Externa/Rede
Interna) vieram de uma semeadura de dados feita na própria PO-050
(`apps/escolas/migrations/0006_seed_processos_setores_status_teste.py`),
não de código genérico que crie um Processo automaticamente para cada
subatividade nova. Ou seja: **possível divergência real entre critério de
aceite e entrega**, não apenas falta de nota na documentação — QA deve
verificar explicitamente, antes de aprovar, se existe hoje um Processo
utilizável para Mapa Calor (seedado por migration ou criável pela tela
Processos sem passo extra não documentado). Investigação técnica da causa
está em andamento pelo Dev em paralelo (agente separado); este registro é
só a checagem documental/de regra, sem duplicar a correção.

Objetivo:
Usuario pediu, em 2026-08-11, a possibilidade de criar subatividades sem
digitar codigo, escolhendo em qual atividade principal cada uma aparece ou
aplicando a todas. Investigacao do Orquestrador confirmou que hoje existe
uma unica atividade principal (Escola) e que RE/RI sao dois models Django
fixos e hardcoded, nao um catalogo dinamico — generalizar isso e refatoracao
de grande porte, com risco de regressao nas 20 regras ja em producao
(RN-023 a RN-042). Apresentadas as alternativas, o usuario decidiu (ver
ADR-025) adiar a generalizacao e manter o pedido concreto imediato: uma
terceira subatividade fixa, "Mapa Calor", implementada em codigo pelo Dev no
mesmo molde de RE/RI — **nao** um cadastro pelo usuario via Admin.

Contexto:
Mesmo espirito da RN-023/ADR-012 (RE e RI como processos independentes por
Escola), estendido para um terceiro processo. Mapa Calor recebe o conjunto
completo de campos e comportamentos que RE/RI ja tem hoje (setor, status,
parceiro, dados adicionais, processo padrao, historico, Campos
personalizados por Setor e envio de e-mail por sub-ticket) — decisao do
usuario em 2026-08-11 de replicar integralmente, sem reduzir escopo.

Criterios de aceite (RN-043):
- novo model `MapaCalor(ProcessoRedeBase)` em `apps/escolas/models.py`,
  reaproveitando a mesma classe abstrata ja usada por `RedeExterna`/
  `RedeInterna` (setor, status, parceiro, dados_adicionais), com
  `escola = OneToOneField(Escola, on_delete=CASCADE,
  related_name="mapa_calor")` e `processo = ForeignKey("Processo", ...,
  related_name="mapas_calor")` (mesmo padrao de `NOME_PROCESSO_PADRAO` de
  RE/RI, PO-048); migration aditiva; registrado no Django Admin no mesmo
  padrao de `RedeExterna`/`RedeInterna`;
- catalogo de Processo/Setor/Status (RN-025, PO-050): Mapa Calor tem seu
  proprio Processo, com Setores e Status cadastraveis como qualquer outro;
- grid de Enderecos Lastmile (PO-049/051): linha da Escola ganha uma
  terceira linha expansivel para Mapa Calor, com edicao de Setor/Status em
  cascata (RN-026), incluindo a trava de Status pelo Setor atual e o
  "Aguardando" automatico ao trocar de Setor (RN-033/PO-051), e a exclusao
  de Status por Setor (RN-034/PO-059);
- Parceiro de Mapa Calor segue a mesma regra de RE/RI (RN-030/PO-056):
  editavel somente na Tela de Setor "Lastmile", via modal de selecao;
- visao por Setor (RN-027/028, PO-052/053) passa a agregar tambem Mapa
  Calor, alem de RE e RI, ao listar as atividades vinculadas a um Setor;
- historico e anexo individuais de Mapa Calor (RN-029/041, PO-054/065),
  com a visao combinada da Escola passando a reunir os tres processos
  (RE, RI e Mapa Calor), nao somente RE+RI;
- modal de Campos personalizados por Setor (RN-031/032, PO-057/058),
  incluindo Campo condicionado a Status e Campo calculado (RN-039/040,
  PO-063/064), disponivel para Mapa Calor no mesmo padrao de RE/RI;
- envio de e-mail (RN-042/PO-066): Mapa Calor passa a ser um terceiro
  "sub-ticket" — envio/resposta a partir dele fica so no historico dele; o
  numero de rastreio ganha um terceiro sufixo de nivel (ao lado de `RE`/
  `RI`/`Global`);
- **fora de escopo desta feature** (ver ADR-025): nenhum cadastro
  administravel de subatividades pelo Admin; nenhuma alteracao para suportar
  mais de uma atividade principal alem de Escola. Mapa Calor e uma terceira
  subatividade fixa, escrita em codigo, exatamente como RE e RI ja sao;
- testes cobrindo: criacao de Mapa Calor vinculado a uma Escola,
  independencia de setor/status/parceiro em relacao a RE e RI da mesma
  Escola, cascata Setor→Status, historico individual e combinado, e o
  terceiro grupo de Campos personalizados no modal.

Regras relacionadas: RN-043, RN-023, RN-025, RN-026, RN-027, RN-028, RN-029,
RN-030, RN-031, RN-032, RN-033, RN-034, RN-039, RN-040, RN-041, RN-042
(docs/business_rules.md).

Decisao arquitetural: docs/adr/ADR-012_PROCESSOS_REDE_EXTERNA_E_REDE_INTERNA_POR_ESCOLA.md
(mesmo padrao reaproveitado para o terceiro processo); decisao de adiar a
generalizacao em docs/adr/ADR-025_GENERALIZACAO_DE_SUBATIVIDADES_E_MULTIPLAS_ATIVIDADES_ADIADA.md.

Dependencias: PO-048 (model base `ProcessoRedeBase`), PO-050 (catalogo de
Processo/Setor/Status), PO-051 (cascata Setor/Status no grid), PO-054
(historico individual/combinado), PO-057/058 (Campos personalizados e
modal), PO-066 (envio de e-mail por sub-ticket) — todas ja concluidas ou em
Aguardando QA; nao ha dependencia do rework do PO-062 (Setor informativo),
que segue em paralelo por decisao do usuario.

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-068 - Cotacao de RE/RI com multiplos parceiros candidatos, com selecao de um vencedor

Status: `🔍 Aguardando QA` (implementado pelo Dev em 2026-08-12)

**Entrega do Dev:**
- Criado o model `CotacaoParceiro` (apps.escolas), com Parceiro candidato + situação (Em cotação/Selecionado/Recusado) vinculado a um RE ou RI via `GenericForeignKey` (mesmo padrão de `CampoValor`/`RegistroHistorico`).
- "Cotação" semeado como Status do catálogo (Setor "Lastmile", Processos de RE e RI) por migration de dados, sem precisar de cadastro manual pela tela de Processos.
- Linha expandida da Tela do Setor "Lastmile" ganhou um modal de gestão de cotação (mesmo padrão visual dos demais modais do grid) quando o RE/RI exibido está no Status "Cotação": busca e adiciona Parceiro candidato, lista situação de cada um e permite remover quem ainda não foi selecionado.
- Marcar "Selecionado" move os demais candidatos do mesmo RE/RI para "Recusado", preenche o Parceiro do RE/RI e gera o histórico Antes/Depois já usado para Parceiro — sem mudar o Status automaticamente.
- Testes do caminho principal (adicionar/selecionar/remover candidato, histórico gerado), da permissão/trava (fora do Setor Lastmile, fora do Status Cotação, sem grupo LastMile) e de regressão (Parceiro, histórico e grid de Endereços Lastmile) executados e passando (215 testes de `apps.leads`/`apps.escolas`, mais 83 de `apps.partners`).
- **Pendência/divergência técnica para o Orquestrador:** a ADR-026 previa a regra de "vencedor único" também como `UniqueConstraint` condicional no banco — o MySQL de produção não suporta índice único condicional (Django confirma via `models.W036`), então essa camada só é reforçada no código (camada de serviço), não no banco. Validação visual em navegador não executada nesta sessão (sem credencial do grupo "LastMile" disponível); renderização conferida via testes automatizados que percorrem as rotas/templates reais (200 e conteúdo esperado).

Objetivo:
Usuario pediu, em 2026-08-12, para adaptar a arquitetura atual um processo
que ja existe na arquitetura antiga: quando o RE ou RI estiver no Setor
"Lastmile" com Status de Cotacao, o analista precisa poder vincular aquele
RE/RI a varios Parceiros candidatos, sabendo que so um vai seguir.

Criterios de aceite (RN-044):
- "Cotacao" existe como Status do catalogo Setor/Status (RN-025) para o
  Setor "Lastmile", nos Processos de RE e de RI;
- com o RE/RI nesse Status, a linha expandida da Tela do Setor "Lastmile"
  ganha um controle que abre um modal de gestao de cotacao (mesmo padrao
  visual dos demais modais do grid);
- modal permite adicionar Parceiros candidatos (mesma busca por nome/
  cidade/UF/bairro da RN-030), listar candidatos com sua situacao (Em
  cotacao/Selecionado/Recusado) e remover candidato ainda nao selecionado;
- marcar um candidato como "Selecionado" move os demais daquele RE/RI para
  "Recusado" automaticamente — nunca mais de um "Selecionado" por vez;
- confirmar o "Selecionado" preenche o campo Parceiro do RE/RI (RN-030),
  gerando `RegistroHistorico` no mesmo padrao Antes/Depois ja usado (RN-041);
- modal disponivel somente na Tela do Setor "Lastmile" (`setor_atual ==
  "Lastmile"`), dentro da permissao `grupo_LastMile_required` ja existente;
- trocar o Status para fora de "Cotacao" continua manual (RN-026/RN-033) —
  selecionar o vencedor nao dispara essa troca;
- fora do escopo: Mapa Calor e dados comerciais por candidato (ADR-026).

Regras relacionadas: RN-044, RN-023, RN-025, RN-026, RN-030, RN-033, RN-041
(docs/business_rules.md). Decisao tecnica: ADR-026 (docs/adr/).

Dependencias: nenhuma — reaproveita catalogo (RN-025), busca de Parceiro
(RN-030) e historico (RN-029/041) ja existentes.

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-069 - Provedores: tela em grid para listar e cadastrar Partner, dentro do menu Projeto

Status: `🔍 Aguardando QA` (implementado pelo Dev em 2026-08-12)

**Entrega do Dev:**
- Criadas as telas `provedores_list` (grid) e `provedores_create` (cadastro), em `apps/partners`, listando/criando `Partner` com os campos Razão Social, Nome Fantasia, CNPJ/CPF, Contato, E-mail, Telefone e Status — reaproveitando `PartnerForm` já existente (campos já eram uma lista explícita, sem `__all__`, nenhum ajuste de segurança necessário).
- No submenu "Projeto", o item antigo (`lead_list`) foi renomeado para "Leads" e ganhou um item novo "Provedores" apontando para a tela nova; nenhuma rota mudou.
- Ambas as telas nova protegidas por `grupo_LastMile_required` (reaproveitado de `apps.leads.views`, mesmo precedente já usado em `apps/core_admin`); tela "Parceiros" (grupo Parceiro) não foi tocada.
- Testes do caminho principal (listagem e criação), permissão (bloqueio sem grupo LastMile), validação (CNPJ/CPF duplicado gera erro de formulário, não 500) e regressão do rótulo "Leads" executados e passando (10 testes novos; suíte completa de `apps.leads`/`apps.partners`/`apps.core`, 294 testes, sem quebras).
- Telas verificadas de ponta a ponta via requisições HTTP autenticadas (login, grid nas 3 páginas, criação com redirecionamento e exibição do novo registro) — sem erro de servidor. Validação visual em navegador (Chrome) não executada nesta sessão por falta da extensão configurada; layout segue o mesmo padrão Tailwind já aprovado em `enderecos_lastmile.html`/`lead_form.html`.
- **Pendência:** revisão do QA; renderização visual completa (celular/desktop) ainda não conferida em navegador de verdade.

Objetivo:
Usuario pediu, em 2026-08-12, que a aba "Provedores" (dentro de Projeto)
mostre todos os provedores cadastrados e permita cadastrar um novo.
Investigacao do Orquestrador encontrou que esse item hoje abre a tela de
Leads, nao um cadastro de provedores — o cadastro real (`partners.Partner`)
vive em outra secao do menu ("Parceiros"), sem tela de criar novo.
Confirmado que "Provedores" deve ser o cadastro de Partner, em tela nova e
independente, sem alterar a tela "Parceiros" existente.

Criterios de aceite (RN-045):
- item de menu "Provedores" (submenu de Projeto) abre tela em grid com
  todos os `Partner` cadastrados — colunas Nome Fantasia/Razao Social,
  CNPJ/CPF, Contato, E-mail, Telefone, Status;
- botao "Novo Provedor" abre formulario com os campos basicos (Razao
  Social, Nome Fantasia, CNPJ/CPF, Contato, E-mail, Telefone, Status),
  reaproveitando `PartnerForm` (`apps/partners/forms.py`);
- item de menu atual "Provedores" (que abre `lead_list`) e renomeado para
  "Leads", mantendo a mesma rota — a tela de Leads nao pode ficar sem
  acesso pelo menu;
- tela nova protegida por `grupo_LastMile_required` (mesma permissao do
  restante do menu Projeto);
- tela "Parceiros" (grupo "Parceiro", propostas/cotacoes) permanece
  inalterada;
- fora do escopo: editar/excluir Partner nesta tela nova.

Regras relacionadas: RN-045, RN-030, RN-044 (docs/business_rules.md).

Dependencias: nenhuma — reaproveita `Partner`/`PartnerForm` ja existentes.

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-070 - Provedores: remover item "Leads" do menu e adicionar edicao de Partner

Status: `🔍 Aguardando QA`

**Entrega do Dev:**
- Removido o item "Leads" do submenu Projeto; a rota `lead_list` continua
  respondendo normalmente, so sem entrada no menu.
- Criada a edicao de Provedor (Partner), reaproveitando o mesmo formulario
  do cadastro (Razao Social, Nome Fantasia, CNPJ/CPF, Contato, E-mail,
  Telefone, Status).
- Acao "Editar" adicionada em cada linha do grid de Provedores.
- Aplicadas as regras RN-046 e RN-045 (protecao `grupo_LastMile_required`,
  bloqueio de CNPJ/CPF duplicado sem erro 500).
- Testes de permissao, caminho principal, validacao e regressao do menu
  executados com sucesso.
- **Pendencia:** ha um debito de commits ja identificado em sessoes
  anteriores (PO-068/PO-069 misturadas com trabalho grande nao commitado
  nos mesmos arquivos); esta entrega tambem nao foi commitada por isso -
  decisao caberia ao Orquestrador.

Objetivo:
Usuario aprovou a tela de Provedores (PO-069) e pediu, em 2026-08-12, para
retirar do menu o item que ficou como "Leads" (criado pela RN-045 so para
nao perder acesso aquela tela antiga) e para acrescentar uma rota de editar
um Provedor (Partner) ja cadastrado.

Criterios de aceite (RN-046):
- item de menu "Leads" (submenu Projeto) e removido de
  `apps/core/templates/core/base.html`; a rota/view `lead_list` continua
  existindo no codigo, so sem entrada de navegacao;
- nova rota de edicao de `Partner`, com os mesmos campos basicos do
  cadastro (RN-045): Razao Social, Nome Fantasia, CNPJ/CPF, Contato,
  E-mail, Telefone, Status — reaproveitando `PartnerForm`;
- acesso a edicao a partir da tela de grid "Provedores" (acao por linha),
  protegido pela mesma permissao `grupo_LastMile_required`;
- fora do escopo: exclusao de Partner (nao pedida).

Regras relacionadas: RN-046, RN-045 (docs/business_rules.md).

Dependencias: PO-069 (tela de grid/cadastro de Provedores).

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

## Ajustes pontuais (sem epico)

### PO-060 - Renomear rotulos do menu "LastMile" e "Cotacao" para "Projeto" e "Endereços"

Status: `👤 Aguardando validação visual` (implementado pelo Dev em 2026-08-10)

**Entrega do Dev:**
- Trocado o texto do cabecalho do submenu de "LastMile" para "Projeto" em
  `apps/core/templates/core/base.html`.
- Trocado o texto do item de submenu de "Cotacao" para "Endereços" no mesmo
  arquivo.
- Nenhuma rota, `has_group`, nome de URL ou arquivo foi alterado — confirmado
  lendo o trecho apos a edicao.
- Container `speed_sistema` reiniciado (cache de template com `DEBUG=False`);
  app volta a responder normalmente (login 200, sem erro nos logs).
- Validação visual em navegador: não executada — a tela exige usuário do
  grupo "LastMile" autenticado e não há credencial de teste disponível para
  esta sessão.
- **Pendência:** validação visual do usuário no navegador (abrir o submenu e
  confirmar "Projeto" e "Endereços").

Objetivo:
Usuario pediu, em 2026-08-10, para trocar os textos exibidos no submenu
principal (`apps/core/templates/core/base.html`): o cabecalho do grupo hoje
rotulado "LastMile" passa a se chamar "Projeto", e o item hoje rotulado
"Cotacao" passa a se chamar "Endereços". Levantamento previo mostrou que o
item "Cotacao" ja aponta para a rota `enderecos_lastmile` (tela de
enderecos) — o rotulo atual estava desalinhado do conteudo real da tela;
"Endereços" corrige esse desalinhamento.

Criterios de aceite:
- No submenu principal, o texto do cabecalho do grupo (linha 170 de
  `base.html`) muda de "LastMile" para "Projeto".
- O texto do item de submenu (linha 175) muda de "Cotacao" para "Endereços".
- Nenhuma rota, nome de grupo de permissao (`has_group:"LastMile"`), view,
  nome de arquivo/template ou nome de URL e alterado — somente o texto
  visivel no menu.
- Comportamento de navegacao, permissoes e destaque do item ativo
  (classes `sidebar-link-active`/`text-ageis-yellow`) continuam identicos.

Fora do escopo desta PO (decisao do usuario em 2026-08-10): renomear o grupo
de permissao "LastMile" no banco, rotas/views/templates/arquivos com
"lastmile"/"cotacao" no nome, chaves em `automacoes_registry`, e o conteudo
de `business_rules.md`/ADRs que usam esses termos como dominio de negocio.
Registrado aqui como pendencia futura, nao aberta como PO nesta decisao.

Regras relacionadas: nenhuma (mudanca de texto, sem regra de negocio nova).

Dependencias: nenhuma.

Tipo de feature: `frontend-layout` (validacao visual do usuario; nao gera
QA-XXX).

Agente recomendado para executar:
- `dev`

### PO-071 - Administracao: tela "Importacao e Exportacao" com card de exportacao de Setores e Escolas em CSV

Status: `🔍 Aguardando QA` (ampliado pelo Dev em 2026-08-12)

**Entrega do Dev:**
- Tela "Importação e Exportação" mantida; CSV gera uma linha por Escola com as colunas fixas (RN-048) mais uma coluna por Campo personalizado aplicável, descoberta a cada exportação (RN-049): 1 coluna para escopo "Escola", até 3 (RE/RI/MC) para "Sub-atividades"; Calculado deriva ao vivo, Status condicionante fica em branco quando não bate.
- Card ganhou um segundo botão — "Baixar Modelo (Só Colunas)" gera o mesmo CSV só com a linha de cabeçalho (sem nenhuma Escola); "Baixar com Todos os Dados" mantém o comportamento completo já existente (RN-050).
- Os dois downloads compartilham a mesma função de montagem de colunas; o modelo não consulta Escola/CampoValor, só o catálogo de Campos.
- Testes novos de RN-050 (permissão, cabeçalho sem linhas, Campo personalizado refletido no modelo) e os de RN-048/049 passando; suíte completa de `core_admin`, `core`, `escolas` e `leads` (402 testes, 1 falha pré-existente sem relação, já registrada na PO-026) sem novas regressões.
- **Pendência:** validação visual em navegador não executada nesta sessão (sem credencial de Administrador disponível).

Objetivo:
Usuario pediu, em 2026-08-12, uma tela nova dentro de Administracao chamada
"Importacao e Exportacao", com um card no mesmo padrao visual dos cards de
automacao ja existentes (Central de Automacoes). Apos testar a primeira
entrega (RN-047, todos os modulos de negocio em formato longo), usuario
pediu para restringir a exportacao a Setores e Escolas, com cada campo em
uma coluna — confirmado replicar as colunas ja existentes na tela de Setor
(RN-048). Em seguida, pediu para os Campos personalizados tambem entrarem,
aparecendo automaticamente ao criar um Campo novo (RN-049).

Criterios de aceite (RN-048, mantidos):
- nova tela "Importacao e Exportacao" em Administracao, acessivel pelo mesmo
  menu lateral das demais telas de Administracao (grupo Administrador), com
  grid de cards no mesmo padrao visual da Central de Automacoes;
- card gera e disponibiliza para download um unico CSV, uma linha por
  Escola, com as colunas INEP, Nome da Escola, Estado, Municipio, Endereco e
  Status da Escola;
- para Rede Externa, Rede Interna e Mapa Calor, tres colunas cada (Setor,
  Parceiro, Status), vazias quando a Escola nao tiver aquela subatividade;
- nao inclui os demais modulos de negocio (Clientes/Enderecos, Leads,
  Provedores/Parceiros, Cotacoes) — fora do escopo desta feature;
- acesso restrito ao grupo Administrador.

Criterios de aceite adicionais (RN-049):
- uma coluna por `Campo` cadastrado em Administracao > Campos, descoberta a
  cada exportacao (sem precisar de deploy quando um Campo novo for criado);
- nome da coluna com o prefixo "Campo Personalizado - " (mais sufixo RE/RI/MC
  quando aplicavel), para nunca colidir com as colunas fixas da RN-048;
- Campo com escopo Escola gera 1 coluna (valor da Escola); Campo com escopo
  Sub-atividades (ou sem `SetorEscopo` cadastrado) gera 1 coluna por
  subatividade aplicavel (RE/RI/MC), valor daquela instancia;
- Campo tipo Calculado usa o valor derivado ao vivo (mesma formula do modal,
  RN-039), nunca o valor bruto; Campo com Status condicionante fica em
  branco na linha quando o Status atual nao bate;
- valor formatado como no historico de Campos (RN-040): data `dd/mm/aaaa`,
  booleano Sim/Nao, demais tipos como texto;
- reaproveitar a logica ja implementada em `apps/leads/services.py`
  (`campos_grid_escola`, `campos_grid_rede`, `_valor_campo_calculado`,
  `_campo_visivel`, `_formatar_valor_campo_historico`) em lote (nao por
  Escola), para nao introduzir N+1.

Criterios de aceite adicionais (RN-050):
- botao "Baixar Modelo" no mesmo card, gerando um CSV so com a linha de
  cabecalho (colunas fixas + Campos personalizados atuais), sem nenhuma
  linha de Escola;
- botao "Baixar com Todos os Dados" mantem o comportamento ja existente
  (uma linha por Escola);
- nenhuma mudanca nas regras de coluna/valor da RN-048/RN-049.

Regras relacionadas: RN-050, RN-049, RN-048, RN-047 (substituida) (docs/business_rules.md).

Dependencias: nenhuma conhecida — tela nova, reaproveita o padrao visual ja
existente dos cards de automacao (`core_admin/partials/*.html`).

Tipo de feature: `fullstack` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-072 - Escola: campos estruturados de Logradouro, Numero, Bairro e CEP (extraidos do endereco em texto livre)

Status: `🔍 Aguardando QA` (implementado pelo Dev em 2026-08-12; migração aplicada no ambiente rodando)

**Entrega do Dev:**
- `Escola` ganhou os campos `logradouro`, `numero`, `bairro`, `cep`; `endereco_descricao` (texto bruto) não foi tocado.
- Função de extração de melhor esforço, testada com 8 formatos reais encontrados investigando produção (com/sem número, com/sem tipo de logradouro, sem bairro, sem CEP) — nunca inventa valor quando não há confiança, só deixa em branco.
- `sincronizar_escolas` (DashboardEACE) já preenche os 4 campos novos a cada sincronização; migração de dados fez o backfill único das Escolas já existentes.
- Exportação de Setores e Escolas (PO-071) troca a coluna única "Endereco" por Logradouro/Numero/Bairro/CEP, no CSV de dados e no modelo.
- Testes da extração (8 formatos reais), da sincronização e do export atualizados e passando; suíte completa de `core_admin`, `core`, `escolas`, `leads`, `clientes` e `partners` (506 testes, 1 falha pré-existente sem relação, já registrada na PO-026) sem novas regressões.
- Migração aplicada no `speed_sistema`/`speed_mysql` após confirmação do usuário (que reportou erro 500 causado pela migração pendente): 2622 Escolas com CEP e Logradouro extraídos, 1795 com Número e 2560 com Bairro — o restante ficou em branco por falta de confiança na extração (esperado, RN-051), sem perda do texto original. Erro 500 confirmado corrigido (endpoint volta a responder).
- **Pendência:** nenhuma.

Objetivo:
Usuario pediu, em 2026-08-12, para separar em colunas proprias as
informacoes hoje misturadas no texto livre de "Endereco" de cada Escola
(tanto no banco quanto na planilha exportada pela PO-071). Investigacao do
Orquestrador confirmou que o texto de origem (DashboardEACE) nao segue um
formato fixo; usuario confirmou seguir com extracao de melhor esforco, com
CEP sempre confiavel e Logradouro/Numero/Bairro em branco quando a
extracao nao tiver confianca — nunca apagando o texto original (RN-051).

Criterios de aceite (RN-051):
- `Escola` ganha os campos `logradouro`, `numero`, `bairro`, `cep`,
  preenchidos por uma extracao automatica do texto de `endereco_descricao`
  (mantido intacto);
- CEP extraido com certeza quando presente no texto (padrao fixo);
  Logradouro/Numero/Bairro por heuristica, em branco quando sem confianca;
- `sincronizar_escolas` (DashboardEACE) preenche os 4 campos novos em toda
  sincronizacao futura;
- backfill unico aplica a mesma extracao as Escolas ja existentes;
- exportacao de Setores e Escolas (PO-071) passa a ter as colunas
  Logradouro, Numero, Bairro e CEP no lugar da coluna unica "Endereco", no
  CSV de dados e no modelo.

Regras relacionadas: RN-051 (docs/business_rules.md).

Dependencias: PO-071 (tela e servico de exportacao de Setores e Escolas, ja
existentes — este PO altera as colunas exportadas).

Tipo de feature: `backend-only` (QA obrigatorio) — sem tela nova; a unica
parte visivel ao usuario e a planilha ja existente (PO-071), so com colunas
diferentes.

Agente recomendado para executar:
- `dev`

### PO-073 - Responsavel de subatividade (RE/RI/Mapa Calor), vinculado ao usuario do sistema

Status: `🔍 Aguardando QA` (implementado pelo Dev em 2026-08-12; conferido e documentado em 2026-08-13)

**Entrega do Dev:**
- Campo Responsável (usuário do sistema) adicionado às três subatividades — Rede Externa, Rede Interna e Mapa Calor.
- Responsável atribuível e reatribuível manualmente nas mesmas telas que já editam Setor e Status (grid global de Endereços Lastmile e Tela de Setor), sem tela nova.
- Ao enviar a subatividade para outro Setor, o Responsável é zerado junto com o Status, liberando reatribuição no Setor de destino.
- Setor, Status e Responsável continuam opcionais no banco; ao salvar com Setor e Status já preenchidos, o Responsável passa a ser exigido também.
- Toda atribuição, reatribuição ou zeragem de Responsável gera histórico De/Para, no mesmo padrão já usado para Setor, Status e Parceiro.
- Suíte de testes de `escolas` e `leads` executada (243 testes), sem falhas; nenhuma pendência identificada.

Objetivo:
Usuario pediu, em 2026-08-12, que toda subatividade (Rede Externa, Rede
Interna e Mapa Calor) tenha Setor, Status e Responsavel, com Responsavel
sendo o usuario do sistema (nao texto livre nem cadastro externo).
Investigacao do Orquestrador confirmou que Setor/Status ja existem mas sao
opcionais, e que Responsavel nao existe hoje — o unico precedente e
`Proposal.responsavel` (cotacao). Perguntado sobre semantica de atribuicao,
obrigatoriedade no banco, escopo, onde editar, comportamento ao trocar de
Setor e geracao de historico, usuario confirmou: atribuicao manual/
reatribuivel (mesmo padrao de Parceiro/`Proposal.responsavel`);
obrigatoriedade so via UI, sem migrar dados legados; vale para as tres
subatividades; edicao nas mesmas telas ja existentes; Responsavel zerado
junto com o Status ao trocar de Setor; gera historico De/Para.

Criterios de aceite (RN-052, ADR-027):
- `ProcessoRedeBase` ganha o campo `responsavel` (FK `core.User`,
  `null=True, blank=True`, `on_delete=SET_NULL`), herdado por
  `RedeExterna`, `RedeInterna` e `MapaCalor` — migration aditiva, sem
  backfill;
- Responsavel e atribuivel/reatribuivel manualmente nas mesmas telas que
  ja editam Setor/Status — grid global de Enderecos Lastmile (RN-026) e
  Tela de Setor (RN-027/028) — sem tela nova; mesma trava por `setor_atual`
  da RN-033;
- Setor, Status e Responsavel continuam opcionais no banco; a validacao de
  obrigatoriedade (os tres preenchidos) fica na camada de formulario/
  servico usada pela RN-026, sem migrar os registros ja existentes;
- ao trocar de Setor (RN-033 zera o Status para "Aguardando"), o
  Responsavel tambem e zerado (`responsavel=None`), liberando a
  subatividade para reatribuicao no novo Setor;
- alteracao de Responsavel (manual ou zeragem automatica) gera
  `RegistroHistorico` no formato De/Para ja usado para Setor/Status/
  Parceiro (RN-029/041);
- vale igualmente para RedeExterna, RedeInterna e MapaCalor, sem excecao.

Regras relacionadas: RN-052, RN-023, RN-025, RN-026, RN-027, RN-028, RN-029,
RN-030, RN-033, RN-035, RN-041, RN-043 (docs/business_rules.md).

Decisao arquitetural: docs/adr/ADR-027_RESPONSAVEL_DE_SUBATIVIDADE_ATRIBUIVEL_VINCULADO_AO_USUARIO_DO_SISTEMA.md

Dependencias: nenhuma bloqueante — reaproveita telas e models ja existentes
(PO-048/050/051/052/053, RN-026/027/028/033).

Pendencia registrada na ADR-027 (RN-056): usuario esclareceu que
Responsavel nunca deve ser obrigatorio ao mover/atribuir Setor a uma
subatividade quando quem faz isso nao esta necessariamente no Setor de
destino. Primeira analise (2026-08-13) concluiu, com o Dev, que nao havia
divergencia de codigo — mas restringiu erroneamente o escopo a "mover
entre Setores ja atribuidos", deixando de fora a primeira atribuicao pelo
grid global. Usuario reportou, no mesmo dia, continuar bloqueado
exatamente nesse caso: primeira atribuicao de Setor pela tela Enderecos
Lastmile (grid global, subatividade sem Setor ainda), com a mensagem
"Selecione um Responsável para salvar — Setor, Status e Responsável são
obrigatórios juntos."

**Divergencia confirmada em 2026-08-13 (RN-056 ampliada):** no ramo `elif
not setor_atual:` de `apps/leads/views.py::escola_rede_editar` (grid
global, RN-035), a checagem final de obrigatoriedade
(`not enviado_a_outro_setor and rede.setor_id and rede.status_id and not
rede.responsavel_id`) ainda exige Responsavel, porque `enviado_a_outro_setor`
so pode ser True quando `setor_atual` esta definido (Tela de Setor) — no
grid global ela e sempre False, entao a excecao nunca se aplica ali.
Correcao cabe ao Dev: a obrigatoriedade deve ficar restrita ao ramo `else`
(Tela de Setor, permanecendo no `setor_atual`); no grid global, Responsavel
nunca deve ser exigido. QA deve verificar esse cenario especifico (atribuir
Setor pela primeira vez no grid global, sem Responsavel) antes de aprovar.

Tipo de feature: `backend-only` (QA obrigatorio) — reaproveita campos de
formulario ja existentes no grid (RN-026); sem tela nova.

Agente recomendado para executar:
- `dev`

### PO-074 - Remover "Velocidade ofertada" da linha expandida de RE/RI/Mapa Calor

Status: `👤 Aguardando validação visual` (implementado pelo Dev em 2026-08-13)

**Entrega do Dev:**
- Removido o rotulo e o valor de "Velocidade ofertada" das duas variantes
  da linha expandida (edicao em cascata e leitura simples) em
  `escola_rede_row.html`, usada por RE, RI e Mapa Calor tanto na tela de
  Enderecos Lastmile quanto na Tela de Setor.
- Demais dados de referencia (Setor, Parceiro) continuam exibidos como
  estavam.
- Model (`Escola._referencia_rede`/`_formatar_velocidade`) e testes
  existentes mantidos intactos, conforme escopo fechado da RN-053; ajustado
  somente um teste que verificava a string "100 Mbps" no HTML renderizado
  (`apps/leads/tests.py`), que nao existe mais na tela.
- Validacao visual em navegador: nao executada (sem ferramenta de browser
  disponivel na sessao e sem credenciais de login). Verificado apenas via
  testes automatizados (Django test client): a string "Velocidade
  ofertada"/"100 Mbps" nao aparece mais na resposta e os demais campos
  (Setor, Parceiro) continuam presentes normalmente.
- **Pendencia:** aguardando validacao visual do usuario em navegador real,
  no celular e no desktop.

Objetivo:
Usuario pediu, em 2026-08-13, para tirar o campo "Velocidade ofertada" da
linha expandida das subatividades (RE/RI/Mapa Calor) na tela de Enderecos
Lastmile e na Tela de Setor. Investigacao do Orquestrador confirmou que o
campo (referencia somente-leitura vinda de `dados_api.velocidade_dl_ofertada`,
RN-024) nunca teve criterio proprio documentado e nao faz parte da
exportacao CSV de Setores e Escolas (PO-071/RN-048/049) — a remocao nao
afeta a planilha.

Criterios de aceite (RN-053):
- a linha expandida de RE, RI e Mapa Calor (grid global de Enderecos
  Lastmile e Tela de Setor, mesma partial `escola_rede_row.html`) deixa de
  exibir o rotulo e o valor de "Velocidade ofertada", nas duas variantes da
  linha (edicao em cascata e leitura simples);
- demais dados de referencia da API (Setor, Parceiro, RN-024) continuam
  exibidos como estao;
- nao altera a exportacao CSV de Setores e Escolas (PO-071) nem nenhuma
  outra tela — o campo so existia neste ponto;
- sem migration — o dado nunca foi coluna propria (vem de dentro do JSON
  `dados_api`).

Regras relacionadas: RN-053, RN-024 (docs/business_rules.md).

Dependencias: nenhuma.

Observacao (escopo fechado pelo usuario em 2026-08-13): esta PO cobre
somente a remocao da exibicao no template. O codigo interno do model
(`Escola._referencia_rede`, `_formatar_velocidade`, leitura de
`dados_api.velocidade_dl_ofertada`, `apps/escolas/models.py`) e os testes
existentes (`apps/escolas/tests.py`, `apps/leads/tests.py`) permanecem
intactos — sem alteracao nesta PO.

Tipo de feature: `frontend-layout` (validacao visual do usuario; nao gera
QA-XXX) — remocao exclusivamente de exibicao, sem mudanca de comportamento,
formulario, navegacao, permissao, model ou testes.

Agente recomendado para executar:
- `dev`

### PO-075 - Grupo dedicado "Setor" e permissao individual por Setor no menu Setores

Status: `🔍 Aguardando QA` (implementado pelo Dev em 2026-08-13; correcao de bug em 2026-08-13)

**Entrega do Dev:**
- Criado o grupo `Setor`, que agora controla o menu "Setores" e as telas de lista/detalhe — deixou de depender do grupo `LastMile`.
- Criada a concessao individual por nome de Setor: cada usuario do grupo `Setor` so ve e acessa os nomes liberados para ele, gerenciados pelo Django Admin (tela "Acessos a Setores").
- Acesso a um nome de Setor nao concedido responde 403, mesmo existindo no catalogo e o usuario estando no grupo `Setor`.
- Usuario sem nenhum Setor concedido nao ve mais a secao "Setores" no menu.
- Cadastro do grupo `Setor` em producao automatizado (mesma rotina que ja cria os demais grupos padrao).
- **Correcao:** o ambiente relatou erro 500 em paginas do sistema em geral (nao so no modulo Setores) apos esta entrega. Causa raiz: faltava aplicar a migracao da tabela de "Acessos a Setores"; sem ela, qualquer usuario comum autenticado (nao superusuario) via erro 500 em qualquer pagina, porque a lista de Setores do menu e calculada em toda pagina. Migracao aplicada, teste de regressao adicionado e suite executada e passando.

**Pendencia relatada pelo usuario (2026-08-13), antes da aprovacao do QA:**
usuario tentou conceder acesso individual (RN-055) apenas a "Implantacao",
e tambem a "Implantacao e Compras", e nao conseguiu. Duas causas possiveis,
a confirmar pelo Dev/QA na revisao — nenhuma delas exige mudanca de decisao
(ADR-028/RN-054/RN-055 continuam validas):
- a concessao em `AcessoSetor` exige o nome **exatamente** igual ao
  cadastrado no catalogo de Setor (RN-025); "Compras" pode nao existir
  como nome cadastrado (o catalogo de exemplo usado nesta sessao tem
  "Suprimentos", nao "Compras") — se o nome nao bater, a concessao fica
  sem efeito e o Setor nao aparece para o usuario, sem erro visivel;
- a concessao por Setor e sempre uma linha por nome no Django Admin (tela
  "Acessos a Setores"); para liberar dois nomes de uma vez ("Implantacao"
  e "Compras"/"Suprimentos") sao necessarios dois registros, um por nome
  — nao ha selecao multipla em um unico registro. Isso e o risco que a
  propria ADR-028 ja registrava (concessao manual, sem tela amigavel,
  sujeita a erro).
Alem disso, o usuario concedente precisa pertencer ao grupo Django
`Setor` (RN-054) alem de ter os registros de concessao (RN-055) — sem o
grupo, o menu "Setores" nao aparece mesmo com Setores concedidos.
Verificacao de causa raiz e correcao, se necessaria, sao escopo do
QA/Dev — o Orquestrador nao testa nem altera codigo.

Origem: usuario, 2026-08-13 — quer que o modulo "Setores" (PO-052/PO-053)
passe a ter controle de acesso proprio, em vez de depender do grupo
`LastMile`, e que dentro do modulo cada usuario so veja/acesse os Setores
liberados para ele. Resolve a pendencia ja registrada na ADR-016
("restringir cada tela de Setor a um grupo/time especifico de usuarios").

Criterios de aceite (RN-054, RN-055, ADR-028):
- criado o grupo `Setor` (mesmo padrao dos grupos existentes: `LastMile`,
  `Parceiro`, `Backoffice`, `Administrador`); superusuario continua com
  acesso irrestrito;
- item de menu "Setores" (`core/base.html`) e as views `setores_list`/
  `setor_detail` (`apps.leads`) passam a exigir o grupo `Setor` em vez do
  grupo `LastMile`;
- dentro do modulo, cada usuario do grupo `Setor` so ve/acessa os nomes de
  Setor explicitamente concedidos a ele — nao automaticamente todos os
  cadastrados no catalogo (RN-025);
- `GET /prospeccao/setores/<nome>/` para um nome nao concedido retorna 403,
  mesmo que o nome exista e o usuario esteja no grupo `Setor`;
- usuario sem nenhum Setor concedido nao ve a secao "Setores" no menu
  (mesmo comportamento hoje ja aplicado quando a lista esta vazia);
- existe uma forma de um gestor conceder/revogar Setores por usuario
  (Django Admin padrao ou tela propria — decisao tecnica do Dev);
- cadastro do grupo `Setor` em producao documentado (mesmo padrao ja usado
  para os grupos existentes).

Regras relacionadas: RN-054, RN-055 (novas); RN-025, RN-027
(docs/business_rules.md).

Decisao arquitetural:
docs/adr/ADR-028_PERMISSAO_GRANULAR_POR_SETOR_INDIVIDUAL.md

Tipo de feature: `backend-only` (QA obrigatorio).

Agente recomendado para executar:
- `dev`.

### PO-076 - Escola: Velocidade Minima e Kit Inicial tipados + catalogo de referencia para TARGET EACE, exibidos em Campos (Atividade Principal)

Status: `Implementada pelo Dev, aguardando QA` — as 3 partes entregues em
2026-08-13: `Escola.velocidade_dl_minima`/`Escola.kit_inicial` (colunas
tipadas, com backfill de migracao e preenchimento continuo pela
sincronizacao); catalogo `TargetRedeExterna` (ADR-029, sem FK com Escola,
com management command `importar_target_rede_externa` para a carga real —
ainda vazio, pois nenhum dado real foi copiado do backup nesta sessao);
`Escola.target_eace` como lookup somente-leitura. Os tres dados aparecem no
modal "Campos" da Escola (RN-057). Pendencia secundaria registrada como
observacao, nao como bloqueio — ver abaixo.

Origem: usuario perguntou, em 2026-08-13, se ja existia no banco uma tabela
com os dados tecnicos EACE (Velocidade Minima, Kit Inicial, TARGET EACE) por
escola, pedindo para exibi-los dentro da opcao "Campos" vinculada a
Atividade Principal (Escola); confirmou o cenario A (vem do DashboardEACE).
No mesmo dia, colocou na raiz do projeto um backup real do banco de origem
(`eace_jira_backup_20260813.sql.gz`, banco MySQL `eace_jira`) e pediu para
estruturar o SGP em cima dele. O Orquestrador inspecionou **somente a
estrutura** do backup (`CREATE TABLE`, nomes/tipos de coluna — nenhuma
linha de dado real foi copiada para a documentacao). Questionado sobre como
tratar TARGET EACE (que nao e coluna por escola), o usuario confirmou:
"essa tabela: 'target_rede_externa' informa o valor da rede externa que o
cliente EACE disponibilizada para nós, esse é o TARGET EACE. preciso dessa
tabela toda no nosso sistema, vamos usar para pegar os valores das
velocidades por estado e colocar na escola" — decisao registrada na
ADR-029.

**Achados da inspecao do backup (schema, sem dados) e decisao por parte:**
- banco `eace_jira`, 19 tabelas (mirror do Jira do DashboardEACE + tabelas
  de metrica/sprint + 2 tabelas financeiras: `target_rede_externa` e
  `valor_kit`); nao ha tabelas `custo_rede_externa`/`custo_rede_interna`
  citadas em `API_EXTERNA.md` — nao existem neste backup;
- **Parte 1 — Velocidade Minima** (confianca alta): `issues
  .velocidade_dl_minima` (`decimal(10,2)`, sem sufixo de unidade). Existe
  tambem `escolas.velocidade_dl_minima_mbps` (`int`), mas a tabela `escolas`
  esta **vazia** neste backup (0 linhas) enquanto `issues` tem dados — e o
  nome "sem sufixo" bate com `velocidade_dl_ofertada`, chave ja confirmada
  em produção (RN-024/PO-046). Promover para coluna tipada em `Escola`
  (dentro de `dados_api` hoje, decisao incremental ja prevista na ADR-010);
- **Parte 2 — Kit Inicial** (confianca media, observacao aberta):
  candidato `issues.kit_wifi` (`decimal(10,2)`), ao lado de
  `ap_adicional`/`nobreak` (mesmo grupo de equipamento). Nao existe coluna
  literalmente chamada "kit_inicial" — **recomendado confirmar o apelido
  com o time EACE antes ou durante a implementacao; nao bloqueia o Dev
  comecar**, so exige atencao ao nomear/documentar o mapeamento final;
- **Parte 3 — TARGET EACE** (decidida em 2026-08-13, ADR-029): nao e
  coluna por escola. Replicar a tabela `target_rede_externa` (`uf` +
  `velocidade_mbps` -> `valor`, ~78 linhas na origem) por completo, como
  catalogo proprio do SGP (nome de trabalho `TargetRedeExterna`, nome
  definitivo a criterio do Dev). O TARGET EACE de uma Escola e sempre um
  lookup (UF da Escola + velocidade da Escola contra esse catalogo), nunca
  um valor gravado na linha da Escola; sem correspondencia exata, fica
  vazio.

Criterios de aceite (RN-057, ADR-029):
- Parte 1: `Escola` ganha a coluna tipada de Velocidade Minima, promovida
  de dentro de `dados_api`; `sincronizar_escolas_dashboard_eace` passa a
  preenche-la em toda sincronizacao futura; migracao de dados faz o
  backfill unico das Escolas ja existentes quando a sincronizacao real
  rodar (mesmo padrao da PO-072);
- Parte 2: mesmo tratamento da Parte 1 para Kit Inicial, apos confirmar o
  apelido com o time EACE (observacao, nao bloqueio);
- Parte 3: criar o catalogo de referencia (UF + velocidade -> valor),
  importado por completo a partir da origem (mecanismo de importacao a
  criterio do Dev — nao ha API para isso); criar a propriedade/consulta que
  deriva o TARGET EACE de uma Escola (UF + velocidade minima da Escola),
  sem gravar o valor na linha da Escola; tratar o mismatch de tipo
  `int`/`decimal` na chave de velocidade com cuidado (nao falhar
  silenciosamente);
- os tres valores aparecem, sempre somente leitura, dentro da area de
  Campos vinculada a Atividade Principal (Escola, RN-037/038) — nao
  editaveis pelo SGP;
- cada Escola mostra seu proprio valor de Velocidade Minima/Kit Inicial
  (nao e dado fixo — RN-038 nao se aplica); TARGET EACE varia por
  Escola apenas porque varia por UF/velocidade da Escola, nao porque e
  armazenado individualmente.

Regras relacionadas: RN-057 (docs/business_rules.md), RN-024, RN-031,
RN-037, RN-038.

Decisao arquitetural:
- docs/adr/ADR-010_MODELO_ESCOLA_DEDICADO_DASHBOARD_EACE.md (pendencia
  "promover campos de `dados_api`" ja prevista ali, cobre as Partes 1/2);
- docs/adr/ADR-029_TABELA_DE_REFERENCIA_TARGET_REDE_EXTERNA_PARA_TARGET_EACE_POR_ESCOLA.md
  (cobre a Parte 3 — catalogo de referencia, sem FK direta com Escola).

Dependencias: nenhuma dependencia de outra PO do backlog.

Seguranca: o schema foi confirmado a partir de
`eace_jira_backup_20260813.sql.gz` (backup real de outro sistema, colocado
na raiz do projeto pelo usuario) — **nenhuma linha de dado (INSERT) foi
lida ou copiada**, somente `CREATE TABLE`/nomes e tipos de coluna. O
arquivo foi adicionado ao `.gitignore` (`*.sql.gz`) pelo Orquestrador nesta
sessao — nao deve ser commitado; o usuario decide se/quando removê-lo do
disco.

Tipo de feature: `fullstack` (QA obrigatorio) — toca model/migracao/servico
de sincronizacao (backend), a importacao do catalogo de referencia e a
exibicao dentro da area de Campos (frontend), mesmo padrao classificado na
PO-049 para dado de referencia da API exibido em tela.

Agente recomendado para executar:
- `dev` (as 3 partes ja tem caminho decidido; Parte 2 carrega uma
  observacao a confirmar com o time EACE, sem bloquear o inicio).

### PO-077 - Tela "Acesso": conceder modulo do menu e Setor individual em um lugar so

Status: `⬜ Pendente` — definicao fechada (usuario decidiu 4 pontos; Orquestrador decidiu 2 pontos reversiveis de baixo risco, Lei 9 CLAUDE.md); ADR e RN escritas; pronta para o Dev iniciar.

Origem: usuario pediu, em 2026-08-13, na sequencia da investigacao do menu
"Setores" (PO-075): "EU queria dentro do administrador uma opcao chamada
acesso e poder dar acesso a cada modulo do menu e a cada setor do menu
setores." Verbatim.

**O que ja existe hoje (verificado no codigo, nao suposto):**
- cada modulo do menu principal depende de um grupo Django nativo, checado
  por `has_group`/`user_passes_test` — sem tela propria: `LastMile`
  ("Projeto"), `Setor` ("Setores"), `Parceiro`, `Backoffice`, `Gestao`,
  `Administrador` (`apps/core/templates/core/base.html`,
  `apps/core/templatetags/auth_extras.py`);
- conceder/revogar esses grupos por usuario hoje se faz pela tela nativa do
  Django Admin (`/admin/`), no formulario padrao de usuario (campo
  "Groups", multi-selecao) — nao existe tela propria no app para isso;
- dentro do modulo "Setores", a concessao individual por nome (RN-055) ja
  existe como model `AcessoSetor` (`apps.leads`), administrada pelo Django
  Admin nativo (tela "Acessos a Setores", uma linha por usuario+nome) —
  sem selecao multipla, ver pendencia registrada na PO-075 acima;
- `apps.core_admin` e a area propria de "Administracao" do sistema (menu
  lateral, nao Django Admin), com paginas dedicadas hoje para Processos,
  Campos e Setor-Escopo (`apps/core_admin/urls.py`,
  `apps/core_admin/views.py`) — e o lugar escolhido para a tela nova.

**Avaliacao de impacto arquitetural:** nao exige modelo novo nem paradigma
novo de permissao. Os dois mecanismos que a tela precisa orquestrar ja
existem (grupo Django nativo para modulo; `AcessoSetor` para Setor
individual, RN-054/055/ADR-028) — o que falta e uma view/formulario
customizado que escreva nos dois de uma vez, por usuario, numa unica tela,
no lugar de exigir Django Admin em duas telas separadas. Extensao do
padrao ja criado pela ADR-028, nao uma decisao arquitetural nova.

**Definicoes fechadas em 2026-08-13 (ADR-030, RN-058, RN-059):**
1. Local/tecnologia: area propria "Administracao" (`apps.core_admin`), nao
   Django Admin nativo — decisao do usuario.
2. Modulos na tela: os 6 grupos hoje existentes (LastMile/Projeto,
   Setor/Setores, Parceiro, Backoffice, Gestao, Administrador), inclusive
   `Administrador` — decisao do Orquestrador (Lei 9, reversivel/baixo
   risco), com aviso obrigatorio de confirmacao ao revogar `Administrador`
   de qualquer usuario (risco de autoexclusao sinalizado, nao bloqueado).
3. Quem acessa a tela "Acesso": grupo de menu `Administrador`
   (`has_group`/`user_passes_test`, mesmo padrao das demais paginas de
   `apps.core_admin`) — nao restrito a superusuario Django — decisao do
   usuario.
4. Auto-inclusao no grupo `Setor`: conceder qualquer Setor individual a um
   usuario fora do grupo `Setor` o inclui nesse grupo automaticamente,
   sem passo manual separado — decisao do usuario (RN-059). Revogar um
   Setor individual **nao** remove automaticamente o usuario do grupo
   `Setor` (assimetria deliberada, ver ADR-030).
5. Conceder e revogar no mesmo lugar: tela permite as duas acoes, tanto
   para modulo (grupo) quanto para Setor individual — decisao do usuario.
6. Estado atual visivel: ao selecionar um usuario, a tela mostra os
   modulos que ele ja tem e os Setores ja concedidos antes de qualquer
   alteracao — decisao do Orquestrador (Lei 9, reversivel/baixo risco;
   padrao esperado numa tela de gestao de acesso).

Criterios de aceite (RN-058, RN-059, ADR-030):
- nova tela "Acesso" em `apps.core_admin`, acessivel apenas ao grupo
  `Administrador` (ou superusuario), seguindo o padrao visual/de rota das
  paginas Processos/Campos/Setor-Escopo ja existentes;
- para um usuario selecionado, formulario unico concede/revoga
  pertencimento aos 6 grupos/modulos (`LastMile`, `Setor`, `Parceiro`,
  `Backoffice`, `Gestao`, `Administrador`) e concede/revoga Setores
  individuais (`AcessoSetor`) dentre os nomes cadastrados no catalogo
  (RN-025);
- revogar `Administrador` de qualquer usuario (inclusive do proprio
  usuario logado) exige confirmacao explicita com aviso de risco de
  autoexclusao antes de efetivar;
- conceder um Setor individual a usuario fora do grupo `Setor` inclui
  esse usuario no grupo automaticamente, na mesma acao (idempotente se
  ja pertencer); revogar Setor individual nao remove o usuario do grupo;
- antes de qualquer alteracao, a tela exibe o estado atual do usuario
  selecionado (modulos e Setores ja concedidos);
- nenhum model novo criado — reaproveita `django.contrib.auth.models.Group`
  e `apps.leads.models.AcessoSetor`.

Regras relacionadas: RN-058, RN-059 (novas); RN-025, RN-054, RN-055
(docs/business_rules.md).

Decisao arquitetural:
docs/adr/ADR-030_TELA_ACESSO_CONCESSAO_DE_MODULO_E_SETOR_INDIVIDUAL.md

Dependencias: nenhuma dependencia bloqueante de outra PO do backlog;
reaproveita o que a PO-075 (ADR-028/RN-054/055) ja entregou — recomendado
so entrar em desenvolvimento depois que a PO-075 passar pelo QA, para nao
construir a tela em cima de um comportamento de base ainda nao validado.

Pendencias tecnicas (baixo risco, a criterio do Dev na implementacao):
- lista de usuarios elegiveis/buscaveis na tela (todos os usuarios com
  busca, mesmo padrao do `autocomplete_fields` ja usado em
  `AcessoSetorAdmin`);
- UX exata do aviso de autoexclusao ao revogar `Administrador` (modal de
  confirmacao, texto).

Tipo de feature: `fullstack` (tela + formulario + escrita em grupo/
`AcessoSetor` — QA obrigatorio).

Agente recomendado para executar:
- `dev`.

## Ordem de prioridade sugerida

Decisao do usuario em 2026-07-29: iniciar diretamente pelo Epic 13 (nova
arquitetura), a partir da PO-031. PO-027 (seguranca) e o QA pendente de
PO-021/PO-026 continuam validos e abertos no backlog, tratados em paralelo —
nao bloqueiam o inicio da reestruturacao.

Ordem original proposta pelo Orquestrador, mantida abaixo como referencia:

| # | PO | Motivo da posicao |
|---|---|---|
| 1 | PO-027 | Seguranca: trocar a senha no AD nao invalida a antiga no sistema (CLAUDE.md secao 15 poe seguranca acima de qualquer outra prioridade, inclusive da reestruturacao abaixo) |
| 2 | PO-021 | Ja implementada, so aguarda QA — destravar antes de abrir frente nova |
| 3 | PO-026 | Ja implementada, so aguarda QA — destravar antes de iniciar o Hub de Integracao (PO-033) |
| 4 | PO-031 | Epic 13 — namespace unico `apps.*`: fundacao de toda a reestruturacao |
| 5 | PO-029 | Epic 13 — mover `clientes/` para `apps/clientes/` |
| 6 | PO-032 | Epic 13 — quebrar os 5 ciclos de importacao entre apps |
| 7 | PO-033 | Epic 13 — Hub de Integracao (`apps/integracoes/`) |
| 8 | PO-034 | Epic 13 — rotinas agendadas viram management command |
| 9 | PO-011 | Epic 13 — camada de servicos nos demais apps |
| 10 | PO-030 | Epic 13 — limpar a raiz do repositorio (independente, baixo risco) |
| 11 | PO-035 | Epic 13 — gate de regressao end-to-end antes do Modulo 2 |
| 12 | PO-014 | Risco funcional ainda nao validado (fechamento incompleto de O.S.); investigar antes que vire incidente |
| 13 | PO-018 | Auditoria de `cadastro_cliente_ixc` incompleta — afeta rastreabilidade do que ja roda em producao |
| 14 | PO-019 | Lacuna de logging de erro nas views de automacao |
| 15 | PO-010 | Autenticacao da API: necessaria antes de qualquer publicacao externa produtiva |

Seguranca (1-3) na frente por regra fixa do `CLAUDE.md`, nao por escolha desta
sessao. O Epic 13 (4-11) vem em seguida, a frente dos itens que nao tem risco
de seguranca nem trabalho ja pronto aguardando QA, conforme a prioridade que
voce definiu de deixar a arquitetura pronta antes do Modulo 2.
