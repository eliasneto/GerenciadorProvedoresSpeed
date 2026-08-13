# Backlog — Arquivo de features concluidas e descontinuadas

Historico das features ja aprovadas pelo QA (`Concluida`) e das que foram
fechadas sem execucao por estarem superadas ou fora do escopo atual
(`Descontinuada`). Separado do `docs/BACKLOG.md` em 2026-07-29 para que o
backlog ativo mostre apenas o que falta fazer.

Nao editar os blocos abaixo: sao registro do que aconteceu. Para retomar um
assunto ja concluido ou descontinuado, abrir uma PO nova no backlog ativo
referenciando a antiga.

## Descontinuadas (2026-07-29)

Fechadas na consolidacao documental de 2026-07-29, sem execucao — cada uma
porque a decisao que pedia ja foi tomada na pratica ou porque a informacao que
pedia passou a existir em outro documento mais completo. Nenhuma delas
apontava trabalho de codigo pendente.

### PO-003 - Completar regras, fluxos e contratos por modulo

Status: `Descontinuada`

Motivo do fechamento: coberta por `docs/business_rules.md` (RN-001 a RN-018) e
pelos diagramas `02 · Ciclo de vida da cotacao` e `03 · Modelo de dominio`, que
documentam regras, fluxos e contratos com mais profundidade do que esta PO
previa originalmente. Nenhuma execucao pendente identificada.

Objetivo original:
Detalhar regras de negocio, fluxos e contratos dos modulos com profundidade
suficiente para manutencao e suporte.

### PO-004 - Definir escopo da API publica v1

Status: `Descontinuada`

Motivo do fechamento: a decisao ja foi tomada e implementada na pratica —
PO-008 e PO-009 (`Concluida`, abaixo) ja entregaram os recursos de clientes,
enderecos, parceiros e propostas com healthcheck, exatamente o escopo proposto
aqui. Nao havia decisao pendente a formalizar.

Objetivo original:
Definir quais recursos entram na primeira versao da API.

### PO-005 - Definir padrao de versionamento e publicacao

Status: `Descontinuada`

Motivo do fechamento: prefixo `/api/v1/` e Swagger ja estao implementados e
documentados em `docs/ARCHITECTURE.md` ("Estado atual"). Decisao ja tomada e
executada na pratica.

Objetivo original:
Garantir que a API nasca com fronteira estavel.

### PO-012 - Consolidar mapa de integracoes existentes

Status: `Descontinuada`

Motivo do fechamento: coberta pelos diagramas `01 · Contexto do Sistema`,
`04 · Arquitetura-alvo`, `05 · Modulos e dependencias` e
`07 · Processos de automacoes e rotinas`, que documentam entradas, saidas,
dependencias e efeitos colaterais das integracoes com mais detalhe do que esta
PO previa.

Objetivo original:
Documentar entradas, saidas, dependencia de scripts e efeitos colaterais das
integracoes atuais.

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

## Epic 2 - Fronteira de API publica

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

## Epic 9 - Qualidade das mensagens de erro do Cadastro de Cliente IXC

### PO-020 - Esclarecer na mensagem de duplicidade do Cadastro de Cliente IXC qual campo gerou a correspondencia (CNPJ/CPF ou razao social)

Status: `Concluida`

Entrega do Dev (2026-07-24):
- Mensagem de bloqueio em `executar_cadastro_cliente_ixc` passou a indicar o
  campo (CNPJ/CPF ou razao social) e o valor comparado que gerou a
  correspondencia.
- Guia `docs/manuais/GUIA_CADASTRO_CLIENTES_IXC.md` atualizado com a nova
  redacao e explicacao do cenario de CNPJ compartilhado por varias entidades.
- Testes de `CadastroClienteIXCTests` (`apps/backoffice/tests.py`) ampliados
  para cobrir os dois cenarios (correspondencia por CNPJ/CPF e por razao
  social).
- **Validacao executada:** logica confirmada com chamada direta da funcao
  (mocks) fora do Django, pois o container `speed_sistema` nao monta o
  codigo deste repositorio (so `media/`) e roda uma copia desatualizada do
  projeto, e o ambiente local nao tem `mysqlclient` para rodar
  `manage.py test`. **Pendencia:** suite completa via `manage.py test` nao
  foi executada nesta entrega — recomenda-se ao Orquestrador/DevOps
  investigar a defasagem do container `speed_sistema`.

Validacao do QA (2026-07-24):
- `CadastroClienteIXCTests` (7/7) executada em container isolado (mesma
  imagem de `speed_sistema`, sem afetar o container em producao), cobrindo
  os dois cenarios de RN-015 (correspondencia por CNPJ/CPF e por razao
  social).
- Suite completa `apps.backoffice.tests` (28/28): sem regressao.
- Suite `apps.core_admin.tests` (20/21): 1 falha pre-existente e sem relacao
  (`AutomacaoMenuTests.test_migracao_de_dados_preservou_automacoes_existentes_em_administrador`,
  area de configuracao de menu de automacoes) — nao pertence ao escopo de
  PO-020, registrada como observacao separada para o Orquestrador.
- **Resultado:** aprovado.

Objetivo:
Corrigir ambiguidade encontrada na investigacao do `log_integracao_274`
(2026-07-24): quando a automacao de Cadastro de Cliente IXC bloqueia uma
linha por duplicidade, a mensagem atual ("Cliente ja existente no IXC (ID
{id}). Nenhuma alteracao feita para {razao_social}.") nao informa se a
correspondencia foi por CNPJ/CPF ou por razao social, nem qual valor foi
comparado. Isso gera confusao quando orgaos publicos municipais usam o
mesmo CNPJ para varias escolas/entidades distintas: o operador abre o ID
indicado no IXC e encontra um cadastro com nome diferente do esperado, e
interpreta como erro do sistema — quando na verdade o CNPJ realmente
coincide, apenas o nome e de outra entidade legitima.

Criterios de aceite:
- mensagem de bloqueio passa a indicar explicitamente o campo que gerou a
  correspondencia (CNPJ/CPF ou razao social) e o valor comparado;
- nenhuma mudanca no comportamento de bloqueio em si (RN-015) — a automacao
  continua nao cadastrando por padrao quando ha correspondencia, exceto com
  `Permitir_Duplicidade = Sim`;
- `docs/manuais/GUIA_CADASTRO_CLIENTES_IXC.md` atualizado se o texto da
  mensagem mudar de forma perceptivel ao usuario.

Regras relacionadas: RN-015 (docs/business_rules.md).

Tipo de feature: `backend-only` (ajuste apenas textual de mensagem, sem
mudanca de logica de bloqueio).

Agente recomendado para executar:
- `dev`

## Epic 10 - Arquitetura modular em camadas (ADR-005)

Direcao aprovada: evoluir para monolito modular em camadas (camada de servicos +
camada de integracao unificada + auditoria como barramento). Ver
`docs/adr/ADR-005_MONOLITO_MODULAR_EM_CAMADAS.md`. Evolucao incremental, app a app.

### PO-022 - Unificar o acesso ao IXC em um unico gateway

Status: `Concluida`

Validacao do QA (2026-07-27):
- Conferido que toda chamada de leitura ao IXC (cliente, radusuarios,
  cliente_contrato, filial, estado, cidade) passa pelo `IXCClient`; nenhuma
  reimplementacao de HTTP restou nos dois scripts de sync.
- Reproduzido o bug de schema do incremental (contrato cru com chave `id`
  chegando numa gravacao que esperava `id_contrato`) e confirmado que a
  normalizacao unica corrige o caso.
- Suite `scripts.integracoes` + `clientes` executada de forma independente:
  30/30. Regressao `backoffice` + `core_admin` + `auditoria`: 58/59 (mesma
  falha pre-existente ja registrada em PO-021, sem relacao com esta mudanca).
- **Observacao (nao impeditiva):** a troca para `IXCClient` passou a aplicar
  timeout de 30s onde antes nao havia limite; recomenda-se, na validacao em
  homologacao com IXC real ja prevista pelo Dev, cronometrar especificamente
  `buscar_mapa_cidades` (busca 10 mil registros de uma vez) e ajustar
  `IXC_TIMEOUT` se necessario.
- **Observacao (fora do escopo desta feature):** outros scripts de automacao
  do IXC (`ixc_faxina.py`, `ixc_explorador.py`, `cria_atendimento_ixc.py` e
  outros) ainda reimplementam HTTP proprio para o IXC. Nao fazem parte do
  objetivo desta PO (sync de clientes) e nao foram alterados; ficam como
  candidato a uma proxima PO de continuidade da ADR-005.
- **Resultado:** aprovado.

Entrega do Dev (2026-07-27):
- Criado `scripts/integracoes/ixc_sync_clientes.py`: modulo unico com toda
  normalizacao (UF/cidade/filial/endereco) e a gravacao em banco, usado pela
  carga total e pela incremental. Toda chamada ao IXC agora passa pelo
  `IXCClient`; `consultar_ixc` nao reimplementa mais HTTP.
- `ixc_api.py` e `ixc_api_incremental.py` viraram entrypoints finos (mesmos
  nomes/caminhos, sem alterar `docker-compose.yml` ou os `admin.py` que os
  disparam): so cuidam de CLI e do ciclo de vida do `HistoricoSincronizacao`.
- **Achado corrigido durante a unificacao:** o sync incremental montava a
  lista de contratos com as chaves cruas do IXC (`id`, `id_filial`), mas a
  gravacao esperava `id_contrato`/`filial_id` (formato so produzido pelo sync
  total) — gerava `KeyError` sempre que um cliente tinha contrato, mascarado
  pelo `except Exception` do script. Corrigido normalizando os dois caminhos
  de extracao para o mesmo formato antes da gravacao.
- Auditoria de alteracao de filial (que so existia no incremental) passou a
  valer tambem para a carga total.
- Testes adicionados em `scripts/integracoes/tests.py` (11 casos): normalizacao
  de UF/campos tecnicos, `consultar_ixc` via IXCClient, e regressao especifica
  do bug de schema de contrato (extracao incremental + gravacao).
- **Testes executados** (container isolado, mesma imagem de `speed_sistema`,
  sem afetar o container em producao): `scripts.integracoes` + `clientes`
  (30/30); regressao `backoffice` + `core_admin` + `auditoria` (58/59 — a 1
  falha e a mesma pre-existente e sem relacao ja registrada na entrega de
  PO-021, `AutomacaoMenuTests...administrador`).

Pendencia: sem acesso a credenciais reais do IXC neste ambiente, a validacao
foi feita com IXCClient mockado; recomenda-se ao QA (ou a uma execucao manual
em homologacao) rodar uma sincronizacao incremental real para confirmar o
comportamento do gateway unico contra o IXC de verdade.

Objetivo:
Fazer todo acesso ao IXC passar pelo cliente HTTP unico `IXCClient`
(`scripts/integracoes/ixc_client.py`) e eliminar a duplicacao entre os dois
scripts de sincronizacao de clientes IXC->Django, hoje quase identicos.

Contexto:
- `ixc_client.py` (`IXCClient`) ja e o cliente HTTP compartilhado, importado por
  backoffice, core_admin e pelos scripts de backoffice;
- `ixc_api.py` (sync completo) e `ixc_api_incremental.py` (sync incremental)
  reimplementam a comunicacao HTTP (`consultar_ixc` proprio) e repetem ~250 linhas
  de normalizacao (UF, cidade, filial, endereco), diferindo essencialmente em
  `extrair_todos_os_clientes` vs `extrair_clientes_recentes`;
- ambos sao consumidos por `apps/auditoria/admin.py` e pelo app solto `clientes/`.

Criterios de aceite:
- toda chamada HTTP ao IXC passa pelo `IXCClient`; nenhum modulo mantem
  implementacao HTTP paralela ao IXC;
- a logica compartilhada de normalizacao (UF, cidade, filial, endereco, campos
  tecnicos) existe em um unico modulo reutilizavel;
- as sincronizacoes completa e incremental passam a ser dois modos de uma unica
  rotina de sync, sem arquivos clones;
- comportamento funcional dos sync (completo e incremental) preservado e coberto
  por testes;
- sem regressao nas telas de `auditoria` e `clientes` que consomem os sync.

Tipo de feature: `backend-only` (QA obrigatorio).

Regras relacionadas: nenhuma nova; preserva RN de duplicidade ja existentes.

Agente recomendado para executar:
- `dev`

### PO-025 - Unificar os demais scripts de automacao IXC no IXCClient

Status: `Concluida`

Validacao do QA (2026-07-27):
- Conferido, arquivo por arquivo (diff completo), que os 8 scripts listados
  nao mantem HTTP/headers/token proprios; todos delegam ao `IXCClient`.
- Confirmado que `ixc_explorador.py` nao tem mais token hardcoded no codigo.
- Assinaturas de todas as funcoes consumidas por outros modulos
  (`executar_abertura_atendimento`, `executar_cadastro_ixc`,
  `normalizar_id_numerico`, `limpar_texto`, `montar_identificacao_usuario_importacao`,
  `validar_tipo_processo`, `executar_faxina`, `sincronizar_os_comercial_lastmile`)
  preservadas sem alteracao de contrato.
- Tracado manualmente, linha a linha, o comportamento de sucesso/erro dos dois
  scripts de escrita (abertura de atendimento e criacao de login) contra a
  versao anterior; equivalente em todos os casos que afetam o resultado
  (sucesso, recusa do IXC, sem ID, 401, erro HTTP), com diferenca apenas no
  texto de mensagens de erro em ramos ja raros (corpo nao-JSON), sem mudanca
  de resultado (falha continua falha).
- Suite `scripts.integracoes` + `backoffice` + `core_admin` + `auditoria` +
  `clientes` executada de forma independente: 103/104 (mesma falha
  pre-existente e sem relacao ja registrada em PO-021/PO-022).
- **Observacao (nao impeditiva):** a entrega do Dev cita 19 testes novos; a
  contagem real e 15 (9 em `scripts/integracoes/backoffice/tests.py` + 6 em
  `scripts/integracoes/tests.py`) — discrepancia de documentacao, sem impacto
  na cobertura em si.
- **Resultado:** aprovado.

Entrega do Dev (2026-07-27):
- Os 8 scripts listados passaram a usar `IXCClient` (leitura via `.listar()`,
  escrita via `.escrever()`); nenhum reimplementa mais HTTP/headers/token
  proprio para o `webservice/v1`.
- **Achado corrigido:** `ixc_explorador.py` tinha um token IXC hardcoded como
  placeholder no codigo (`IXC_TOKEN = "COLOQUE_SEU_TOKEN_AQUI"`), convidando a
  colar um token real em versionamento. Passou a usar `IXCClient` (token via
  variavel de ambiente), eliminando o risco.
- `cria_atendimento_ixc.py` e `cria_login_atendimento.py` (usados por varias
  outras automacoes de Backoffice) tiveram só a camada de transporte trocada;
  assinatura e contrato de retorno de todas as funções publicas preservados.
- Testes adicionados (19 casos) em `scripts/integracoes/tests.py` e
  `scripts/integracoes/backoffice/tests.py`, cobrindo com mais profundidade os
  dois scripts de escrita (sucesso, recusa do IXC, sem ID retornado, erro 401,
  erro HTTP generico, campo obrigatorio ausente) e com testes de contrato os
  demais.
- **Testes executados** (container isolado, mesma imagem de `speed_sistema`):
  `scripts.integracoes` + `backoffice` (76/76); regressao `core_admin` +
  `auditoria` + `clientes` incluida na mesma rodada (103/104 no total — a 1
  falha e a mesma pre-existente e sem relacao ja registrada em PO-021/PO-022).

Pendencia: sem credenciais reais do IXC neste ambiente, a validacao foi feita
com IXCClient mockado; recomenda-se, na mesma validacao em homologacao ja
prevista para PO-022, exercitar tambem a abertura de atendimento e a criacao
de login contra o IXC real.

Objetivo:
Continuar a unificacao iniciada em PO-022: fazer os demais scripts que ainda
reimplementam HTTP proprio para a API `webservice/v1` do IXC passarem a usar
o `IXCClient`, eliminando as implementacoes paralelas remanescentes.

Contexto:
Revisao de QA em PO-022 identificou que os seguintes scripts possuem cada um
sua propria funcao `consultar_ixc`/`get_headers`/`auth_headers` e HTTP cru
apontando para o mesmo `webservice/v1` que o `IXCClient` ja cobre:
- `scripts/integracoes/ixc_faxina.py`;
- `scripts/integracoes/ixc_explorador.py`;
- `scripts/integracoes/debug_primeira_os_ixc.py`;
- `scripts/integracoes/ixc_os_comercial_lastmile.py`;
- `scripts/integracoes/ixc_primeira_os.py`;
- `scripts/integracoes/backoffice/cria_atendimento_ixc.py`;
- `scripts/integracoes/backoffice/cria_login_atendimento.py`;
- `scripts/integracoes/backoffice/descobrir_rota_IXC.py`.

Fora desta feature:
`scripts/integracoes/ixc_ticket_arquivo_service.py` ja usa o `IXCClient` para
resolver a URL base, mas suas demais chamadas HTTP fazem navegacao no painel
web do IXC (login por `IXC_PANEL_EMAIL`/`IXC_PANEL_PASSWORD`, nao pelo token
da API). E uma fronteira de integracao diferente (painel web, nao
`webservice/v1`) e nao deve ser confundida com duplicacao da mesma API;
tratar em feature propria caso vire prioridade.

Criterios de aceite:
- os 8 scripts listados passam a obter dados do IXC via `IXCClient` (ou via o
  modulo `ixc_sync_clientes.py` quando a operacao for equivalente), sem
  reimplementar HTTP proprio para o `webservice/v1`;
- comportamento funcional de cada automacao preservado (faxina, exploracao de
  tabelas, criacao de atendimento/login, OS comercial lastmile, primeira OS);
- sem regressao nas automacoes de Backoffice e Lastmile que dependem desses
  scripts;
- cobertura de teste equivalente a PO-022 nos pontos de maior risco (schema de
  dados entre extracao e gravacao/chamada).

Tipo de feature: `backend-only` (QA obrigatorio).

Regras relacionadas: nenhuma nova.

Agente recomendado para executar:
- `dev`

### PO-023 - Extrair orquestracao de importacao das views de Backoffice para camada de servicos

Status: `Concluida`

Validacao do QA (2026-07-27):
- Conferido que as tres views (`cotacao_import`, `atendimento_import`,
  `cadastrar_clientes_ixc`) ficaram finas: so tratam metodo/arquivo da
  requisicao, mensagens/redirect e delegam ao `apps/backoffice/services.py`.
  Decoradores de permissao (`permissao_automacao` + `login_required`)
  preservados sem alteracao.
- Comparada a logica de cada `processar_*` com o comportamento anterior
  (inclusive o texto exato de mensagens e o caractere em-dash em
  "OK — apto para envio", verificado byte a byte); nenhuma divergencia
  encontrada.
- Confirmado que a view fora do escopo (`download_template_cadastro_cliente_ixc`,
  que usa `buscar_opcoes_ixc`) continua funcionando apos o realocamento.
- Suite `core_admin` + `backoffice` + `scripts.integracoes` + `auditoria` +
  `clientes` executada de forma independente: 107/108 (mesma falha
  pre-existente e sem relacao ja registrada em PO-021/PO-022/PO-025).
- Teste de bloqueio por permissao (achado pelo proprio Dev como lacuna
  pre-existente) validado com usuario real e banco real, confirmando que
  `PermissionDenied` continua sendo levantado corretamente apos a extracao.
- **Resultado:** aprovado.

Entrega do Dev (2026-07-27):
- Criado `apps/backoffice/services.py` com a orquestracao das tres importacoes
  (`processar_cotacao_import`, `processar_atendimento_import`,
  `processar_cadastro_clientes_ixc`), cada uma recebendo `(arquivo, usuario)` e
  devolvendo `(output, filename[, extras])` prontos para a view virar
  `HttpResponse`.
- `cotacao_import`, `atendimento_import` e `cadastrar_clientes_ixc` em
  `apps/backoffice/views.py` ficaram finas: so tratam HTTP (metodo, arquivo,
  mensagens, redirect) e chamam o servico correspondente.
- Eliminada, como parte da extracao, uma duplicacao real que havia entre
  `_ler_dataframe_upload` (cadastro de clientes) e a leitura inline de
  `atendimento_import`: ambas tinham a mesma cascata Excel/CSV com fallback de
  encoding; agora compartilham `_ler_planilha_com_fallback`, sem alterar o
  comportamento de nenhuma das duas (a normalizacao de nomes de coluna,
  especifica do cadastro de clientes, continua so nele).
- `apps/backoffice/views.py` caiu de 1250 para 799 linhas; a orquestracao
  extraida (451 linhas) passa a ser testável isoladamente da camada HTTP.
- **Achado corrigido em testes existentes:** 4 testes em `apps/core_admin/tests.py`
  e 1 em `apps/backoffice/tests.py` faziam `@patch`/`import` direto em nomes
  de `apps.backoffice.views` que se moveram para `services.py`; ajustados para
  o novo local (`ler_dataframe_upload` e o novo nome publico do antigo
  `_ler_dataframe_upload`).
- Adicionados testes de view novos (5 casos) em `apps/core_admin/tests.py`:
  sucesso e mistura sucesso/erro em `cotacao_import`, sucesso e planilha
  recusada na validacao previa em `atendimento_import`, e bloqueio de usuario
  sem permissao (numa `TestCase` propria, com banco real, ja que a checagem de
  permissao consulta `AutomacaoMenu`).
- **Testes executados** (container isolado, mesma imagem de `speed_sistema`):
  `core_admin` + `backoffice` + `scripts.integracoes` + `auditoria` + `clientes`
  executados juntos: 107/108 (1 falha pre-existente e sem relacao, ja
  registrada em PO-021/PO-022/PO-025).

Pendencia: nenhuma nova; RN-015/RN-016 (duplicidade) permanecem cobertas pelos
mesmos testes de `scripts.integracoes.backoffice` ja existentes, agora
exercitados tambem no nivel de view.

Objetivo:
Introduzir camada de servico em `apps/backoffice` e mover para ela a
orquestracao hoje duplicada dentro das views de importacao, deixando as views
finas (leitura da requisicao, chamada ao servico, resposta HTTP).

Contexto:
As tres views de importacao de planilha em `apps/backoffice/views.py`
(`cotacao_import`, `atendimento_import`, `cadastrar_clientes_ixc`) repetem, cada
uma com ~100 a 190 linhas, a mesma estrutura misturada com HTTP:
- leitura do arquivo (Excel/CSV, com fallback de encoding em `atendimento_import`);
- `registrar_auditoria_integracao` da importacao da planilha;
- em duas delas (`atendimento_import`, `cadastrar_clientes_ixc`), uma fase de
  validacao previa "tudo ou nada" (chama a regra de negocio ja existente em
  `scripts/integracoes/backoffice/*.py`, decide se a planilha inteira e
  recusada e gera um relatorio Excel de validacao);
- loop de execucao linha a linha chamando a funcao de regra correspondente
  (`executar_cadastro_ixc`, `executar_abertura_atendimento`,
  `executar_cadastro_cliente_ixc`);
- `registrar_auditoria_integracao` da execucao;
- geracao de relatorio Excel de resultado (`BytesIO` + `ExcelWriter` +
  `HttpResponse` com `Content-Disposition`), com pequenas variacoes de
  formatacao entre as tres.

As proprias regras de negocio (validacao de linha, montagem de payload, chamada
ao IXC) ja estao extraidas em `scripts/integracoes/backoffice/*.py` desde antes
desta ADR — o que esta duplicado e misturado com HTTP e a orquestracao do fluxo
de importacao (auditoria + tudo-ou-nada + execucao + relatorio), nao a regra em
si.

Nao existe hoje nenhum teste no nivel de view para essas tres rotas (os testes
atuais em `apps/backoffice/tests.py` e `scripts/integracoes/backoffice/tests.py`
cobrem as funcoes de regra chamadas pelas views, mas nao o fluxo completo de
upload -> validacao -> execucao -> relatorio via `self.client.post`).

Criterios de aceite:
- criado `apps/backoffice/services.py` (ou modulo equivalente) contendo a
  orquestracao de importacao (auditoria, tudo-ou-nada quando aplicavel,
  execucao linha a linha, geracao do relatorio Excel), reutilizada pelas tres
  views;
- `cotacao_import`, `atendimento_import` e `cadastrar_clientes_ixc` passam a
  apenas: validar a requisicao HTTP (metodo, arquivo presente), chamar o
  servico e devolver a resposta (arquivo ou redirect/mensagem);
- comportamento observavel preservado: mesmas mensagens, mesmo nome de arquivo
  de download, mesmas RN-015/RN-016 (duplicidade) aplicadas exatamente como
  hoje, mesmo formato de auditoria registrado;
- criados testes de view (via `self.client.post`, com as funcoes de regra
  mockadas) cobrindo pelo menos: upload valido com sucesso, planilha recusada
  na validacao previa (quando aplicavel), mistura de sucesso e erro na
  execucao, usuario sem permissao do grupo Backoffice bloqueado;
- sem regressao nos testes existentes de `scripts.integracoes.backoffice` e
  `apps/backoffice`;
- reducao de duplicacao entre as tres views e evidenciada (a orquestracao deixa
  de estar escrita tres vezes).

Fora desta feature:
- mover as funcoes de regra que ja estao em `scripts/integracoes/backoffice/*.py`
  para dentro do app `backoffice` (isso e o escopo de PO-024, reorganizacao de
  `scripts/` para os apps);
- alterar qualquer RN-XXX ou criterio de validacao existente.

Tipo de feature: `backend-only` (QA obrigatorio).

Regras relacionadas: RN-015, RN-016 (business_rules.md) — comportamento
preservado, nao alterado.

Agente recomendado para executar:
- `dev`

### PO-024 - Mover os modulos de regra do Backoffice de scripts/ para apps/backoffice

Status: `Concluida`

Validacao do QA (2026-07-27):
- Busca ampla e independente no repositorio inteiro: nenhum resquicio do
  caminho antigo (`scripts.integracoes.backoffice`), exceto `_testar_cadastro.py`
  (script solto, nao rastreado, ja sinalizado como fora do codebase mantido).
  Diretorio `scripts/integracoes/backoffice/` confirmado removido.
- Confirmado que `docker-compose.yml`/`docker-compose.local.yml` nao foram
  alterados.
- Inspecionado o conteudo real de cada um dos 8 modulos movidos e dos arquivos
  consumidores (`apps/backoffice/services.py`, `apps/backoffice/views.py`,
  `apps/core_admin/views.py`, `apps/auditoria/admin.py`): em todos, a unica
  mudanca e o caminho do import; nenhuma alteracao de comportamento.
- Conferido o arquivo de testes fundido: 12 classes, sem colisao de nomes,
  56 metodos de teste, nenhuma sobrescrita silenciosa.
- Suite `core_admin` + `backoffice` + `auditoria` + `scripts.integracoes` +
  `clientes` executada de forma independente: 107/108 (mesma falha
  pre-existente e sem relacao ja registrada em PO-021/PO-022/PO-025).
- Reexecutado de forma independente o smoke test de import via `django.setup()`
  (o mesmo que revelou a dependencia de `apps/auditoria/admin.py` durante o
  desenvolvimento) e `python manage.py check`: ambos sem erros.
- **Resultado:** aprovado. Sem achados.

Entrega do Dev (2026-07-27):
- Os 8 modulos moveram (via `git mv`, preservando historico) para
  `apps/backoffice/integracoes_ixc/`; importacoes cruzadas entre eles
  atualizadas para o novo caminho.
- Atualizados todos os pontos de import encontrados: `apps/backoffice/services.py`,
  `apps/backoffice/views.py`, `apps/backoffice/tests.py`, `apps/core_admin/views.py`,
  `apps/core_admin/tests.py`, `scripts/integracoes/tests.py` e
  `apps/auditoria/admin.py` (este ultimo nao constava no levantamento inicial
  do Orquestrador; encontrado ao rodar `django.setup()` apos a mudanca, que
  falhou no autodiscovery do admin ate a correcao).
- `scripts/integracoes/backoffice/tests.py` foi mesclado em `apps/backoffice/tests.py`
  (12 classes de teste ao todo, sem colisao de nomes; import fix de patches
  tambem aplicado); diretorio `scripts/integracoes/backoffice/` removido por
  completo (vazio apos a migracao).
- `docker-compose.yml` nao foi tocado (confirmado desnecessario no
  levantamento do Orquestrador e reconfirmado agora).
- `_testar_cadastro.py` (script solto, nao rastreado pelo git) ficou com
  import desatualizado, como ja esperado e registrado na feature.
- **Testes executados** (container isolado, mesma imagem de `speed_sistema`):
  `core_admin` + `backoffice` + `auditoria` + `scripts.integracoes` + `clientes`:
  107/108 (1 falha pre-existente e sem relacao, ja registrada em
  PO-021/PO-022/PO-025) — mesma contagem total de testes de antes da migracao
  (nenhum teste perdido ou duplicado na fusao).

Pendencia: nenhuma nova.

Objetivo:
Primeira fatia da reorganizacao prevista na ADR-005: mover os 8 modulos de
regra de negocio de `scripts/integracoes/backoffice/` para dentro do app
`apps/backoffice`, deixando de existir uma pasta de "regra de negocio" fora da
estrutura de apps Django para este dominio.

Contexto:
Levantamento confirmou que nenhum dos 8 modulos abaixo e invocado via
subprocess ou cron do `docker-compose.yml` (isso foi checado diretamente); todos
sao consumidos por import direto a partir de `apps/backoffice` e
`apps/core_admin`. Por isso, esta fatia especifica **nao precisa alterar
`docker-compose.yml`** nem qualquer configuracao de deploy — fica inteiramente
dentro do escopo do Dev, sem depender do DevOps:
- `cadastrar_cliente_ixc.py`;
- `cria_atendimento_ixc.py`;
- `cria_login_atendimento.py`;
- `desativar_atendimento_ixc.py`;
- `descobrir_rota_IXC.py`;
- `editar_atendimento_ixc.py`;
- `editar_login_ixc.py`;
- `resolver_os_atendimento_ixc.py`.

Pontos de import a atualizar (levantados diretamente, nao exaustivo — conferir
novamente no momento da implementacao): `apps/backoffice/services.py`,
`apps/backoffice/views.py`, `apps/backoffice/tests.py`, `apps/core_admin/views.py`,
`apps/core_admin/tests.py`, `scripts/integracoes/tests.py` (testa
`descobrir_rota_IXC`), e as importacoes cruzadas entre os proprios 8 modulos
(ex.: `resolver_os_atendimento_ixc.py` importa de `desativar_atendimento_ixc.py`
e de `cria_atendimento_ixc.py`).

Atencao: `scripts/integracoes/backoffice/tests.py` (arquivo hoje existente com
os testes desses 8 modulos) precisa ser conciliado com `apps/backoffice/tests.py`
(que ja existe e ja tem testes de view, incluindo os criados em PO-023) —
decidir se os testes sao mesclados num so arquivo ou organizados como pacote
`apps/backoffice/tests/`.

Dependencias externas que continuam fora do app (nao precisam mover nesta fase,
pois nao ha problema em `apps/backoffice` importar de `scripts/integracoes/`):
`ixc_client.py` (o gateway, ja e o alvo correto conforme ADR-005),
`ixc_finalizacao_service.py` e `ixc_ticket_arquivo_service.py` (usados por
`resolver_os_atendimento_ixc.py`/`desativar_atendimento_ixc.py`, mas com
dependencias proprias mais amplas — candidatos a uma fatia futura).

Observacao: existe um script solto `_testar_cadastro.py` na raiz do repositorio
(nao versionado/rastreado pelo git, marcado como "script temporario" no proprio
arquivo) que importa `cadastrar_cliente_ixc`; nao faz parte do codebase mantido
e nao precisa ser atualizado, mas fica registrado para nao causar confusao caso
alguem o encontre quebrado apos a mudanca.

Fora desta feature (candidatos a fatias futuras da ADR-005, todos com
acoplamento a cron/subprocess do `docker-compose.yml`, exigindo coordenacao com
o DevOps): `ixc_api.py`, `ixc_api_incremental.py`, `ixc_sync_clientes.py`,
`ixc_faxina.py`, `ixc_primeira_os.py`, `ixc_os_comercial_lastmile.py`,
`sincronizar_respostas_email_cotacao.py`, `ixc_finalizacao_service.py`,
`ixc_finalizar_os_lastmile.py`, `ixc_ticket_arquivo_service.py`, e a integracao
`Lastmile/APIGoogle_BuscaFornecedores.py`.

Criterios de aceite:
- os 8 modulos passam a residir dentro de `apps/backoffice` (estrutura interna
  de pastas fica a criterio do Dev, seguindo convencao Django);
- todos os pontos de import listados acima (e quaisquer outros encontrados na
  implementacao) atualizados; nenhuma referencia antiga a
  `scripts.integracoes.backoffice.*` restante no codigo versionado;
- testes dos 8 modulos preservados e passando, conciliados com
  `apps/backoffice/tests.py` sem perda de cobertura;
- nenhuma alteracao em `docker-compose.yml` ou em comportamento funcional das
  automacoes (RN-015, RN-016 e demais preservadas);
- sem regressao em `apps/backoffice`, `apps/core_admin`, `scripts.integracoes`
  (o que sobrar la).

Regras relacionadas: nenhuma nova; RN-015, RN-016 preservadas.

Tipo de feature: `backend-only` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

## Epic 11 - Portal de documentacao interna

### PO-028 - Criar rota com pagina de links para os documentos tecnicos (diagramas/ADRs)

Status: `Concluida`

Validacao do QA (2026-07-28):
- Rota `/docs/` testada sem login: retornou 200 e listou os 3 documentos hoje
  existentes em `docs/diagrams/` (incluindo o ADR-006).
- Rota `/docs/adr-006-expansao-modular.html/` testada: retornou o documento
  completo (200, `text/html`).
- Tentativa de acessar arquivo `.json` (fora da whitelist) e tentativa de
  path traversal (`../config/settings.py`) testadas: ambas bloqueadas com 404.
- Suite de testes da feature (4 testes) e suite completa de `apps.core`
  (9 testes) executadas em MySQL local: todas passaram, sem regressao.
- Nenhuma regra de negocio nova associada; decisao de rota sem autenticacao
  ja registrada em `ARCHITECTURE.md`.
- **Resultado:** aprovado.

Entrega do Dev (2026-07-28):
- Criada a rota publica `/docs/` (sem necessidade de login), que lista os
  documentos HTML existentes em `docs/diagrams/` (hoje: ADR-006, diagrama de
  arquitetura geral e diagrama do gerenciador).
- Criada a rota `/docs/<nome_arquivo>/` que serve o conteudo de cada documento
  individualmente, validando que o arquivo pertence a `docs/diagrams/` e tem
  extensao `.html`.
- Lista de documentos e gerada automaticamente a partir da pasta
  `docs/diagrams/` — novos diagramas aparecem sem alteracao de codigo.
- Pagina nova, com identidade visual propria, sem depender do menu interno
  (rota publica, sem sidebar/login).
- Criados testes cobrindo acesso sem login, listagem, bloqueio de extensao
  invalida e documento inexistente (404).
- **Pendencia:** suite de testes nao pode ser executada neste ambiente (Python
  local sem `mysqlclient` e stack Docker do projeto nao estava de pe); validado
  apenas por compilacao estatica dos arquivos alterados. Recomenda-se ao QA
  rodar a suite completa no container `speed_sistema` antes de aprovar.
  Validacao visual em navegador tambem nao foi executada pelo mesmo motivo.

Objetivo:
Permitir que outras pessoas do time acessem os documentos tecnicos (diagramas
de arquitetura, ADRs em HTML) pelo navegador, sem depender de abrir o arquivo
localmente via `file://`.

Contexto:
Hoje os diagramas gerados (ex.: `docs/diagrams/adr-006-expansao-modular.html`)
so podem ser abertos localmente por quem tem o repositorio na propria maquina.
Decisao registrada em `ARCHITECTURE.md` (secao "Portal de documentacao
interna"): criar uma rota simples, sem autenticacao, com uma pagina que lista
links para os documentos.

Criterios de aceite:
- rota HTML acessivel sem login (ex.: `/docs/`);
- pagina lista ao menos o link para
  `docs/diagrams/adr-006-expansao-modular.html`;
- estrutura permite adicionar novos documentos no futuro sem redesenho da
  pagina;
- nenhum dado de negocio, credencial ou informacao de cliente exposta na
  rota — apenas documentacao tecnica.

Fora desta feature:
- autenticacao/controle de acesso;
- geracao automatica da lista a partir do diretorio (Dev decide se a lista e
  mantida manualmente ou lida do sistema de arquivos).

Regras relacionadas: nenhuma.

Tipo de feature: `frontend-functional` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

## Epic 13 - Nova Infraestrutura (ADR-005/006/007)

### PO-031 - Unificar namespace de import para `apps.*`

Status: `Concluida`

Validacao do QA (2026-07-29):
- `apps/__init__.py` criado e `sys.path.insert` de `apps/` removido de
  `config/settings.py` — conferido por leitura direta dos dois arquivos.
- Busca ampla no repositorio inteiro por `from core.`, `from leads.`,
  `from partners.`, `from core_admin.`, `from auditoria.`, `from backoffice.`,
  `from clientes.`, `from integracoes_api.` (sem prefixo `apps.`): nenhuma
  ocorrencia restante, incluindo `apps/core_admin/tests.py`.
- `app_label` de cada app confirmado inalterado: nenhum `apps.py` declara
  `label` explicito, e `manage.py makemigrations --check --dry-run` nao
  gerou nenhuma migration nova.
- `manage.py check`: sem erro.
- Suite completa executada (140 testes): mesmas 2 falhas pre-existentes e
  sem relacao com o namespace (dependencia `tqdm` ausente; teste de menu do
  `core_admin`); nenhuma regressao.
- **Resultado:** aprovado.

Entrega do Dev (2026-07-29):
- `apps/__init__.py` criado; `sys.path.insert` de `apps/` removido de
  `config/settings.py`.
- `INSTALLED_APPS`, `MIDDLEWARE`, `TEMPLATES` e `config/urls.py` passaram a
  referenciar `apps.core`, `apps.leads`, `apps.partners`, `apps.core_admin`,
  `apps.auditoria`, `apps.backoffice` e `apps.integracoes_api` (`clientes`
  segue como estava, fora deste escopo).
- Todos os imports sem prefixo convertidos para `apps.*` em apps, scripts e
  testes, incluindo `apps/core_admin/tests.py`, que misturava os dois
  caminhos.
- `app_label` de cada app confirmado inalterado (`manage.py check` e
  `makemigrations --check` sem erro e sem migration nova).
- Suíte completa executada num MySQL local: 115 testes, 113 passaram; as 2
  falhas restantes já existiam antes desta entrega, sem relação com o
  namespace (dependência ausente no ambiente e teste de dado de automação).
- **Pendência:** nenhuma por parte do Dev; aguardando avaliação do QA.

Objetivo:
Eliminar o duplo caminho de import de app (`core` e `apps.core` resolvendo
para o mesmo codigo) fechando o defeito latente encontrado em 2026-07-29:
`apps/` nao e pacote Python (falta `__init__.py`) e `config/settings.py`
insere `apps/` no `sys.path`, entao todo app e importavel pelos dois caminhos
ao mesmo tempo. Hoje 76 imports usam o caminho sem prefixo e 49 usam
`apps.*` — o primeiro import de model feito pelo caminho errado duplica o
registro da classe no Django.

Contexto:
Achado no levantamento para o diagrama `05 · Modulos e dependencias` e
registrado na ADR-007, item 1. E o pre-requisito de tudo o mais neste epico:
mexer em estrutura de pastas com dois namespaces ativos multiplica o risco de
cada fatia seguinte.

Criterios de aceite:
- `apps/__init__.py` criado; `apps/` passa a ser pacote Python de verdade;
- `sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))` removido de
  `config/settings.py`;
- `INSTALLED_APPS` passa a listar `apps.core`, `apps.leads`, `apps.partners`,
  `apps.backoffice`, `apps.core_admin`, `apps.auditoria`,
  `apps.integracoes_api` (`apps.clientes` fica para a PO-029, que so faz
  sentido depois desta);
- os 76 imports sem prefixo (`from core.`, `from leads.`, `from partners.`,
  `from core_admin.`, `from auditoria.`) convertidos para `apps.*`;
- confirmado que o `app_label` de cada app nao muda (Django deriva do ultimo
  componente do caminho) — nenhuma migration de renomeacao e gerada;
- `python manage.py check` sem erro; nenhum aviso de model duplicado.

Verificacao de regressao obrigatoria (Dev, antes de marcar como pronta para
QA):
- rodar a suite de testes completa do projeto, nao so por app isolado —
  regressao de import e sistemica, nao local;
- smoke test de `django.setup()` limpo (mesmo teste que revelou a dependencia
  de `apps/auditoria/admin.py` durante a PO-024);
- grep amplo por `from core.` / `from leads.` / `from partners.` /
  `from core_admin.` / `from auditoria.` sem prefixo `apps.` remanescente no
  codigo versionado;
- atencao especial a `apps/core_admin/tests.py`, que hoje mistura os dois
  caminhos no mesmo arquivo (`from core_admin.admin import` e
  `from apps.core_admin.views import`) — e o caso mais provavel de quebrar
  silenciosamente.

Regras relacionadas: nenhuma.

Decisao arquitetural: `docs/adr/ADR-007_ESTRUTURA_ALVO_DO_REPOSITORIO.md`,
item 1.

Tipo de feature: `backend-only` (QA obrigatorio — alto risco, toca toda a
base de codigo).

Dependencias: nenhuma — primeira fatia do epico.

Agente recomendado para executar:
- `dev`

### PO-032 - Quebrar os ciclos de importacao entre apps e aplicar a ordem de camada da ADR-007

Status: `Concluída`

Histórico resumido: 1ª revisão do QA (2026-07-29) reprovou por
`apps/core/urls.py` reintroduzir o import proibido (só tinha mudado de
`views.py` para `urls.py`); Dev corrigiu movendo as rotas para `config/urls.py`.

Validação do QA — re-revisão (2026-07-30):
- Diff da correção revisado: `apps/core/urls.py` não importa mais
  `apps.leads`/`apps.partners`/`apps.core_admin`; as 8 rotas foram movidas
  para `config/urls.py` (fora da tabela de camadas da ADR-007), mesmos nomes
  e caminhos de URL.
- Grafo de imports entre os 8 apps refeito de forma independente: nenhum
  ciclo restante (`core` só importa `clientes`, camada 0 e camada-folha).
- `manage.py check` e `makemigrations --check --dry-run`: sem erro, sem
  migration nova.
- Suíte dos 6 apps envolvidos (131 testes) reexecutada: mesma 1 falha
  pré-existente (menu do `core_admin`), sem regressão nova.
- Rotas retestadas via test client com usuário autorizado: `home`,
  `minhas-cotacoes/`, os 6 relatórios de gestão e as rotas não movidas
  (`health/`, `docs/`, `login/`, `gestao/`) — mesmo código HTTP de antes.
- **Resultado:** aprovado.

Correção do Dev (2026-07-29):
- `apps/core/urls.py` deixou de importar `apps.leads`, `apps.partners` e
  `apps.core_admin` — as 8 rotas que dependiam dessas views (`home`,
  `minhas-cotacoes/`, `minhas-cotacoes/enviar-email/` e os 6
  `gestao/relatorios/...`) foram movidas para `config/urls.py`, que fica fora
  da tabela de camadas da ADR-007. Nomes de rota e comportamento inalterados.
- Grafo de imports entre os 8 apps refeito após a correção: nenhum ciclo
  restante (`core` volta a não importar de nada além de `clientes`, camada 0
  e camada-folha).
- `manage.py check` e `makemigrations --check`: sem erro, sem migration nova.
- Suíte dos 6 apps envolvidos (131 testes) e as 8 rotas realocadas testadas
  novamente via test client: mesmos resultados de antes da correção (mesma 1
  falha pré-existente, sem relação; nenhum código HTTP mudou).

Entrega do Dev (2026-07-29):
- Os 3 ciclos que nasciam de `apps/core/views.py` (core<->leads,
  core<->partners, core<->core_admin) foram eliminados: as views que liam
  `Lead`/`Proposal`/`ConfiguracaoEmailEnvio` migraram para o app dono do dado.
- `home` foi para `apps/leads/views.py`; os 6 relatorios de gestao (login x
  status, proposta x status, status x cliente, cotacao x endereco, login x
  usuario e seu POST de responsavel) foram para `apps/partners/views.py`.
- "Minhas Cotacoes" (lista + envio de e-mail) foi para
  `apps/core_admin/quotes_views.py` (novo arquivo) — unico lugar que pode ler
  `Proposal` (partners) e `ConfiguracaoEmailEnvio` (core_admin) ao mesmo tempo.
- `apps/core/urls.py` passou a rotear direto para as views novas, mesmo padrao
  ja usado pelo `include('apps.backoffice.urls')`; nomes de URL e templates
  inalterados (nenhuma tela muda de endereco).
- `manage.py check` sem erro; suite dos 6 apps (106 testes) e suite completa
  (115 testes) rodadas num MySQL local, mais 11 checagens manuais via test
  client nas telas movidas — mesmos codigos HTTP de antes, 2 falhas
  pre-existentes sem relacao com esta fatia (confirmado revertendo a mudanca).
- **Pendencia:** os ciclos `core_admin <-> backoffice` e `core_admin ->
  auditoria -> backoffice -> core_admin` nao foram resolvidos nesta fatia;
  dependem de decisao de arquitetura do Orquestrador (ver observacao
  detalhada na entrega).

Nota do Orquestrador (2026-07-29): os 2 ciclos remanescentes, mais a
divergencia adicional encontrada pelo Dev (`apps/partners/views.py` ja
importava `apps.auditoria.models.CotacaoStatusAuditoria`, camada 1 importando
da camada 2 — pre-existente, nao criada por esta fatia), foram desmembrados
para a **PO-036**, por exigirem decisao sobre ownership do registro
`AutomacaoMenu`/disparo manual compartilhado entre `core_admin` e
`backoffice`. Esta PO-032 cobre integralmente o que dependia dela (PO-011);
a `PO-036` e pre-requisito apenas da `PO-035` (gate final).

Dependencias: PO-031 (namespace unico).

Objetivo:
Eliminar os cinco ciclos de importacao encontrados em 2026-07-29
(`core`<->`core_admin`, `core`<->`leads`, `core`<->`partners`,
`core_admin`<->`backoffice`, `core_admin`->`auditoria`->`backoffice`->`core_admin`)
e passar a seguir a ordem de camada proposta no item 7 da ADR-007.

Contexto:
Levantado no diagrama `05 · Modulos e dependencias`. Tres dos cinco ciclos
nascem de um unico arquivo: `apps/core/views.py`, linhas 27-29, que importa de
`leads`, `partners` e `core_admin` — sendo `core` a camada mais baixa da
ordem proposta.

Criterios de aceite:
- ordem de camada da ADR-007 (item 7) confirmada pelo usuario em 2026-07-29 —
  vale como criterio de reprovacao em code review a partir de agora;
- `apps/core/views.py` deixa de importar `leads`, `partners` e `core_admin`
  diretamente — a logica que hoje vive ali migra para o app dono (o que le
  `Lead`/`Proposal` passa a ser uma chamada de servico do app dono, nao import
  direto de model alheio);
- os ciclos `core_admin <-> backoffice` e
  `core_admin -> auditoria -> backoffice -> core_admin` resolvidos aplicando a
  mesma regra (revisar caso a caso qual dependencia e a "errada" a remover);
- nenhum ciclo de import restante entre os 8 apps atuais;
- `clientes` continua sendo app-folha (nao passa a importar nada).

Verificacao de regressao obrigatoria (Dev):
- suite completa de testes de `core`, `core_admin`, `backoffice`, `leads`,
  `partners`, `auditoria` — sao exatamente os 6 apps envolvidos nos ciclos;
- mapear qual tela e atendida pela parte de `apps/core/views.py` que importa
  `leads`/`partners`/`core_admin`, e testa-la manualmente via navegador, nao
  so via teste automatizado, ja que e comportamento HTTP.

Regras relacionadas: nenhuma nova.

Decisao arquitetural: `docs/adr/ADR-007_ESTRUTURA_ALVO_DO_REPOSITORIO.md`,
item 7 (emenda de 2026-07-29).

Tipo de feature: `backend-only` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-033 - Criar `apps/integracoes/` (Hub de Integracao) e mover os gateways existentes

Status: `Concluída`

Validação do QA (2026-08-03):
- Busca ampla no codigo: nenhuma referencia restante a `apps.core.ixc_client`,
  `apps.core.integracoes_ixc`, `apps.core.ad_sync` ou aos caminhos antigos em
  `scripts/`; `apps/integracoes/correios/` confirmado como nao criado.
- `manage.py check` limpo; suite de `backoffice/core_admin/auditoria/leads/
  partners/core/scripts.integracoes` reexecutada de forma independente (301
  testes): mesmos 3 problemas pre-existentes e sem relacao (1 ja documentado
  na PO-036; 2 de encoding de emoji no console Windows, em script nao
  alterado por esta PO alem do import).
- Reexecutados manualmente os 4 gateways movidos (IXC, AD, Email, Google) e o
  wrapper `scripts/integracoes/sincronizar_respostas_email_cotacao.py`: mesmo
  comportamento de antes (mesma mensagem/retorno sem credencial configurada).
- Confirmado `docker-compose.yml` e os 2 botoes manuais de disparo
  (`clientes/admin.py`, `auditoria/admin.py`) inalterados - continuam
  apontando para o mesmo caminho de script.
- `docs/ARCHITECTURE.md` e os 4 diagramas (`04`/`05`/`06`/ANEXO A) conferidos:
  todos ja refletem `apps/integracoes/` como estrutura real, nao mais "alvo".
- **Resultado:** aprovado.

Entrega do Dev (2026-08-03):
- Criado `apps/integracoes/` com `ixc/` (`client.py` + `services/`, os 8
  modulos que vieram de `apps.core.integracoes_ixc`), `ad/` (`ad_sync.py`),
  `email/` (logica de `sincronizar_respostas_email_cotacao.py`) e `google/`
  (`APIGoogle_BuscaFornecedores.py` e `buscaParceiro.py`).
- Todos os imports atualizados (apps, scripts e testes, incluindo strings de
  `@patch`); busca no codigo versionado nao encontra mais nenhuma referencia
  aos caminhos antigos.
- `scripts/integracoes/sincronizar_respostas_email_cotacao.py` virou wrapper
  fino que so faz o bootstrap do Django e chama a logica movida; docker-compose
  e os 2 botoes manuais de disparo em `admin.py` continuam apontando para o
  mesmo caminho de arquivo, sem mudanca de comportamento.
- `apps/integracoes/correios/` nao criado — gap do CEP continua documentado
  em `docs/ARCHITECTURE.md`, conforme escopo.
- `manage.py check` limpo; suite de `backoffice/core_admin/auditoria/leads/
  partners/core/scripts.integracoes` (301 testes): 3 problemas, todos
  pre-existentes e sem relacao com esta PO (1 e a mesma falha ja documentada
  na PO-036 — `AutomacaoMenuTests...administrador`; 2 sao erro de encoding de
  emoji no console Windows do `ixc_explorador.py`, script nao alterado aqui
  alem do import do `IXCClient`).

Dependencias: PO-026 (`Concluida`) e PO-031 (`Concluida`, namespace unico) —
ambas ja satisfeitas.

Objetivo:
Criar o pacote `apps/integracoes/`, com uma subpasta por sistema externo
(`ixc/`, `ad/`, `email/`, `google/`), e mover para la os gateways que hoje
estao espalhados. E o "Hub de Integracao" da nova arquitetura: o lugar unico
onde vive a comunicacao com cada sistema externo.

**Reafirmacao de escopo (decisao ja tomada — nao reabrir sem nova conversa com
o usuario):** este Hub e organizacao de pastas, nao um Manager/Registry
generico. Cada servico continua importando o gateway especifico de que
precisa, direto (`from apps.integracoes.ixc.client import IXCClient`) — sem
despacho dinamico por nome, sem interface `BaseProvider` comum. Decisao
tomada e confirmada duas vezes: ADR-006 item 10 e ADR-007 item 4 (ambas
2026-07-29). Ver `docs/diagrams/integration-hub-conceitual.html` para o
desenho do que foi avaliado e descartado.

Escopo:
- `apps/integracoes/ixc/client.py` — recebeu o `IXCClient`, saindo de
  `apps/core/` (continuacao direta da PO-026);
- `apps/integracoes/ixc/services/` — recebeu tambem as funcoes de
  `apps/backoffice/integracoes_ixc/` (posicionadas em `apps/core` pela
  PO-036 como parada intermediaria; ver ADR-007 item 8);
- `apps/integracoes/ad/` — recebeu `ad_sync.py` (antes em `apps/core/`);
- `apps/integracoes/email/` — recebeu a logica de
  `sincronizar_respostas_email_cotacao.py` (antes em `scripts/integracoes/`);
- `apps/integracoes/google/` — recebeu `APIGoogle_BuscaFornecedores.py` e
  `buscaParceiro.py` (antes em `scripts/`);
- `apps/integracoes/correios/` — **nao criado**: gap conhecido (consulta
  de CEP inline em `clientes/views.py::buscar_cep`), sem gateway hoje. So vira
  pasta quando houver decisao de formalizar (ver gap conhecido em
  `docs/ARCHITECTURE.md`) — nao inventar gateway sem necessidade real.

Criterios de aceite:
- as quatro subpastas (`ixc`, `ad`, `email`, `google`) existem e contem o
  codigo movido, com `git mv` preservando historico onde possivel;
- todos os pontos de import atualizados para o novo caminho; nenhuma
  referencia antiga restante no codigo versionado;
- nenhuma alteracao de comportamento HTTP/IMAP/SMTP/API dos gateways movidos;
- `docs/ARCHITECTURE.md` e os diagramas `04`, `05`, `06` e ANEXO A atualizados
  para refletir que a estrutura passou de "alvo" para "real";
- `apps/integracoes/correios/` permanece como gap documentado, nao criado
  nesta PO.

Regras relacionadas: nenhuma nova.

Decisao arquitetural: `docs/adr/ADR-007_ESTRUTURA_ALVO_DO_REPOSITORIO.md`,
item 4.

Tipo de feature: `backend-only` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

### PO-034 - Migrar as rotinas agendadas de `scripts/` para management commands

Status: `Concluída`

Validação do QA — parte DevOps (2026-08-03):
- Diff conferido: so as 6 linhas esperadas mudaram no `docker-compose.yml`
  (5 para `python manage.py <comando>`, 1 para `python ops/backup_manual.py`);
  nenhuma outra linha do arquivo tocada.
- `docker compose config` (e `--profile backup` para o servico de backup,
  que fica atras de profile) confirma que as 6 linhas resolvem sem erro de
  sintaxe/escaping, com o nome exato dos 5 commands ja registrados em
  `manage.py help`.
- `ops/backup_manual.py` confirmado no caminho correto.
- **Observacao, nao bloqueia:** `README.md` ainda documenta
  `python scripts/integracoes/ixc_api.py`/`ixc_faxina.py` como exemplo de
  execucao manual — continua funcionando via wrapper, so ficou desatualizado;
  ajuste cosmetico para quando for conveniente, nao e defeito.
- **Pendencia operacional (fora de code review):** o rollout para o
  container em producao (rebuild/restart de `speed_sincronizador` e
  `speed_backup`) depende da janela de deploy do time — nao executado
  nesta sessao.
- **Resultado:** aprovado.

Entrega do DevOps (2026-08-03):
- `docker-compose.yml` atualizado nos 6 pontos que chamavam script por
  caminho de arquivo: os 5 que viraram management command agora chamam
  `python manage.py <comando>` (`ixc_sincronizacao_incremental`,
  `ixc_carga_total`, `ixc_os_comercial_lastmile`, `ixc_faxina`,
  `sincronizar_respostas_email_cotacao`); `backup_manual.py` (que nao virou
  command, foi para `ops/`) agora chama `python ops/backup_manual.py`.
- Nenhuma outra linha do `docker-compose.yml` alterada: mesmos horarios,
  mesmo loop `while true; sleep 60`, mesmas variaveis de ambiente e volumes.
- Validado com `docker compose config` (servico `speed_sincronizador` e,
  com `--profile backup`, o `speed_backup`): as 6 linhas resolvem
  exatamente para o comando esperado, sem erro de escaping no `sh -c`.
- **Pendencia:** troca validada apenas estaticamente (arquivo do repositorio);
  o rollout para o container em producao (rebuild/restart do
  `speed_sincronizador` e do `speed_backup`) exige janela de deploy
  coordenada com o time — nao executado nesta sessao, sem acesso ao
  servidor.

Validação do QA — parte funcional (2026-08-03):
- Busca ampla no codigo: nenhuma referencia antiga restante aos 6 scripts
  fora dos proprios wrappers finos; `docker-compose.yml` e os botoes manuais
  em `admin.py` conferidos linha a linha — inalterados, mesmo caminho de
  antes.
- Suite de `scripts.integracoes/clientes/backoffice/core_admin/auditoria/
  leads/partners/core` reexecutada de forma independente (301 testes):
  mesmos 3 problemas pre-existentes e sem relacao.
- Testados os 5 commands e o wrapper de backup fim a fim (funcao de rede
  mockada, escrita real em `HistoricoSincronizacao`): `ixc_os_comercial_lastmile`
  verificado com o argv real do Admin (`manual <user> --cliente-local-id=
  --os-alterada-desde=`), incluindo a geracao correta do arquivo de log;
  `ops/backup_manual.py` confirmado ate o ponto esperado (ambiente local sem
  `mysqldump`). Artefatos de teste removidos ao final.
- `backup_manual.py` nao virar management command (foi para `ops/` como
  script de infraestrutura) e decisao correta, ja prevista no proprio
  criterio de aceite (ADR-007 item 5).
- **Pendencia (fora do escopo do Dev, nao reprova a entrega):**
  `docker-compose.yml` continua chamando os scripts antigos (agora
  wrappers) e os 5 bootstraps manuais permanecem neles ate o DevOps
  coordenar a troca para `python manage.py <comando>` — exatamente como a
  propria PO ja previa.
- **Resultado:** aprovado (parte funcional/codigo).

Entrega do Dev (2026-08-03):
- Criados os 5 management commands: `ixc_carga_total` e
  `ixc_sincronizacao_incremental` (`apps/clientes`, vieram de `ixc_api.py`/
  `ixc_api_incremental.py`), `ixc_faxina` e `ixc_os_comercial_lastmile`
  (`apps/clientes`), `sincronizar_respostas_email_cotacao` (`apps/core`,
  chama a logica ja movida na PO-033).
- Os 5 scripts antigos em `scripts/integracoes/` viraram wrappers finos que
  delegam para os commands novos (`call_command`/`execute_from_command_line`);
  `docker-compose.yml` e os botoes manuais de disparo em `admin.py` continuam
  apontando para o mesmo caminho de arquivo, sem mudanca de comportamento.
- `backup_manual.py` avaliado e movido para `ops/` (infraestrutura, nao
  rotina de app — ADR-007 item 5), tambem com wrapper fino no caminho antigo.
- `scripts/integracoes/tests.py` atualizado (import e `@patch`) para os 2
  casos que testavam `ixc_faxina`/`ixc_os_comercial_lastmile` na localizacao
  antiga; nenhuma referencia antiga restante no codigo versionado.
- `manage.py check` limpo; os 5 commands aparecem em `manage.py help` e
  respondem a `--help`; suite de `scripts.integracoes/clientes/backoffice/
  core_admin/auditoria/leads/partners/core` (301 testes): mesmos 3 problemas
  pre-existentes e sem relacao, ja documentados nas entregas anteriores.
- **Pendencia:** nao foi possivel testar em homologacao real contra IXC/AD/
  Graph (sem ambiente ou credencial disponivel nesta sessao) — validado via
  `manage.py check`, parsing de argumentos e os testes automatizados
  existentes (mock do `IXCClient`). `docker-compose.yml` continua chamando os
  scripts antigos (agora wrappers); a troca para `python manage.py <comando>`
  direto e escopo do DevOps, conforme a propria PO ja determinava.

Dependencias: PO-031, PO-033 (os commands vao chamar os gateways ja movidos
para `apps/integracoes/`).

Objetivo:
Fechar a divergencia da ADR-007 item 5: as seis rotinas hoje chamadas por
caminho de arquivo no `docker-compose.yml` (`ixc_api_incremental.py`,
`ixc_api.py`, `ixc_os_comercial_lastmile.py`, `ixc_faxina.py`,
`sincronizar_respostas_email_cotacao.py`, `backup_manual.py`) passam a ser
management commands do app dono, eliminando os dez bootstraps manuais de
Django (`sys.path` + `django.setup()`) hoje espalhados por
`scripts/integracoes/`.

Contexto:
Levantado no diagrama `07 · Processos de automacoes e rotinas`. O agendador
hoje e um `while true; sleep 60` com estado em variavel de shell — reiniciar o
container perde o controle de "ja rodei neste slot". Migrar para management
command nao resolve isso sozinho (o loop continua sendo o agendador), mas e
pre-requisito para uma solucao melhor no futuro e resolve o bootstrap manual
imediatamente.

Criterios de aceite:
- as seis rotinas viram `manage.py <comando>` dentro do app dono;
- `docker-compose.yml` atualizado para chamar `python manage.py <comando>` em
  vez do caminho do arquivo — **coordenar com DevOps antes de alterar**, por
  mexer em rotina de producao;
- nenhuma mudanca de comportamento funcional das seis automacoes (mesmos
  horarios, mesmo resultado);
- os dez bootstraps manuais de Django em `scripts/integracoes/` removidos;
- `backup_manual.py` e `setup_speed.py` avaliados para mover para `ops/`
  (ADR-007) nesta mesma fatia, se nao aumentar o risco.

Verificacao de regressao obrigatoria (Dev):
- rodar manualmente cada um dos seis commands em homologacao e comparar o
  resultado com uma execucao do script antigo antes de considerar pronto;
- confirmar que `HistoricoSincronizacao` e `IntegrationAudit` continuam sendo
  gravados da mesma forma;
- validar com o DevOps a janela de deploy do `docker-compose.yml` antes de
  trocar em producao.

Regras relacionadas: nenhuma nova.

Decisao arquitetural: `docs/adr/ADR-007_ESTRUTURA_ALVO_DO_REPOSITORIO.md`,
item 5.

Tipo de feature: `devops` com impacto tecnico em `backend-only` (QA
obrigatorio na parte funcional; validacao tecnica do DevOps na troca do
`docker-compose.yml`).

Agente recomendado para executar:
- `dev` (commands); `devops` (docker-compose.yml e janela de deploy).

### PO-036 - Resolver os ciclos remanescentes core_admin<->backoffice e core_admin->auditoria->backoffice->core_admin

Status: `Concluída`

Validação do QA (2026-08-03):
- `AutomacaoMenu`, `RestoreBackupAuditoria` e `CotacaoStatusAuditoria`
  confirmados como models reais em `apps/core/models.py`; `apps/auditoria/models.py`
  mantem so proxies (`Meta.proxy = True`) dos dois ultimos, preservando a
  secao do Admin.
- `automacoes_registry.py` confirmado so em `apps/core/`; nao existe mais em
  `apps/core_admin/`.
- `apps/auditoria/admin.py` nao tem mais a action `processar_planilha_desativacao`
  (busca no codigo + teste proprio que afirma a ausencia); `apps/partners`
  nao importa mais `apps.auditoria` em nenhum ponto.
- Busca por cross-import entre `core`, `core_admin`, `backoffice` e
  `auditoria`: nenhuma referencia em codigo de producao (so um import de
  teste em `core_admin/tests.py`, fora da contagem de ciclos pela mesma
  convencao ja usada no diagrama 05); `apps/core` confirmado sem nenhum
  import desses 3 apps.
- `makemigrations --check --dry-run`: "No changes detected"; suite de
  `core/core_admin/backoffice/auditoria/partners` reexecutada de forma
  independente (252 testes): 1 falha, a mesma ja documentada e
  pre-existente (`AutomacaoMenuTests`).
- **Resultado:** aprovado.

Entrega do Dev (2026-07-29):
- `AutomacaoMenu`, `automacoes_registry.py`, `integracoes_ixc` e os 2 models
  de auditoria migrados para `apps/core`; imports atualizados em todo o resto.
- Migrations de state-move preservam as 3 tabelas fisicas; testadas em MySQL
  local descartavel com dado inserido manualmente — contagem identica (9/2/1).
- `auditoria/models.py` mantem os 2 models como proxy do real em `core`
  (mesmo precedente do `IntegrationAudit`), so para preservar a secao do Admin.
- Removida a action duplicada de `apps/auditoria/admin.py`; confirmado via
  test client que a URL antiga nao dispara mais nada e o botao de `core_admin` segue igual.
- `makemigrations --check` mostrou exatamente as 4 migrations esperadas;
  suites de `core/core_admin/backoffice/auditoria/partners` rodadas (102 testes, 1 falha).
- **Pendencia:** a falha (`AutomacaoMenuTests...administrador`) e anterior a
  esta PO — migration `core_admin/0007` (nao tocada por mim) ja contradizia esse teste.

Dependencias: PO-032 (entregou os outros 3 ciclos e a confirmacao da ordem de
camada; esta PO cobre o restante).

Decisao de ownership (usuario + Orquestrador, 2026-07-29 — ver item 8 da
ADR-007 para o raciocinio completo):
1. `apps/core_admin/automacoes_registry.py` + model `AutomacaoMenu` migram
   para `apps/core` (camada 0) — mesma natureza do `IntegrationAudit`, que ja
   mora la;
2. `apps/backoffice/integracoes_ixc/*.py` (funcoes de execucao das
   automacoes IXC) tambem migram para `apps/core`, como posicionamento
   intermediario — o levantamento confirmou que esse pacote nao depende de
   nada proprio de `backoffice`. Destino final continua sendo
   `apps/integracoes/ixc/services/` (item 4 da ADR-007), quando a PO-033
   rodar;
3. `RestoreBackupAuditoria` (unico escritor `core_admin`) e
   `CotacaoStatusAuditoria` (unico escritor `partners`) migram de `auditoria`
   para `apps/core`, seguindo o mesmo precedente do `IntegrationAudit`;
4. autorizada a remocao da action de disparo manual duplicada em
   `apps/auditoria/admin.py` (`processar_planilha_desativacao`, copia da
   mesma automacao ja disparada por `core_admin`) — `core_admin` passa a ser
   o unico ponto de disparo manual dessa automacao.

Objetivo:
Eliminar os 2 ciclos de importacao que a PO-032 nao resolveu, mais a
divergencia adicional encontrada durante a execucao dela: `apps/partners/views.py`
(camada 1) ja importava `apps.auditoria.models.CotacaoStatusAuditoria`
(camada 2) antes de qualquer mudanca desta fatia — nao e um dos 5 ciclos
originais, mas fere a mesma ordem de camada da ADR-007 item 7. Aplicando a
decisao acima, os 3 pontos de acoplamento (item 1 e 2 do ciclo
`core_admin<->backoffice`, e os 2 models de auditoria) passam a apontar so
para `apps/core` (camada 0) — nenhuma excecao de dependencia de mesma camada
alem da ja aprovada (`leads -> partners`) e necessaria.

Criterios de aceite:
- `AutomacaoMenu`, `automacoes_registry.py`, `RestoreBackupAuditoria` e
  `CotacaoStatusAuditoria` residem em `apps/core`; migrations geradas movendo
  os 3 models preservando dado (state move, sem recriar tabela nem perder
  registro existente);
- `apps/backoffice/integracoes_ixc/*.py` reside em `apps/core` (sem
  migration, sao so funcoes); todos os imports em `core_admin`,
  `auditoria`, `backoffice` e testes atualizados para o novo caminho;
- `apps/auditoria/admin.py` nao tem mais a action `processar_planilha_desativacao`
  (nem qualquer outro disparo manual duplicado da mesma automacao);
- `apps/partners/views.py` deixa de importar `apps.auditoria.models`
  diretamente — passa a ler `CotacaoStatusAuditoria` de `apps.core`;
- nenhum ciclo de import restante entre os 8 apps atuais (fecha o criterio
  que a PO-032 deixou em aberto);
- nenhuma alteracao de comportamento observavel das automacoes (mesmas
  mensagens, mesmo resultado) — exceto a remocao do botao duplicado em
  `auditoria/admin.py`, que e mudanca intencional e autorizada.

Verificacao de regressao obrigatoria (Dev):
- `python manage.py makemigrations --check` mostrando exatamente as
  migrations de state-move esperadas, nenhuma outra;
- suite completa de `core`, `core_admin`, `backoffice`, `auditoria`,
  `partners`;
- testar manualmente cada botao de disparo manual envolvido (ver diagrama
  `07`) antes e depois da mudanca, incluindo confirmar que o botao removido
  de `auditoria/admin.py` de fato some e que o de `core_admin` continua
  funcionando identico.

Regras relacionadas: nenhuma nova.

Decisao arquitetural: `docs/adr/ADR-007_ESTRUTURA_ALVO_DO_REPOSITORIO.md`,
item 8 (emenda de 2026-07-29).

Tipo de feature: `backend-only` (QA obrigatorio — envolve migration movendo
models entre apps).

Agente recomendado para executar:
- `dev`

### PO-011 - Separar logica reutilizavel de views extensas

Status: `Concluída` — as 4 fatias (`leads`, `core`, `partners`, `core_admin`)
entregues e aprovadas pelo QA.

Validação do QA — fatias leads/core/partners (2026-08-03):
- **leads:** `services.py` (1147 linhas) confirmado com a regra de negocio
  migrada; `views.py` (1952 -> 570 linhas) so chama `services.*`;
  `mover_lead_para_negociacao` usa `LEAD_STATUS_CHOICES` (fix da PO-037 ja
  aplicado e confirmado no codigo).
- **core:** `services.py` (230 linhas) confirmado; `views.py` (1660 -> 310
  linhas) importa e chama `services.*`; achado de codigo morto
  (`gestao_logs_integracoes`) segue rastreado separadamente na PO-038, sem
  link quebrado novo.
- **partners:** `services.py` (1850 linhas) confirmado, incluindo a
  sub-fatia de maior risco (Fechamento de O.S./edicao financeira) —
  `proposal_update`/`proposal_batch_status_update` inspecionados: a view
  ficou fina (so HTTP/contexto), toda a regra (RN-017/018, integracao IXC,
  calculo financeiro) esta em `services.aplicar_atualizacao_lote_status`/
  `processar_conversao_viavel`/`processar_edicao_proposta`, com historico e
  auditoria preservados; achado de UI (`partner_detail` sem exibir
  historico) segue rastreado na PO-039.
- **Regressao:** `makemigrations --check --dry-run`: "No changes detected";
  suite isolada de `apps.leads`, `apps.core` e `apps.partners` reexecutada
  de forma independente — **139 testes, 100% aprovados** (nenhuma das 2
  falhas pre-existentes conhecidas pertence a esses 3 apps).
- **Resultado:** aprovado.

Decisao do Orquestrador (2026-07-29): QA valida cada fatia (app) de forma
independente, assim que o Dev a entregar, em vez de esperar as quatro fatias
prontas. Reduz o lote de risco por revisao e cada app ja tem suite isolada.
Decisao tecnica reversivel e de baixo risco — nao altera regra de negocio,
arquitetura ou criterio de aceite original (que ja previa entrega fatiada).

Entrega do Dev — fatia leads (2026-07-29):
- Criado `apps/leads/services.py` com a regra de negocio que estava nas
  views (casamento/sincronizacao lead-parceiro, conversao, transicoes de
  status, importacao de planilha e buscas/filtros das telas de listagem).
- Views de `leads` passaram a apenas validar a requisicao, chamar o servico
  e devolver mensagem/redirect; ~450 linhas de views duplicadas/mortas
  (ja substituidas por `lastmile_views.py` em entrega anterior) removidas.
- 23 testes de view novos (`self.client.get/post`), cobrindo fluxos sem
  cobertura HTTP ate agora (cadastro, edicao, exclusao, status, conversao,
  proposta rapida, importacao).
- Suite de `leads` (antes/depois) e suite completa do projeto executadas;
  sem regressao. Duas falhas pre-existentes sem relacao com `leads`
  (dependencia `tqdm` ausente; teste de menu do `core_admin`) continuam la.
- **Achado, nao corrigido:** `update_lead_status` referencia
  `Lead.STATUS_CHOICES` (inexistente; o certo e `LEAD_STATUS_CHOICES`) e
  quebra ao mover lead para "negociacao" a partir de outro status. Registrado
  como PO-037 (bug, fora do escopo desta PO; ja entregue e aguardando QA).

Entrega do Dev — fatia core (2026-07-30):
- Criado `apps/core/services.py`: saude do sistema (com o mesmo cache de
  30s), portal de documentacao (listar/ler diagrama com a mesma validacao de
  path traversal), catalogo de relatorios de gestao, filtro de logs de
  integracao e historico generico (`RegistroHistorico`) de leitura/escrita.
- Views (`system_health`, `docs_index`, `docs_documento`,
  `gestao_relatorios`, `gestao_logs_integracoes`, `timeline_global`) passaram
  a apenas validar a requisicao, chamar o servico e renderizar. Utilitarios
  genericos (`_resolve_sort`, `_csv_response`, `grupo_*_required` etc.), ja
  reaproveitados por `partners`/`core_admin`, permaneceram em `views.py` sem
  mudanca de local ou assinatura — nenhum import de outro app foi afetado.
- 14 testes de view novos, cobrindo fluxos sem cobertura HTTP ate agora
  (healthcheck ok/indisponivel, permissao e busca de `gestao_relatorios`,
  permissao de `gestao_logs_integracoes`/`gestao_log_integracao_detail`, e
  `timeline_global` completo: listagem por periodo, criacao de comentario e
  de anexo, permissao); mais 6 testes de servico para o filtro de logs.
- Suite completa do projeto (158 testes) executada; `manage.py check` e
  `makemigrations --check --dry-run` sem erro. Mesmas 2 falhas pre-existentes
  sem relacao com esta fatia (dependencia `tqdm` ausente; teste de menu do
  `core_admin`).
- **Achado, nao corrigido:** `gestao_logs_integracoes` e
  `gestao_log_integracao_detail` nao tem rota em nenhum `urls.py` do projeto
  e os dois templates fazem `{% url 'gestao_logs_integracoes' %}`
  (inexistente) — a pagina quebra mesmo chamando a view direto, antes desta
  fatia e sem relacao com ela. Decisao do usuario (2026-07-30): remover o
  codigo morto em vez de reativar — ver PO-038.
- **Pendencia:** fatias `core_admin` e `partners` ainda nao entregues.

Entrega do Dev — fatia partners, grupo Parceiro (2026-07-30):
- Criado `apps/partners/services.py` com a regra de negocio das 10 views do
  grupo Parceiro: listagem/agrupamento de parceiros convertidos (dedup por
  lote), agrupamento de propostas em aberto por cliente/lote, historico
  ativo/arquivado, planos, clientes vinculados e as duas transicoes de
  status mais sensiveis — inativar/declinar/contratar parceiro e a esteira
  de reativacao win-back (que arquiva historico e apaga as propostas do
  parceiro ao voltar para "andamento").
- Views (`partner_list`, `partner_inactive_list`, `partner_detail`,
  `partner_plan_manage`, `partner_add_historico`, `update_partner_status`,
  `update_winback_status`, `partner_clients_list`) passaram a apenas validar
  a requisicao, chamar o servico e renderizar/redirecionar.
  `partner_add_historico` passou a reusar
  `apps.core.services.registrar_historico_generico` (camada 0) em vez de
  duplicar a logica de comentario/anexo.
- 23 testes de view e servico novos, cobrindo fluxos sem cobertura HTTP ate
  agora: permissao, deduplicacao de lote convertido, agrupamento por
  cliente/lote, toggle de historico antigo, CRUD de plano, bloqueio de
  transicao a partir de aguardando_contratacao, e o caminho destrutivo do
  win-back (reativacao apaga propostas e arquiva historico).
- Suite completa do projeto (178 testes) executada; `manage.py check` e
  `makemigrations --check --dry-run` sem erro. Mesmas 2 falhas pre-existentes
  sem relacao com esta fatia.
- **Achado, nao corrigido:** `partner_detail.html` nao usa `historico`,
  `qtd_antigo` nem `ver_antigos` — a view calcula os tres a cada requisicao
  mas o template nunca os renderiza (a tela nao mostra o historico do
  parceiro nem o toggle "ver antigos"). Pre-existente, preservado
  fielmente na extracao. Decisao do usuario (2026-07-30): construir a tela
  — ver PO-039.
- **Pendencia:** grupos `Proposta` e `Relatorios de Gestao` de `partners`, e
  a fatia `core_admin`, ainda nao entregues.

Entrega do Dev — fatia partners, grupo Relatorios de Gestao (2026-07-30):
- Movidos para `apps/partners/services.py` os 6 relatorios de gestao
  (Responsaveis por Endereco, Status por Endereco, Status por Cotacao,
  Cotacao por Cliente, Cotacao por Endereco e a troca de responsavel do
  login) e os 6 helpers de formatacao (`_proposal_cliente_nome` e
  similares) que ja existiam isolados na view, so nao estavam em
  `services.py`. Consulta repetida (subquery de ultima interacao) deixou de
  ser duplicada 3x — agora e uma unica funcao. `apps/core_admin/quotes_views.py`
  importava 3 desses helpers direto de `apps.partners.views`; import
  corrigido para `apps.partners.services` (unico ajuste fora do arquivo).
- Views passaram a apenas resolver ordenacao/paginacao (`_resolve_sort`,
  `Paginator`), montar o CSV de exportacao e renderizar — a montagem de cada
  relatorio (queryset, filtros, agrupamento por lote/cliente/endereco e
  contagem por status) ficou no servico.
- 25 testes de view novos, cobrindo os 6 relatorios sem cobertura HTTP ate
  agora: permissao, agrupamento por lote/cliente/endereco, contagem por
  status, filtros (busca/cliente/endereco/usuario), exportacao CSV e as 4
  ramificacoes da troca de responsavel do login (bloqueio fora de analise,
  bloqueio sem usuario, sucesso com historico, permissao).
- Suite completa do projeto (195 testes) executada; `manage.py check` e
  `makemigrations --check --dry-run` sem erro. Mesmas 2 falhas
  pre-existentes sem relacao com esta fatia.
- **Observacao, nao corrigida (sem impacto funcional):** os templates de
  `gestao_relatorio_login_status` e `gestao_relatorio_proposta_status`
  estao com nomes de arquivo trocados/confusos
  (`gestao_relatorio_proposta_status.html` e
  `..._proposta_status_real.html`, respectivamente) — cada view renderiza
  corretamente o seu proprio template, so o nome do arquivo em disco nao
  bate com o nome da view. Pre-existente, preservado fielmente (nenhuma
  tela quebra); nao registrado como PO por ser so nomenclatura, sem
  comportamento incorreto.
- **Pendencia:** grupo `Proposta` de `partners`, e a fatia `core_admin`,
  ainda nao entregues.

Plano do Orquestrador (2026-07-30) — decomposicao do grupo `Proposta`:
levantamento direto de `apps/partners/views.py` mostra ~900 linhas
remanescentes em 13 views, concentracao de risco desigual entre elas.
3 sub-fatias, na ordem abaixo (a ordem reduz o risco por entrega, do mais
simples ao mais critico):

1. **CRUD e navegacao** (~170 linhas): `proposal_create`, `proposal_detail`,
   `proposal_assumir_responsavel`, `proposal_add_historico`,
   `proposal_status_update`, `proposal_delete`, `proposal_global_list`,
   `address_proposals_list`. Risco baixo — telas simples de criar/ver/excluir.
2. **Lote (batch)** (~130 linhas): `proposal_batch_detail`,
   `proposal_batch_logins`, `proposal_batch_add_historico`. Risco baixo —
   agrupamento/exibicao de logins de um mesmo lote.
3. **Fechamento de O.S. e edicao financeira** (~590 linhas, incluindo os
   helpers privados hoje no topo do arquivo — `_baixar_endereco_da_fila_lastmile`,
   `_resumir_erro_anexo_ixc`, `_encerrar_outras_cotacoes_automaticamente` e
   afins; `_registrar_auditoria_status_cotacao`, `_propostas_com_os_lastmile`
   e as duas funcoes de "outras cotacoes no mesmo endereco" ja foram
   relocadas nas sub-fatias 1 e 2): `proposal_update` (maior view do app) e
   `proposal_batch_status_update`. **Risco alto** — RN-017/RN-018,
   integracao com o `IXCGateway` e a fila de fallback da ADR-006, calculo
   financeiro (`resultado_mensal`, `valor_total_proposta`). QA deve dar
   atencao redobrada aqui: cenarios de erro do IXC, calculo financeiro e
   nao-regressao das regras de status.

Entrega do Dev — fatia partners, grupo Proposta, sub-fatia Lote (2026-07-30):
- Criadas em `apps/partners/services.py`: `listar_propostas_do_lote`,
  `montar_historico_do_lote` (deduplica registros replicados nas propostas
  do lote, com contagem de quantas foram afetadas),
  `montar_contexto_lote` e `replicar_historico_lote`.
- `_propostas_com_os_lastmile`, `_endereco_possui_os_lastmile`,
  `_outras_cotacoes_em_negociacao_mesmo_endereco` e
  `_montar_resumo_outras_cotacoes_por_endereco` (compartilhados com a
  sub-fatia `Fechamento de O.S.`, ainda nao migrada) foram relocados para
  `services.py` sem alteracao de logica; o unico ponto de chamada restante
  em `views.py` (dentro de `proposal_batch_status_update`) so ganhou o
  prefixo `services.`.
- As 3 views da sub-fatia (`proposal_batch_detail`, `proposal_batch_logins`,
  `proposal_batch_add_historico`) passaram a apenas validar a requisicao,
  chamar o servico e renderizar/redirecionar.
- 8 testes de view novos, cobrindo fluxos sem cobertura HTTP ate agora:
  contagem de logins do lote, deduplicacao de historico replicado no mesmo
  instante, alerta de OS LastMile, outras cotacoes em negociacao no mesmo
  endereco, listagem de logins do lote e replicacao de historico (com
  POST vazio ignorado).
- Suite completa do projeto (219 testes) executada; `manage.py check` e
  `makemigrations --check --dry-run` sem erro. Mesmas 2 falhas
  pre-existentes sem relacao com esta fatia.
- **Pendencia:** sub-fatia `Fechamento de O.S./edicao financeira` do grupo
  `Proposta`, e a fatia `core_admin`, ainda nao entregues.

Entrega do Dev — fatia partners, grupo Proposta, sub-fatia CRUD e navegacao
(2026-07-30):
- Criadas em `apps/partners/services.py`: `criar_proposal`,
  `assumir_responsavel_login`, `atualizar_status_proposal_individual`,
  `listar_propostas_globais`, `listar_propostas_do_endereco`.
  `proposal_detail` passou a reusar `apps.core.services.listar_historico_periodo`
  e `proposal_add_historico` a reusar
  `apps.core.services.registrar_historico_generico` (camada 0), em vez de
  duplicar logica.
- `_registrar_historico_proposta` e `_registrar_auditoria_status_cotacao`
  (helpers compartilhados com as sub-fatias `Lote` e `Fechamento de O.S.`,
  ainda nao migradas) foram relocados para `services.py` sem alteracao de
  logica; os demais pontos de chamada em `views.py` (dentro de
  `proposal_batch_status_update`, `proposal_update` e
  `_encerrar_outras_cotacoes_automaticamente`) so tiveram o prefixo
  `services.` adicionado — nenhuma outra linha dessas views foi tocada.
- As 8 views da sub-fatia passaram a apenas validar a requisicao, chamar o
  servico e renderizar/redirecionar.
- 26 testes de view novos, cobrindo fluxos sem cobertura HTTP ate agora:
  criacao de proposta (com/sem endereco), listagem de historico por
  periodo, assumir responsavel (bloqueio fora de analise, ja-responsavel,
  sucesso), historico de proposta, as 4 ramificacoes de troca de status
  (invalido, "ativa", sem mudanca, atualizado com auditoria), exclusao e as
  2 listagens (global e por endereco).
- Suite completa do projeto (211 testes) executada; `manage.py check` e
  `makemigrations --check --dry-run` sem erro. Mesmas 2 falhas
  pre-existentes sem relacao com esta fatia.
- **Pendencia:** sub-fatias `Lote` e `Fechamento de O.S./edicao financeira`
  do grupo `Proposta`, e a fatia `core_admin`, ainda nao entregues.

Entrega do Dev — fatia partners, grupo Proposta, sub-fatia Fechamento de
O.S./edicao financeira (2026-07-30):
- Criadas em `apps/partners/services.py`: `processar_conversao_viavel`
  (fecha a fila LastMile no IXC quando aplicavel, encerra outras cotacoes
  do mesmo endereco quando solicitado e registra a auditoria de status),
  `processar_edicao_proposta` (edicao financeira normal, com historico de
  antes/depois por campo e criacao de links/clones para enderecos
  adicionais) e `aplicar_atualizacao_lote_status` (as transicoes de status
  do lote: declinado, inviavel, aguardando_contratacao com ou sem
  alteracao de OS no IXC, e contratado). Os helpers que ja apoiavam esse
  fluxo (`_registrar_auditoria_status_cotacao`, `_propostas_com_os_lastmile`,
  `_baixar_endereco_da_fila_lastmile`, `_resumir_erro_anexo_ixc`,
  `_encerrar_outras_cotacoes_automaticamente`) foram movidos junto, sem
  alteracao de logica.
- Views `proposal_update` e `proposal_batch_status_update` — as duas
  ultimas do app `partners` com regra de negocio, RN-017/RN-018 e
  integracao com o `IXCGateway` — passaram a apenas montar o contexto de
  exibicao, validar a requisicao, chamar o servico e renderizar/redirecionar.
- 22 testes novos, cobrindo os cenarios de maior risco desta sub-fatia: as
  ramificacoes de fechamento do lote com IXC (sucesso, falha, sem
  observacao, sem alterar OS), bloqueio de conversao quando ha outras
  cotacoes do mesmo endereco em negociacao, conversao com e sem OS
  LastMile, edicao normal com historico de antes/depois, criacao de link
  para endereco extra e feedback de OS do IXC ja finalizada (idempotencia).
- Suite completa do projeto (238 testes) e suite isolada de `partners` (83
  testes) executadas; `manage.py check` e `makemigrations --check
  --dry-run` sem erro. Mesmas 2 falhas pre-existentes sem relacao com esta
  fatia (dependencia `tqdm` ausente; teste de menu do `core_admin`).
- Com esta entrega, a fatia `partners` da PO-011 esta integralmente
  concluida (Parceiro, Relatorios de Gestao e os 3 sub-grupos de Proposta)
  e aguardando QA.
- **Pendencia:** fatia `core_admin` ainda nao entregue.

Entrega do Dev — fatia core_admin (2026-07-30):
Ultima fatia pendente da PO-011, fatiada internamente em 5 grupos por
risco (do mais simples ao mais critico), mesmo padrao usado em `partners`:
- **Diagnosticos** (`smtp_test`, `testar_api_ixc`): validacao de e-mail e
  envio de teste SMTP, e consulta de status da API do IXC, movidos para
  `services.py`.
- **Download de templates** (5 views de modelo de planilha, incluindo as
  4 usadas pelas automacoes de IXC): montagem do arquivo XLSX e auditoria
  de download movidas para `services.py`; views passaram a so montar a
  resposta HTTP.
- **Hub de automacoes + importacao de prospects** (`automacoes_area`,
  `import_prospects`): contexto da central de automacoes (status das
  ultimas execucoes de cada integracao) e o fluxo de iniciar/interromper
  a importacao de prospects em segundo plano movidos para `services.py`.
- **Automacoes IXC** (`desativar_atendimentos_ixc`, `editar_atendimentos_ixc`,
  `resolver_os_atendimento_ixc`, `editar_logins_ixc`): leitura da planilha,
  execucao linha a linha contra o IXC, auditoria de importacao/execucao e
  montagem do relatorio de resultado movidos para `services.py`. Views
  passaram a apenas validar o upload e tratar erro com mensagem/redirect.
- **Backup/restore** (`restore_backup`, risco mais alto — restaura o banco
  de producao): guardas de seguranca contra zip-slip
  (`_is_within_directory`/`_extract_zip_safely`), listagem e resolucao de
  backups salvos no servidor, e a execucao do restore (`mysql` + sincronizacao
  da pasta `media`) movidos para `services.py`, sem alteracao de logica.
  A view manteve integralmente o fluxo de validacao e as mensagens
  existentes (inclusive a assimetria ja existente: falha de validacao do
  ZIP antes do restore nao gera auditoria; falha durante o restore gera).
- 52 testes novos, cobrindo fluxos sem cobertura HTTP ate agora em todos os
  5 grupos: permissao, validacao de arquivo, os 2 ramos de diagnostico, o
  hub de automacoes (menu invalido, grupo exigido, importacao bloqueada/em
  andamento/falha ao iniciar) e, no grupo mais sensivel, guardas de
  seguranca do restore de backup (path traversal na escolha de um backup
  do servidor, zip-slip na extracao, SQL ausente ou vazio) com
  `services.restaurar_banco_e_midia` sempre mockado — nenhum teste executa
  `mysql` de verdade.
- Suite completa do projeto (290 testes) e suite isolada de `core_admin`
  (80 testes) executadas; `manage.py check` e `makemigrations --check
  --dry-run` sem erro. Mesmas 2 falhas pre-existentes sem relacao com esta
  fatia (dependencia `tqdm` ausente; teste de menu do `core_admin`, este
  ultimo pre-existente e nao relacionado a nenhuma view tocada aqui).
- Com esta entrega, a PO-011 tem todas as fatias (`leads`, `core`,
  `partners`, `core_admin`) entregues e aguardando QA.

**Validação do QA — fatia core_admin:**
- **Rota/tela:** automacoes administrativas (importar prospects, hub de
  automacoes, 4 automacoes de integracao com o IXC, download dos 5
  modelos de planilha, teste de SMTP e de API do IXC, restaurar backup).
- **Cenarios testados:** permissao negada e permitida em cada grupo;
  planilha ausente ou vazia; importacao bloqueada, em andamento e com
  falha ao iniciar; e-mail invalido no teste de SMTP; ZIP malicioso
  (tentativa de gravar arquivo fora da pasta de destino) e escolha de um
  backup fora da pasta esperada no restore.
- **Valores usados:** e-mail invalido, ZIP com entrada
  `../../fora_do_destino.txt`, planilha sem `.sql`, dump `.sql` vazio.
- **Permissoes:** usuario sem o grupo/automacao exigido foi bloqueado nas
  4 automacoes de IXC, nos 4 modelos de planilha vinculados, no restore
  de backup e no hub de automacoes; usuario autorizado acessou normalmente.
- **Regras verificadas:** nenhuma regra de negocio nova (a fatia so move
  codigo de lugar); mensagens, redirecionamentos e formato de auditoria
  permaneceram os mesmos de antes da extracao.
- **Problema:** nenhum impeditivo. Observacao registrada a parte (nao
  reprova esta entrega, pois e anterior a ela): a resolucao de um backup
  escolhido no servidor compara o caminho por prefixo de texto em vez de
  usar a mesma checagem de diretorio já aplicada na extracao do ZIP;
  hoje o campo do formulario so aceita backups realmente listados, mas
  vale reforcar essa validacao.
- **Resultado:** aprovado.

Dependencia recomendada: apos PO-032 (ciclos de importacao, concluida), para
nao mexer na mesma view duas vezes — `apps/core/views.py` estava em ambas.

Objetivo:
Estender aos demais apps o padrao de camada de servicos ja aplicado em
`apps/backoffice` (PO-023, concluida): `models · views finas · services/ ·
management/commands/`. Reduz o acoplamento entre tela web, resposta JSON e
integracao que hoje concentra regra de negocio nas views.

Contexto (achado em 2026-07-29, reforca o objetivo original desta PO):
Levantamento de linhas por view encontrou `apps/leads/views.py` (1952
linhas), `apps/core/views.py` (1660), `apps/core_admin/views.py` (1633),
`apps/partners/views.py` (1603). `apps/backoffice` e hoje o unico app com
`services.py` (451 linhas, PO-023).

Criterios de aceite:
- cada app (`leads`, `core`, `core_admin`, `partners`) ganha um `services.py`
  ou pacote `services/`, com a regra de negocio hoje misturada na view movida
  para la;
- views passam a apenas: validar requisicao HTTP, chamar o servico, devolver
  resposta;
- pode ser fatiado por app — nao precisa ser uma entrega unica; documentar no
  checklist da feature qual fatia foi entregue;
- comportamento observavel preservado (mesmas mensagens, mesmos redirects,
  mesmo formato de auditoria).

Verificacao de regressao obrigatoria (Dev):
- para cada app fatiado, rodar a suite de testes existente antes e depois, e
  criar testes de view (`self.client.post`) para os fluxos que hoje nao tem
  cobertura no nivel HTTP — mesmo padrao usado em PO-023.

Regras relacionadas: nenhuma nova.

Decisao arquitetural: `docs/adr/ADR-005_MONOLITO_MODULAR_EM_CAMADAS.md`;
`docs/ARCHITECTURE.md` ("Estado atual x alvo").

Tipo de feature: `backend-only` (QA obrigatorio).

Agente recomendado para executar:
- `dev`, fatiado app a app.

### PO-030 - Remover arquivos fora de padrao versionados na raiz do repositorio

Status: `Concluída`

Validação do QA — re-revisao (2026-08-03):
- Apontamento da reprovacao anterior conferido pontualmente (sem reabrir a
  auditoria completa, ja feita na revisao original): `git ls-files
  historicos_anexos/` reexecutado de forma independente — retorna vazio.
- Confirmado que os 2 arquivos continuam presentes em disco, com o mesmo
  tamanho de antes (12162 bytes cada) — a correcao removeu do indice, nao
  do disco.
- `git diff --cached --stat -- historicos_anexos/` confirma que so esses 2
  arquivos foram afetados pela correcao, nenhum efeito colateral.
- `manage.py check` reexecutado: limpo.
- **Resultado:** aprovado. Os demais itens ja haviam sido confirmados na
  revisao anterior e nao foram reabertos.

Correcao do Dev (2026-08-03):
- Reprovacao do QA: `historicos_anexos/2026/03/input.xlsx` e
  `input_LG4drf5.xlsx` continuavam rastreados pelo git (`git rm --cached`
  da entrega original nao estava refletido no indice atual).
- Reexecutado `git rm --cached` para os 2 arquivos; confirmado que
  `git ls-files historicos_anexos/` fica vazio e que os 2 arquivos
  continuam presentes em disco (12162 bytes cada, inalterados).

Entrega do Dev (2026-07-29):
- Movidos os 4 scripts de infraestrutura para `ops/`; ajustadas as 3 chamadas
  em `Dockerfile`/`docker-compose*.yml` que apontavam para `setup_speed.py`.
- Removidos do git `_checar_ixc_hoje.py`, `_testar_cadastro.py` e `.tmp_ziptest/`
  (scripts de debug ad hoc, sem uso fora do proprio arquivo).
- `uritemplate.py` investigado e **mantido**: e o shim usado pelo DRF para gerar
  o schema OpenAPI (pacote real nao esta no `requirements.txt`).
- `historicos_anexos/*.xlsx` tirados do controle de versao via `git rm --cached`
  (mantidos em disco).
- Corrigida a entrada `infor DEV.txt/` no `.gitignore` (barra final removida).
- `AGENTS.md` resolvido pelo Orquestrador (2026-07-29): o unico ponto ainda
  valido e nao coberto pelo `CLAUDE.md` (padrao de evitar tabelas grandes em
  documentos longos) foi incorporado ao `CLAUDE.md` secao 8; o restante
  (roteiro de 12 agentes, orcamento de uso por agente) e legado, conflitante
  com o modelo atual de 4 agentes, e foi removido (`git rm AGENTS.md`).

Objetivo:
Remover do controle de versao arquivos que nao sao codigo-fonte mantido e que
se acumularam na raiz do repositorio, encontrados na auditoria de organizacao
de 2026-07-29 (a pedido do usuario, antes do inicio do Modulo 2).

Contexto:
Levantamento direto do repositorio (`git ls-files` + inspecao da raiz)
encontrou os seguintes itens ja rastreados pelo git, fora de qualquer pasta de
codigo (`apps/`, `scripts/`, `docs/`):

- `.tmp_prod_apply.sh`, `.tmp_prod_fastvalidate.sh`: scripts com nome de
  "temporario" versionados permanentemente;
- `.tmp_ziptest/tmp/banco.sql`: dump de banco versionado dentro de uma pasta de
  teste temporaria;
- `_checar_ixc_hoje.py`, `_testar_cadastro.py`: scripts de debug ad hoc na
  raiz (o segundo ja e citado como "fora do codebase mantido" em PO-024);
- `migrar_credenciais_mysql_legado.sql`, `setup_speed.py`: scripts pontuais de
  setup/migracao sem pasta propria;
- `uritemplate.py`: arquivo de 137 bytes na raiz, aparenta ser um shim manual
  da biblioteca `uritemplate` — precisa de investigacao (buscar quem importa
  esse arquivo) antes de decidir remover ou substituir pela dependencia real
  em `requirements.txt`;
- `AGENTS.md`: constituicao legada de um fluxo de agentes anterior (referencia
  "Codex"), hoje duplicada/conflitante com `CLAUDE.md` + `.claude/agents/`;
  decidir entre arquivar, mesclar o que ainda for valido em `CLAUDE.md`, ou
  remover;
- `historicos_anexos/2026/03/input.xlsx` e `input_LG4drf5.xlsx`: **ja
  rastreados no git** mesmo com `historicos_anexos/` no `.gitignore` — foram
  commitados antes da regra existir; precisam sair do controle de versao via
  `git rm --cached` (mantendo os arquivos localmente), sem depender de reescrita
  de historico nesta fase;
- `.gitignore`: a entrada `infor DEV.txt/` tem barra final e por isso nao
  corresponde ao arquivo real `infor DEV.txt` (sem barra) — regra hoje
  inefetiva; corrigir a entrada ou remover o arquivo, o que for decidido.

Criterios de aceite:
- cada item acima resolvido (removido do controle de versao, movido para uma
  pasta apropriada, ou justificado como necessario e documentado);
- nenhuma referencia quebrada apos a remocao (busca ampla por imports de
  `uritemplate` antes de decidir seu destino);
- `python manage.py check` e a suite de testes existentes sem regressao;
- `.gitignore` corrigido onde a regra estiver com problema de padrao.

Regras relacionadas: nenhuma.

Tipo de feature: `backend-only` (QA obrigatorio, focado em ausencia de
referencia quebrada — nao ha regra de negocio envolvida).

Agente recomendado para executar:
- `dev` (para o `git rm --cached`/remocao de arquivos e verificacao de
  imports); coordenar com `devops` apenas se algum dos scripts estiver referenciado
  em `docker-compose.yml` ou pipeline (nao identificado neste levantamento).

### PO-029 - Mover o app `clientes` para dentro de `apps/`

Status: `Concluída`

Validação do QA (2026-07-30):
- Codigo migrado para `apps/clientes/` via `git mv`; nenhuma referencia antiga
  a `clientes.*` restante no codigo versionado (raiz `clientes/` sem arquivos
  rastreados).
- `INSTALLED_APPS`, `config/urls.py` e `apps/clientes/apps.py` apontam para
  `apps.clientes`; `manage.py check` e `makemigrations --check --dry-run` sem
  alteracoes pendentes.
- Suite dos apps que dependem de `Cliente`/`Endereco` (`clientes`, `partners`,
  `leads`, `integracoes_api`) executada contra o MySQL real: 120 testes, 0
  falhas.
- Rota `buscar_cep` confirmada: CEP com formato invalido retorna 400 antes de
  qualquer chamada externa.
- `docs/ARCHITECTURE.md` ja cita o caminho novo `apps/clientes/admin.py` nas
  duas ocorrencias relevantes.
- **Problema:** nenhum.
- **Resultado:** aprovado.

Entrega do Dev (2026-07-29):
- Codigo movido via `git mv` para `apps/clientes/` (historico preservado);
  `INSTALLED_APPS`, `config/urls.py` e `apps/clientes/apps.py` atualizados
  para `apps.clientes` (app_label continua `clientes`, sem migration nova).
- Todos os imports diretos de `clientes.*` (apps de dominio, scripts de
  integracao e os dois `.tmp_prod_*.sh` versionados) convertidos para
  `apps.clientes.*`; nenhuma referencia antiga restante no codigo versionado.
- `manage.py check` sem erro; `makemigrations --check --dry-run` sem migration
  nova.
- Suite completa executada num MySQL local: 115 testes, 113 passaram, mesmas
  2 falhas pre-existentes da entrega da PO-031 (dependencia ausente no
  ambiente e teste de dado de automacao) — nenhuma regressao introduzida.
- Verificado manualmente via test client: `/clientes/` (200), rota de
  `buscar_cep` com CEP invalido (400) e o changelist do admin de auditoria
  que consome `apps.clientes.sync_utils` (200); o changelist de
  `clientes/admin.py` ja estava desregistrado do admin antes desta PO
  (comportamento pre-existente, nao alterado aqui).

Dependencia: PO-031 (namespace unico) deve estar concluida antes desta fatia,
para que `apps.clientes` ja nasca no padrao certo em vez de precisar de dois
ajustes de import em sequencia.

Objetivo:
Corrigir a ultima inconsistencia estrutural entre apps de dominio: `clientes`
(`Cliente`, `Endereco`, `HistoricoSincronizacao`, `ClienteExcluido`) reside em
`clientes/`, na raiz do repositorio, enquanto todos os demais apps de dominio
(`core`, `core_admin`, `auditoria`, `backoffice`, `leads`, `partners`,
`integracoes_api`) residem em `apps/`. Alinhar `clientes` a essa convencao
antes do primeiro app do Modulo 2 ser criado, para que a nova expansao nao
tenha uma referencia inconsistente logo no inicio.

Contexto:
Achado na auditoria de organizacao do repositorio de 2026-07-29 (a pedido do
usuario, antes do inicio do Modulo 2). E divergencia antiga — existe desde o
commit inicial do projeto, nao e uma regressao recente. A ADR-006 exige que o
Modulo 2 siga "a mesma convencao de app Django ja usada por `core`,
`backoffice`, `partners`" sob `apps/modulo2/<setor>/`; a inconsistencia do
`clientes` fora de `apps/` era a excecao que quebrava essa referencia.

Criterios de aceite:
- codigo do app passa a residir em `apps/clientes/` (preferencialmente via
  `git mv`, preservando historico);
- `INSTALLED_APPS` e todos os pontos de import atualizados; nenhuma referencia
  antiga a `clientes.*` (fora de `apps.clientes.*`) restante no codigo
  versionado;
- migrations preservadas e aplicaveis sem re-gerar historico (mesmo app label
  Django, `clientes`);
- testes existentes do app preservados e passando; suite completa sem
  regressao;
- `docs/ARCHITECTURE.md` atualizado para remover a nota de divergencia e
  corrigir o caminho de `clientes/admin.py` citado na secao de integracoes IXC.

Verificacao de regressao obrigatoria (Dev):
- testar manualmente os 6 botoes de disparo manual duplicados em
  `clientes/admin.py` e `apps/auditoria/admin.py` (ver diagrama `07`) — sao os
  pontos mais expostos a um import quebrado nessa mudanca;
- testar a rota de consulta de CEP (`buscar_cep`) apos a mudanca de caminho.

Regras relacionadas: nenhuma nova.

Tipo de feature: `backend-only` (QA obrigatorio).

Agente recomendado para executar:
- `dev`

## Infraestrutura e DevOps

### PO-077 - DevOps: gate contra deploy com migration pendente (processo formal ou CI/CD)

Status: `Concluida` (abordagem "a" escolhida pelo usuario — regra de
processo manual documentada; nenhum codigo, pipeline ou automacao criado)

**Validacao tecnica (Orquestrador, 2026-08-13 — sem QA: tipo `devops`,
mudanca documental/de processo, sem logica de aplicacao):**
- Decisao do usuario, com as palavras exatas: "coloque uma regra no
  [processo de] deploy: sempre que entrar no servidor e fizer pull, tem que
  rodar o comando para atualizar as migrations" — escolheu a abordagem (a)
  (processo formal, sem automacao), descartando (b)/(c).
- Confirmado que `docs/devops/TROUBLESHOOTING.md` foi atualizado (secao
  "Decisao do usuario (2026-08-13) — regra manual obrigatoria, sem CI/CD
  por agora"): registra a regra (rebuild + recreate do `speed_web` via
  `docker compose build/up -d`, seguido de `docker exec speed_sistema
  python manage.py migrate` explicito) e deixa (b)/(c) disponiveis para o
  futuro, sem apagar as alternativas descartadas.
- `deploy_servidor` (arquivo local de acesso ao servidor, nao versionado,
  ja listado no `.gitignore`) recebeu a mesma regra, segundo o relato do
  DevOps — **nao lido pelo Orquestrador nesta validacao**, por conter
  acesso a servidor real (CLAUDE.md secao 6); a validacao se apoiou no
  arquivo publico equivalente (`TROUBLESHOOTING.md`), que documenta a
  mesma regra sem dado sensivel.
- Nenhum arquivo de codigo, `.github/workflows/`, script de deploy ou
  migration foi criado — coerente com a abordagem (a) escolhida.
- **Resultado:** aprovado. Regra registrada nos dois lugares esperados; sem
  risco funcional (nao altera comportamento da aplicacao). A eficacia
  pratica da regra (se o proximo deploy real vai segui-la) e uma questao
  operacional continua, fora do que uma PO de documentacao consegue
  garantir — nao e reaberta por isso, a menos que uma 3a ocorrencia do
  mesmo incidente aconteca.

Origem: 2a ocorrencia do mesmo incidente em 48h — erro 500 em producao por
migration nao aplicada (PO-072, 2026-08-12; PO-076, 2026-08-13), corrigido
nas duas vezes com `manage.py migrate` manual pelo Dev, sem alteracao de
codigo. Investigacao do DevOps (`docs/devops/TROUBLESHOOTING.md`, secao
"Erro 500 apos deploy: migration pendente (RECORRENTE)") apontou como causa
mais provavel deploys feitos via hot-patch direto no container em execucao
(`docker cp`/`docker exec`), que pulam a salvaguarda ja existente no
entrypoint (`ops/setup_speed.py`, que roda `migrate` automaticamente quando
o deploy passa por `docker compose up -d --build`). Nao confirmado ao vivo
(sem acesso SSH no ambiente de investigacao). A lacuna "nao existe pipeline
de CI/CD nem script de deploy formal" ja estava registrada como decisao
pendente em `docs/devops/CONTAINERS.md` antes deste PO.

Abordagens apresentadas ao usuario (registro do que foi decidido e do que
foi descartado, para nao serem rediscutidas sem motivo novo):
- **(a) processo formal, sem automacao [ESCOLHIDA]:** exigir que todo
  deploy siga `docker compose build speed_web && docker compose up -d
  speed_web` (reaproveita a salvaguarda ja existente no entrypoint) e,
  como segunda camada, sempre seguir com `docker exec speed_sistema python
  manage.py migrate` explicito antes de considerar o deploy concluido —
  sem codigo/pipeline novo, so disciplina de operacao;
- **(b) gate automatizado [nao escolhida por agora]:** criar pipeline de
  CI/CD (`.github/workflows/`) e/ou script de deploy (`scripts/deploy_*.sh`)
  que roda `manage.py migrate --check` (ou equivalente) antes do restart,
  bloqueando o deploy se houver migration pendente — exige acesso SSH a
  servidor real e secrets no GitHub, permanece disponivel em
  `docs/devops/CONTAINERS.md` se o usuario quiser priorizar automacao no
  futuro;
- **(c) combinacao [nao escolhida por agora]:** adotar (a) como pratica
  imediata e avaliar (b) depois, se a recorrencia continuar — superada pela
  escolha direta de (a) como decisao final por ora.

Criterios de aceite (atendidos):
- regra de deploy (rebuild+recreate seguido de `migrate` explicito)
  documentada em `deploy_servidor` (acesso ao servidor) e em
  `docs/devops/TROUBLESHOOTING.md` (registro publico do projeto);
- nenhum codigo, pipeline ou script de automacao criado, coerente com a
  abordagem (a);
- alternativas (b)/(c) preservadas na documentacao, nao apagadas, para
  decisao futura se a recorrencia continuar.

Regras relacionadas: nenhuma (processo de deploy/infraestrutura, nao regra
de negocio).

Decisao arquitetural: nenhuma ADR criada — decisao de processo manual, sem
automacao/infraestrutura nova (confirmado com o usuario que isso nao
justifica ADR).

Evidencia: `docs/devops/TROUBLESHOOTING.md` (secao "Decisao do usuario
(2026-08-13) — regra manual obrigatoria, sem CI/CD por agora");
`docs/devops/CONTAINERS.md` (pendencia de pipeline de CI/CD, mantida como
opcao futura); `deploy_servidor` (arquivo local, nao versionado — nao lido
pelo Orquestrador, ver Validacao tecnica acima).

Tipo de feature: `devops` (validacao tecnica; sem impacto em regra de
negocio ou codigo funcional da aplicacao — nao gerou QA).

Agente recomendado para executar:
- decisao de abordagem: usuario (decidiu (a)); implementacao: `devops`
  (concluida).
