# Backlog

## Visao geral

Este backlog cobre a iniciativa de organizacao documental e preparacao da API publica v1.

Status utilizados neste documento:

- `Planejada`
- `Pronta para sprint`
- `Em execucao`
- `Bloqueada`
- `Concluida`

## Epic 1 - Fundacao documental do produto

### PO-001 - Criar base documental do projeto

Status: `Concluida`

Objetivo:
Criar a estrutura inicial de documentacao para servir como ponto de entrada do projeto.

Entregas:
- indice geral;
- brief do produto;
- status atual;
- backlog;
- roadmap;
- sprint inicial.

### PO-002 - Catalogar modulos existentes

Status: `Concluida`

Objetivo:
Registrar os modulos atuais e suas responsabilidades funcionais iniciais.

Entregas:
- README por modulo atual;
- identificacao do modulo planejado para API/integracoes.

### PO-003 - Completar regras, fluxos e contratos por modulo

Status: `Planejada`

Objetivo:
Detalhar regras de negocio, fluxos e contratos dos modulos com profundidade suficiente para manutencao e suporte.

Criterios de aceite:
- cada modulo ter regras rastreaveis;
- contratos principais documentados;
- fluxos criticos descritos em portugues do Brasil.

Proximo agente recomendado:
- `docs_writer`
- apoio de `product_owner_requirements`

## Epic 2 - Fronteira de API publica

### PO-004 - Definir escopo da API publica v1

Status: `Pronta para sprint`

Objetivo:
Definir quais recursos entram na primeira versao da API.

Escopo inicial proposto:
- clientes;
- enderecos;
- parceiros;
- propostas;
- healthcheck.

Criterios de aceite:
- recursos v1 priorizados;
- operacoes iniciais definidas;
- exclusoes explicitas fora do escopo v1.

### PO-005 - Definir padrao de versionamento e publicacao

Status: `Pronta para sprint`

Objetivo:
Garantir que a API nasca com fronteira estavel.

Diretrizes de produto:
- prefixo `/api/v1/`;
- Swagger acessivel em ambiente interno/homologacao;
- rotas internas HTML nao entram no contrato publico.

### PO-006 - Criar modulo dedicado para API/integracoes

Status: `Concluida`

Objetivo:
Centralizar a exposicao externa da aplicacao em uma camada separada dos modulos web internos.

Criterios de aceite:
- modulo novo criado;
- namespace de URL proprio;
- responsabilidade documentada.

Agente executor:
- `backend_django`

Observacao:
- implementado na Sprint 001 com app dedicado `integracoes_api` e namespace `/api/v1/`.

## Epic 3 - Swagger e contratos externos

### PO-007 - Habilitar OpenAPI/Swagger

Status: `Concluida`

Objetivo:
Disponibilizar documentacao navegavel das rotas publicas da API.

Criterios de aceite:
- schema OpenAPI gerado;
- interface Swagger acessivel;
- apenas endpoints publicos versionados documentados.

Dependencia:
- PO-006

Agente executor:
- `backend_django`

Observacao:
- schema OpenAPI e tela Swagger publicados para a camada publica da API.

### PO-008 - Publicar endpoints de leitura de clientes e enderecos

Status: `Concluida`

Objetivo:
Entregar primeiro conjunto de integracao util para consulta externa.

Escopo minimo:
- listar clientes;
- detalhar cliente;
- listar enderecos de um cliente.

Observacao:
- implementado em `/api/v1/clientes/`, `/api/v1/clientes/<id>/` e `/api/v1/clientes/<cliente_pk>/enderecos/`.

### PO-009 - Publicar endpoints de leitura de parceiros e propostas

Status: `Concluida`

Objetivo:
Entregar visibilidade externa controlada do funil operacional.

Escopo minimo:
- listar parceiros;
- listar propostas;
- detalhar proposta.

Observacao:
- implementado em `/api/v1/parceiros/`, `/api/v1/propostas/` e `/api/v1/propostas/<id>/`.

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

## Epic 4 - Organizacao interna para suporte

### PO-011 - Separar logica reutilizavel de views extensas

Status: `Planejada`

Objetivo:
Reduzir acoplamento entre tela web, resposta JSON e integracoes.

Observacao:
Esta tarefa deve ser fatiada pelo `software_architect` e executada pelo `backend_django`.

### PO-012 - Consolidar mapa de integracoes existentes

Status: `Planejada`

Objetivo:
Documentar entradas, saidas, dependencia de scripts e efeitos colaterais das integracoes atuais.

Agentes recomendados:
- `product_owner_requirements`
- `docs_writer`

## Epic 5 - Automacoes de Backoffice IXC

### PO-013 - Resolver O.S. de atendimentos em lote sem finalizar o atendimento (IXC)

Status: `✅ Concluida` — lote, anexo condicional, ZIP e fechamento em loop até esgotar (RN-010/ADR-004) implementados pelo Dev em 2026-07-09; testes corrigidos pelo Dev e criterios de aceite atualizados pelo Orquestrador em 2026-07-21.

**Entrega do Dev (correcao da reprovacao):**
- Corrigidos os 6 testes de `ResolucaoOsAtendimentoIXCTests` que quebravam com `TypeError` (`arquivo=Mock()` nao existe mais na assinatura; a funcao usa `zip_arquivos` posicional). Testes ajustados para chamar com `zip_arquivos=` e para incluir os campos `Tem_Anexo`/`Fechar_Todas_OS`/`Confirmar_Resolucao` e o formato de atendimento (`su_status`) que a implementacao atual já exige.
- Suite `apps.backoffice.tests.ResolucaoOsAtendimentoIXCTests` executada no container `speed_sistema` (banco MySQL real): 7/7 testes passando, cobrindo RN-004, RN-005, RN-006, RN-008 e RN-010.
- Suite completa `apps.backoffice.tests` executada no mesmo container: sem regressao nova; continuam as 3 falhas pre-existentes e sem relacao em `CadastroClienteIXCTests` (`resolver_cidade_ixc` — feature de cadastro de cliente IXC em andamento, fora do escopo deste item).
- **Pendencia:** nenhuma. O Orquestrador registrou RN-012 (fechamento parcial via `Fechar_Todas_OS`), RN-013 (`Confirmar_Resolucao`) e RN-014 (gate `su_status = EP`) em `docs/business_rules.md`, com decisao do usuario em 2026-07-21 de manter os tres comportamentos como estavam implementados.

**Validacao do QA (re-revisao):**
- **Rota/funcao:** `executar_resolucao_os_atendimento_ixc` (`scripts/integracoes/backoffice/resolver_os_atendimento_ixc.py`).
- **Testes executados:** `apps.backoffice.tests.ResolucaoOsAtendimentoIXCTests` (7/7) e suite completa `apps.backoffice.tests` (24/27) no container `speed_sistema`, banco MySQL real.
- **Regras verificadas:** RN-001, RN-004, RN-005, RN-006, RN-007, RN-008, RN-009, RN-010, RN-012, RN-013, RN-014 — codigo confere com os criterios de aceite atualizados de PO-013.
- **Problema (do apontamento anterior):** corrigido — os 6 testes que falhavam com `TypeError` agora passam e exercitam de fato os cenarios de RN-004/005/006/008/010.
- **Observacao (nao bloqueante):** as 3 falhas em `CadastroClienteIXCTests` sao pre-existentes e de outra feature (cadastro de cliente IXC), ja registradas anteriormente; nao pertencem ao escopo de PO-013.
- **Resultado:** aprovado.

Objetivo:
Fechar todas as O.S. abertas de varios atendimentos no IXC, um lote por
execucao via planilha, mantendo cada atendimento ativo. O anexo de documento
e condicional por atendimento (coluna `Tem_Anexo`); quando houver anexo, o
documento e localizado por nome dentro de um ZIP importado junto com a
planilha.

Criterios de aceite:
- a planilha aceita varios `Atendimento_ID` por execucao, com colunas
  `Atendimento_ID`, `Confirmar_Resolucao` (obrigatorio, RN-013), `Tem_Anexo`
  (Sim/Nao), `Fechar_Todas_OS` (Sim/Nao, obrigatorio, RN-012), `Nome_Anexo`
  (obrigatorio quando `Tem_Anexo = Sim`) e `Mensagem` (opcional);
- a linha so e processada se `Confirmar_Resolucao = SIM` (RN-013);
- a linha e rejeitada, sem tocar o IXC, se o atendimento nao estiver com
  `su_status = EP` (Em Progresso) (RN-014);
- quando `Tem_Anexo = Sim`, o documento e localizado por nome dentro do ZIP
  importado e anexado ao atendimento antes de qualquer O.S. ser fechada; se
  o anexo falhar ou o nome nao existir no ZIP, nenhuma O.S. daquele
  atendimento e fechada;
- quando `Tem_Anexo = Nao`, a linha fecha as O.S. do atendimento sem
  tentativa de anexo;
- cada atendimento processado permanece ativo (`status != F`) no IXC ao
  final da execucao;
- O.S. de cada atendimento sao fechadas em ordem crescente de ID;
- falha parcial no fechamento das O.S. de um atendimento nao desfaz o que ja
  foi concluido naquele atendimento e nao interrompe o processamento das
  demais linhas do lote;
- documentos PDF do ZIP nao sao persistidos no sistema; apenas planilha de
  entrada e planilha/log de saida sao mantidos, no padrao ja usado pelas
  demais automacoes do backoffice;
- quando `Fechar_Todas_OS = SIM`, o fechamento de O.S. do atendimento repete
  busca+fechamento até esgotar as O.S. abertas (nao apenas uma listagem
  fixa), respeitando um limite maximo de rodadas de seguranca; se o limite
  for atingido com O.S. ainda aberta, o atendimento e reportado como falha
  (RN-010); quando `Fechar_Todas_OS = NAO`, fecha somente a O.S. mais antiga
  em aberto, sem repetir a busca (RN-012).

Regras relacionadas: RN-001, RN-004, RN-005, RN-006, RN-007, RN-008, RN-009,
RN-010, RN-012, RN-013, RN-014 (docs/business_rules.md). RN-002 e RN-003
foram substituidas (ver historico em business_rules.md).

Decisao arquitetural: docs/adr/ADR-003_RESOLUCAO_OS_ATENDIMENTO_EM_LOTE_COM_ANEXO_CONDICIONAL.md
(substitui a execucao unitaria de ADR-002) e
docs/adr/ADR-004_FECHAMENTO_OS_EM_LOOP_ATE_ESGOTAR.md (corrige o fechamento
de O.S. para repetir até esgotar).

Tipo de feature: `fullstack` (QA obrigatorio) — novo formulario de upload de
planilha + ZIP, nova logica de leitura do ZIP em memoria e reescrita da
orquestracao unitaria hoje existente.

Dependencias:
- reaproveita `finalizar_os_existente` (ixc_finalizacao_service.py);
- reaproveita `anexar_arquivo_ticket_ixc` (ixc_ticket_arquivo_service.py);
- reaproveita busca/ordenacao de O.S. do atendimento hoje em `desativar_atendimento_ixc.py`;
- reaproveita o padrao de leitura/validacao de planilha e geracao de log de
  execucao ja usado nas demais automacoes do `core_admin`.

Impacto em codigo existente:
- `scripts/integracoes/backoffice/resolver_os_atendimento_ixc.py`,
  `apps/core_admin/views.py` e `apps/core_admin/templates/core_admin/automacoes.html`
  ja foram reescritos para o lote via planilha, anexo condicional, ZIP e
  fechamento de O.S. em loop até esgotar (RN-010/ADR-004), pelo Dev em
  2026-07-09.

Risco identificado (nao bloqueia esta feature, mas deve ser tratado pelo Dev):
- token de acesso ao IXC com valor padrao gravado no codigo (viola CLAUDE.md
  secao 6 - Seguranca). Escopo real e tratamento: ver PO-016.

Agente recomendado para executar:
- `dev` (fullstack/backend_django)

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

## Epic 6 - Configuracao de Menu de Automacoes

### PO-015 - Permitir configurar em qual menu uma automacao aparece

Status: `✅ Concluida`

**Entrega do Dev:**
- Implementacao ja existia no codigo (model `AutomacaoMenu`, migrations 0004-0006, registry, admin com `list_editable`, grid dinamica); verificada nesta sessao e confirmada aderente aos criterios de aceite.
- Adicionados 6 testes novos (`AutomacaoMenuTests` em `apps/core_admin/tests.py`): valor padrao Administrador, preservacao das automacoes existentes apos a migracao, filtro por menu ativo, realocacao refletindo sem deploy, e permissao por grupo (autorizado, nao autorizado, superuser, slug inexistente).
- **Correcao do apontamento do QA:** as 4 views de download de modelo de planilha (`download_template_desativacao_atendimento`, `download_template_edicao_login_ixc`, `download_template_edicao_atendimento_ixc`, `download_template_resolucao_os_atendimento`, em `apps/core_admin/views.py`) passaram a usar `permissao_automacao(slug)` da propria automacao, em vez do grupo `Administrador` fixo.
- Reproduzi o cenario do QA apos a correcao: automacao realocada para Backoffice agora libera as 4 rotas de download para o grupo Backoffice, e continua negando para um grupo nao relacionado (Parceiro).
- Suite `core_admin` + `backoffice` executada contra banco MySQL local: os 6 testes novos continuam passando; mesmas 12 falhas pre-existentes de antes (nao relacionadas), nenhuma nova.
- **Pendencia:** nenhuma para este item.

**Observacao fora do escopo (nao corrigida aqui):** a suite completa tem falhas pre-existentes sem relacao com PO-015 — 4 em `backoffice.tests.ResolucaoOsAtendimentoIXCTests` (`executar_resolucao_os_atendimento_ixc() got an unexpected keyword argument 'arquivo'`) e 3 em `core_admin.tests.CoreAdminViewsTests` ligadas a cadastro de clientes IXC (nome de arquivo mudou de `Relatorio_...` para `Validacao_...`, uma rota retornando 302 em vez de 200, e um mock quebrado por falta do metodo `_buscar_ultimo_cadastro_cliente_ixc` em `apps/core_admin/views.py`). Parecem de uma feature de cadastro de clientes IXC em andamento, refletida nos arquivos ja modificados antes desta sessao. Recomendo abrir isso como pendencia separada com o Orquestrador.

**Validacao do QA:**
- **Re-revisao apos correcao.** Conferido o diff: as 4 views de download passaram de `grupo_Administrador_required` para `permissao_automacao(slug)`.
- Reproduzi de forma independente (menu diferente do usado pelo Dev, LastMile em vez de Backoffice): realoquei `editar_logins_ixc` e `editar_atendimentos_ixc` para LastMile — usuario do grupo LastMile passou a baixar o modelo das duas; `desativar_atendimentos_ixc` e `resolver_os_atendimento_ixc`, mantidas em Administrador, continuaram bloqueadas para esse mesmo usuario.
- Executados os 6 testes de `AutomacaoMenuTests` e a suite `CoreAdminViewsTests`: sem regressao nova causada pela correcao; as falhas pre-existentes (cadastro de clientes IXC) continuam la, sem relacao com este item.
- **Problema:** nenhum.
- **Resultado:** aprovado.

Objetivo:
Permitir que uma automacao seja realocada entre menus (Administrador, Backoffice,
LastMile, Parceiro) por configuracao, sem exigir edicao de template/codigo e
deploy para mudar onde ela aparece. Administrador e sempre o valor padrao.

Criterios de aceite:
- existe um registro por automacao com o menu de destino;
- automacao sem configuracao explicita aparece em Administrador;
- usuario com permissao de Administrador consegue alterar o menu de destino
  de uma automacao existente, sem deploy;
- o menu (`core/templates/core/base.html`) passa a renderizar a lista de
  automacoes de cada area a partir dessa configuracao, nao mais com link
  fixo por automacao;
- automacoes ja existentes (import de prospects, automacoes de Backoffice
  IXC) continuam funcionando e aparecendo no menu correto apos a migracao.

Regras relacionadas: RN-011 (docs/business_rules.md).

Decisao arquitetural: docs/ARCHITECTURE.md (secao "Configuracao de menu de
automacoes").

Tipo de feature: `fullstack` (QA obrigatorio) - novo model `AutomacaoMenu` +
migration + data migration para automacoes existentes, tela/acao de
configuracao restrita a Administrador, e refatoracao do menu (`base.html`)
para renderizar a partir da configuracao em vez de links fixos.

Dependencias:
- nenhuma bloqueante; recomenda-se implementar antes de adicionar novas
  automacoes que exijam menus diferentes de Administrador.

Agente recomendado para executar:
- `dev` (fullstack/backend_django)

## Epic 7 - Seguranca de credenciais

### PO-016 - Remover token IXC hardcoded no codigo e rotacionar a credencial exposta

Status: `✅ Concluida`

**Entrega do Dev:**
- Removido o valor real do token dos 10 arquivos listados abaixo.
- Token passa a vir somente de `os.getenv("IXC_TOKEN")`, com erro claro se ausente.
- Criado `.env.example` documentando as variaveis do projeto sem valores reais.
- Confirmado por busca no repositorio que o valor do token nao aparece mais em nenhum arquivo versionado.
- **Pendencia:** rotacao da credencial no IXC (acao fora do codigo, do usuario/dono do produto).

**Validacao do QA:**
- Busca pelo valor literal do token em todo o repositorio: nenhuma ocorrencia fora do `.env` (nao versionado).
- Conferidos os 10 arquivos listados: todos passaram a exigir `IXC_TOKEN` via variavel de ambiente, com erro claro se ausente.
- `python -m py_compile` nos arquivos alterados: sem erro de sintaxe.
- **Problema:** nenhum.
- **Resultado:** aprovado.

Objetivo:
Eliminar a credencial de acesso ao IXC gravada em texto plano como valor
padrao no codigo (viola CLAUDE.md secao 6 - Seguranca) e tratar a exposicao
ja ocorrida no historico do repositorio Git.

Escopo confirmado no mapeamento de 2026-07-21 (mais amplo que o registrado
originalmente no risco de PO-013):
- `scripts/integracoes/ixc_client.py`
- `scripts/integracoes/ixc_api.py`
- `scripts/integracoes/ixc_api_incremental.py`
- `scripts/integracoes/ixc_faxina.py`
- `scripts/integracoes/ixc_os_comercial_lastmile.py`
- `scripts/integracoes/ixc_primeira_os.py`
- `scripts/integracoes/debug_primeira_os_ixc.py`
- `scripts/integracoes/backoffice/cria_atendimento_ixc.py`
- `scripts/integracoes/backoffice/cria_login_atendimento.py`
- `scripts/integracoes/backoffice/descobrir_rota_IXC.py`

Criterios de aceite:
- nenhum arquivo do codigo contem o valor real do token, nem como default de
  `os.getenv(...)`, nem em constante;
- token so pode vir de variavel de ambiente, sem fallback para valor real;
- credencial exposta e rotacionada no IXC (acao junto ao provedor/usuario,
  fora do escopo de codigo) apos a limpeza do codigo;
- `.env.example` (ou equivalente) documenta a variavel `IXC_TOKEN` sem valor
  real.

Risco se nao tratado:
- a credencial ja esta no historico do Git (commit `7ef65cd` e anteriores);
  qualquer pessoa com acesso ao repositorio tem acesso operacional ao IXC.

Agente recomendado para executar:
- `dev` (remocao do hardcode); rotacao da credencial no IXC e decisao do
  usuario/dono do produto.

### PO-017 - Externalizar SECRET_KEY do Django para variavel de ambiente

Status: `✅ Concluida`

**Entrega do Dev:**
- `SECRET_KEY` deixou de ser literal e passa a ser lido via `config('SECRET_KEY')` (decouple), sem default.
- Gerado novo valor de `SECRET_KEY` (o anterior e tratado como comprometido) e adicionado ao `.env` local, nao versionado.
- Achado adicional no mesmo arquivo: `DB_PASSWORD` tambem tinha um valor padrao hardcoded (`config('DB_PASSWORD', default=...)`); corrigido da mesma forma, sem default.
- Validado com `python manage.py check` que as configuracoes carregam corretamente a partir do `.env`.
- **Correcao do apontamento do QA:** removido o arquivo orfao `config/Wsettings.py` (continha `SECRET_KEY` e `DB_PASSWORD` antigos em literal); `README.md`, `infor DEV.txt` e `migrar_credenciais_mysql_legado.sql` deixaram de citar as senhas reais, substituidas por referencia ao `.env`/cofre de segredos.
- **Pendencia:** `ALLOWED_HOSTS = ['*']` segue como observacao registrada, nao tratado (decisao de infra, fora deste item).

**Validacao do QA:**
- **Re-revisao apos correcao.** `config/Wsettings.py` nao existe mais no repositorio; `config/settings.py` le `SECRET_KEY` e `DB_PASSWORD` somente via `config(...)`, sem default.
- Busca pelos valores antigos de `SECRET_KEY` e `DB_PASSWORD` em todo o repositorio (nao so nos arquivos alterados): nenhuma ocorrencia restante em `README.md`, `infor DEV.txt` ou `migrar_credenciais_mysql_legado.sql` — todos passaram a referenciar o `.env`/cofre de segredos em vez do valor real.
- `python manage.py check` executado no container `speed_sistema`: sem erros, configuracoes carregam do `.env` normalmente.
- **Problema:** nenhum.
- **Resultado:** aprovado.

**Observacao (nao bloqueia a aprovacao):** as correcoes ainda estao apenas no working tree, sem commit. Recomenda-se commitar antes de considerar o item entregue de fato no historico do projeto.

Objetivo:
Remover o `SECRET_KEY` do Django gravado como literal em `config/settings.py`
(viola CLAUDE.md secao 6 - Seguranca), passando a le-lo obrigatoriamente de
variavel de ambiente.

Criterios de aceite:
- `SECRET_KEY` deixa de existir como literal no codigo;
- aplicacao falha de forma clara em subir sem a variavel de ambiente
  definida;
- valor atual e tratado como comprometido e substituido por um novo,
  gerado apos a mudanca.

Observacao relacionada:
- `ALLOWED_HOSTS = ['*']` tambem foi identificado no mesmo arquivo; avaliar
  se e adequado restringir para os hosts reais de producao (decisao de
  arquitetura/infra, nao bloqueante para este item).

Agente recomendado para executar:
- `dev`

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

## Ordem de prioridade sugerida

1. PO-016 (seguranca - credencial ja exposta no historico do Git)
2. PO-017 (seguranca - SECRET_KEY hardcoded)
3. PO-004
4. PO-005
5. PO-006
6. PO-007
7. PO-008
8. PO-009
9. PO-010
10. PO-011
11. PO-012
12. PO-013
13. PO-014 (investigacao; priorizar apos confirmar o risco)
14. PO-015
15. PO-018 (mapeamento de auditoria incompleto)
16. PO-019 (lacuna de logging de erros)
