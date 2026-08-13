# ADR-007 - Estrutura alvo do repositorio: namespace unico, camada de integracao e producao dentro dos apps

## Status

`Aprovado` (desenho da arquitetura-alvo; nenhuma execucao autorizada por esta ADR)

## Escopo desta ADR

Esta ADR **desenha o alvo**. Ela nao altera codigo, nao move arquivo, nao
mexe em `docker-compose.yml` e nao cria feature de execucao. Serve como
referencia unica para: (a) onde cada coisa deve morar quando for mexida, e
(b) o padrao que o Modulo 2 (ADR-006) deve seguir desde o primeiro app.

Decisao do usuario em 2026-07-29: "estamos trabalhando apenas com a
arquitetura, documentacao". A ordem, o risco e o momento de cada migracao
ficam para uma decisao posterior.

## Contexto

A ADR-005 aprovou o monolito modular em tres camadas e a ADR-006 detalhou a
expansao para o Modulo 2. Ambas foram aplicadas de forma parcial. Um
levantamento estrutural do repositorio em 2026-07-29 (`git ls-files`,
contagem de imports, leitura de `config/settings.py` e `docker-compose.yml`)
encontrou cinco problemas estruturais, sendo o primeiro inedito na
documentacao:

### 1. Duplo namespace de import (armadilha ativa)

`config/settings.py` linha 34 executa
`sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))`, e o diretorio `apps/`
**nao possui `__init__.py`**. Como consequencia, todo app e importavel por
dois caminhos distintos - `core` e `apps.core` - e o Python trata cada um
como um modulo diferente.

O codigo usa os dois simultaneamente hoje: 76 imports sem prefixo
(`from core.models`, `from clientes.`, `from partners.`) contra 49 com
prefixo (`from apps.core.ixc_client`, `from apps.backoffice.services`).

Nao ha quebra hoje apenas porque os **models** sao sempre importados como
`core.models`, nunca como `apps.core.models`. No momento em que alguem
escrever `from apps.core.models import User`, o modulo de models carrega uma
segunda vez, com uma segunda copia de cada classe, e o registro de models do
Django passa a ter duas entidades para a mesma tabela. E um defeito latente,
nao uma preferencia de estilo.

### 2. Codigo de producao rodando como script solto

Dez scripts em `scripts/integracoes/` fazem bootstrap manual do Django
(`sys.path` na mao + `django.setup()`), e o `docker-compose.yml` invoca seis
deles por caminho de arquivo em rotinas agendadas: `ixc_api_incremental.py`,
`ixc_api.py`, `ixc_os_comercial_lastmile.py`, `ixc_faxina.py`,
`sincronizar_respostas_email_cotacao.py` e `backup_manual.py`. O Django
resolve esse caso nativamente com management commands; o projeto inteiro tem
apenas tres.

### 3. Camada de servicos aplicada em 1 app de 8

`apps/backoffice/services.py` (451 linhas, PO-023) e o unico. As views
seguem concentrando HTTP, regra e integracao: `leads` 1952 linhas, `core`
1660, `core_admin` 1633, `partners` 1603.

### 4. Regra de negocio pesada fora dos apps

`scripts/integracoes/ixc_os_comercial_lastmile.py` (1338 linhas) e
`scripts/integracoes/Lastmile/APIGoogle_BuscaFornecedores.py` (1001 linhas)
concentram regra de dominio fora de qualquer app Django.

### 5. Inconsistencias estruturais ja mapeadas

App `clientes/` na raiz em vez de `apps/clientes/` (PO-029) e 21 arquivos
soltos versionados na raiz, incluindo `.tmp_*.sh`, `_checar_ixc_hoje.py`,
`_testar_cadastro.py` e `uritemplate.py` (PO-030).

## Decisao

### 1. Namespace unico: `apps.*`

`apps/` passa a ser um pacote Python de verdade (`apps/__init__.py`), o
`sys.path.insert` de `config/settings.py` e removido, e `INSTALLED_APPS`
passa a listar `apps.core`, `apps.clientes`, etc. Todo import de app usa
exclusivamente o prefixo `apps.`.

Nota tecnica que torna essa mudanca segura: o Django deriva o `app_label` do
ultimo componente do caminho, entao `apps.core` mantem o label `core`. Nomes
de tabela (`core_user`, etc.) e o historico de migrations permanecem
inalterados - nao ha migration de renomeacao envolvida.

### 2. Estrutura alvo do repositorio

```text
manage.py
config/                     settings, urls, wsgi, asgi
apps/
  __init__.py               pacote real - habilita o namespace unico
  core/                     User, RegistroHistorico, IntegrationAudit,
                            middleware, templatetags
  clientes/                 Cliente, Endereco, HistoricoSincronizacao
  leads/                    LeadEmpresa, LeadEndereco, Lead
  partners/                 Partner, PartnerPlan, Proposal
  backoffice/               automacoes operacionais (sem models)
  core_admin/               configuracao (AutomacaoMenu, etc.)
  auditoria/                proxies de leitura sobre auditoria/historico
  integracoes_api/          API publica v1 (JWT)
  integracoes/              camada de integracao unificada
    ixc/                    client.py + services/
    google/                 lastmile, busca parceiro
    email/                  cotacao (IMAP/SMTP)
    ad/                     Active Directory / LDAP
    correios/               consulta de CEP
  modulo2/<setor>/          expansao futura (ADR-006)
docs/                       documentacao, ADRs, diagramas
ops/                        infraestrutura: backup, setup, deploy
scripts/                    SOMENTE ferramentas de desenvolvimento
```

### 3. Padrao interno de cada app

```text
apps/<app>/
  models.py                 dominio persistido
  views.py                  fina: HTTP, mensagem, redirect - sem regra
  services/                 toda a regra de negocio do app
  forms.py  urls.py  admin.py
  management/commands/      entrypoints de rotina agendada
  tests/                    espelha os modulos do app
```

Regra derivada da ADR-005, agora explicita: **view nao chama integracao
diretamente**. O caminho e sempre `view -> service -> gateway`.

### 4. Camada de integracao: pacote unico com uma subpasta por sistema

Todos os gateways vivem em `apps/integracoes/`, um subpacote por sistema
externo. Cada subpacote e independente: expoe sua propria classe, com
timeout, tratamento de erro e log proprios.

Decisao explicita, confirmada com o usuario em 2026-07-29: **nao existe
Manager, Registry, `BaseProvider` ou despacho dinamico por nome**. Cada
servico importa diretamente o gateway de que precisa
(`from apps.integracoes.ixc.client import IXCClient`). Isso mantem a
decisao do item 10 da ADR-006 - o agrupamento aqui e organizacao de pastas,
nao uma camada de indirecao.

A subpasta existe para separar responsabilidades dentro de cada sistema
(client HTTP separado dos servicos de integracao), nao para permitir troca
dinamica de provider.

### 5. `scripts/` deixa de conter codigo de producao

Fronteira: se roda em producao (rotina agendada, automacao chamada pela
aplicacao), pertence a um app - como service, e com management command
quando for rotina agendada. Se e ferramenta de investigacao/manutencao
manual de desenvolvedor (`ixc_explorador.py`, `debug_*`), permanece em
`scripts/`. Se e infraestrutura (`backup_manual.py`, `setup_speed.py`,
`.tmp_prod_*.sh`), vai para `ops/`.

Management command e o alvo para as seis rotinas agendadas de hoje, porque
elimina os dez bootstraps manuais de Django e o hack de `sys.path`
duplicado em cada script. **Nao decidido nesta ADR:** quando e como migrar,
por exigir alteracao de `docker-compose.yml` e janela de validacao das
rotinas de producao (escopo DevOps).

### 6. Mapa de destino (referencia, sem prazo)

| Hoje | Alvo |
|---|---|
| `clientes/` (raiz) | `apps/clientes/` |
| `apps/core/ixc_client.py` | `apps/integracoes/ixc/client.py` |
| `apps/core/ad_sync.py` | `apps/integracoes/ad/` |
| `scripts/integracoes/ixc_sync_clientes.py` | `apps/integracoes/ixc/services/` |
| `scripts/integracoes/ixc_finalizacao_service.py`, `ixc_ticket_arquivo_service.py` | `apps/integracoes/ixc/services/` |
| `scripts/integracoes/ixc_api.py`, `ixc_api_incremental.py` | `apps/clientes/management/commands/` |
| `scripts/integracoes/ixc_os_comercial_lastmile.py`, `ixc_finalizar_os_lastmile.py`, `ixc_primeira_os.py` | regra em `apps/leads/services/`, acesso em `apps/integracoes/ixc/`, disparo em management command |
| `scripts/integracoes/Lastmile/APIGoogle_BuscaFornecedores.py` | `apps/integracoes/google/` + `apps/leads/services/` |
| `scripts/automacoes/API_BuscaParceiro/buscaParceiro.py` | `apps/integracoes/google/` + `apps/partners/services/` |
| `scripts/integracoes/sincronizar_respostas_email_cotacao.py` | `apps/integracoes/email/` + management command |
| `scripts/integracoes/ixc_faxina.py` | management command do app dono |
| `scripts/integracoes/importar_leads_planilha.py` | `apps/leads/management/commands/` |
| `apps/backoffice/integracoes_ixc/*.py` | `apps/backoffice/services/` (regra), consumindo `apps/integracoes/ixc/` |
| `clientes/views.py::buscar_cep` | `apps/integracoes/correios/` |
| `scripts/integracoes/backup_manual.py`, `setup_speed.py`, `.tmp_prod_*.sh` | `ops/` |
| `scripts/integracoes/ixc_explorador.py`, `debug_primeira_os_ixc.py` | permanecem em `scripts/` (ferramenta de dev) |
| `_checar_ixc_hoje.py`, `_testar_cadastro.py`, `uritemplate.py`, `.tmp_ziptest/` | fora do controle de versao (PO-030) |

### 7. Ordem de camada entre os apps (emenda de 2026-07-29)

Emenda registrada no mesmo dia da aprovacao original, apos o levantamento do
grafo de dependencias feito para o diagrama `03 · Modulos e dependencias`.

**Motivo da emenda:** a versao original desta ADR definia onde o codigo mora,
mas nao definia quem pode depender de quem. Pasta organizada sem regra de
dependencia nao impede ciclo — e o levantamento provou isso: **cinco ciclos de
importacao envolvendo seis dos oito apps**, todos em nivel de modulo:

- `core` <-> `core_admin`, `core` <-> `leads`, `core` <-> `partners`
  (os tres nascem de `apps/core/views.py`, linhas 27-29, onde o app base
  importa de apps de dominio e de configuracao);
- `core_admin` <-> `backoffice`;
- `core_admin` -> `auditoria` -> `backoffice` -> `core_admin`.

A `ADR-006` item 3 ja havia estabelecido dependencia em uma via so, mas apenas
para o futuro Modulo 2. Esta emenda **generaliza a mesma regra para os apps
atuais**, em vez de criar uma terceira ADR sobre o mesmo assunto.

**Decisao:** os apps passam a ter ordem de camada explicita. Um app pode
importar de camada estritamente inferior; **nunca de camada superior**.

| Camada | Apps | Pode importar de |
|---|---|---|
| 0 — base tecnica | `core`, `integracoes/*` | nada (fora bibliotecas) |
| 1 — dominio | `clientes`, `partners`, `leads` | camada 0 |
| 2 — aplicacao | `backoffice`, `core_admin`, `auditoria` | camadas 0 e 1 |
| 3 — entrada | `integracoes_api` | camadas 0, 1 e 2 |
| 4 — expansao | `modulo2/<setor>` | camadas 0 a 3 (ja era a regra da ADR-006) |

Dependencia entre apps da **mesma camada** e excecao, nao padrao: so vale se
estiver listada aqui. Excecao aprovada nesta emenda: `leads` -> `partners`
(o lead alimenta a proposta; e um fluxo real de dominio, nao acoplamento
acidental).

Consequencia direta da tabela: `apps/core/views.py` linhas 27-29 passam a ser
violacao explicita — `core` e camada 0 e nao pode importar de `leads`,
`partners` nem `core_admin`. Fica registrado como divergencia conhecida; a
correcao nao esta autorizada por esta ADR (ver escopo no topo).

**Aplicacao da regra**, na mesma linha do item 3 da ADR-006: verificacao
manual em code review nesta fase; se o numero de apps crescer a ponto de
tornar isso arriscado, avaliar `import-linter` no CI com o DevOps — a tabela
acima ja esta no formato que essa ferramenta consome.

**Confirmado pelo usuario em 2026-07-29:** a ordem de camada acima passa a
valer como criterio de reprovacao em code review. A aplicacao da correcao
(eliminar os cinco ciclos listados e alinhar os apps a ordem de camada) e o
escopo da PO-032 em `docs/BACKLOG.md`.

### 8. Ownership de registros e models compartilhados entre camadas iguais (emenda de 2026-07-29, PO-036)

Levantamento feito para a PO-032 encontrou dois pontos onde um app grava dado
"de auditoria" que na verdade pertence a outro app, e um registro de
configuracao usado por dois apps da mesma camada — os tres geravam ciclo de
importacao mesmo depois da correcao da PO-032. Decisao, para os tres casos:

- **`apps/core_admin/automacoes_registry.py` + model `AutomacaoMenu`** (hoje
  em `core_admin`, consumido tambem por `backoffice`) migram para `apps/core`
  (camada 0). E um registro de configuracao/permissao transversal, mesma
  natureza do `IntegrationAudit` que ja mora la;
- **`apps/backoffice/integracoes_ixc/*.py`** (funcoes de execucao das
  automacoes IXC) tambem migram para `apps/core`, como posicionamento
  intermediario — confirmado por levantamento que esse pacote nao depende de
  nada proprio de `backoffice`, apenas de `apps.core.ixc_client` (ja camada
  0). O destino final continua sendo `apps/integracoes/ixc/services/`
  (item 4 desta ADR), quando a PO-033 rodar; mover para `apps/core` agora
  evita mexer no mesmo codigo duas vezes antes da PO-033 estar destravada
  (ela depende da aprovacao de QA da PO-026, ainda pendente);
- **`RestoreBackupAuditoria`** (hoje em `auditoria`, unico escritor
  `core_admin`) e **`CotacaoStatusAuditoria`** (hoje em `auditoria`, unico
  escritor `partners`) migram para `apps/core`, seguindo o mesmo precedente
  do `IntegrationAudit` — convencao unica para "model de auditoria escrito
  por outro app", em vez de decidir caso a caso.

Com as tres mudancas, `core_admin` e `backoffice` deixam de se importar
mutuamente (cada um passa a importar so de `apps/core`, camada 0), e
`auditoria`/`partners` deixam de gravar em model hospedado um no outro —
nenhuma excecao de dependencia de mesma camada precisou ser criada alem da
ja aprovada (`leads -> partners`).

Adicionalmente, a **action de disparo manual duplicada** em
`apps/auditoria/admin.py` (`processar_planilha_desativacao`, copia da mesma
automacao ja disparada por `core_admin`) e removida — autorizado pelo
usuario em 2026-07-29. `core_admin` passa a ser o unico ponto de disparo
manual dessa automacao especifica (ja tem controle de permissao via
`automacoes_registry`).

Consequencia para `apps/core`: o app acumula, alem de `User`,
`RegistroHistorico`, `IntegrationAudit`, middleware e templatetags, agora
tambem `AutomacaoMenu`, os tres models de auditoria realocados e o pacote
`integracoes_ixc` (temporario). Risco assumido conscientemente — mitigado
porque o pacote de integracao sai de novo quando a PO-033 rodar, mantendo
`apps/core` como camada 0 (nada especifico de dominio ou de UI).

Migration necessaria: mover model entre apps preservando dado (state move,
sem recriar tabela) para `AutomacaoMenu`, `RestoreBackupAuditoria` e
`CotacaoStatusAuditoria`. `integracoes_ixc` nao tem model, so funcoes —
sem migration.

## Consequencias positivas

- elimina o defeito latente de duplo carregamento de models antes que o
  Modulo 2 amplie a superficie de risco;
- o Modulo 2 nasce com uma referencia estrutural correta, em vez de copiar
  as excecoes atuais (`clientes/` na raiz, producao em `scripts/`);
- toda integracao passa a ter um lugar previsivel, incluindo as que hoje nao
  tem gateway (Correios/CEP);
- rotina agendada deixa de depender de bootstrap manual e passa a ser
  testavel como qualquer codigo do app;
- `scripts/` volta a significar uma coisa so (ferramenta de dev), tornando
  obvio o que e producao.

## Consequencias negativas / riscos

- a unificacao de namespace toca 125 imports e o `settings.py`; e mecanica,
  mas ampla - exige varredura completa e QA de regressao;
- migrar as rotinas agendadas para management commands exige alterar
  `docker-compose.yml` e validar cron em producao (DevOps), com risco
  operacional real - por isso nao foi decidido aqui;
- ate a migracao concluir, convivem o padrao antigo e o novo, como ja
  aconteceu na ADR-005;
- `apps/integracoes/` cria um app Django sem models; e intencional (pacote
  de fronteira), mas exige disciplina para nao virar deposito de codigo
  orfao.

## Alternativas consideradas

### 1. Manter os dois namespaces e apenas padronizar por convencao

Descartada: convencao nao impede o defeito. Basta um `from apps.core.models
import ...` para quebrar o registro de models, e nada no projeto detecta
isso hoje.

### 2. Achatar tudo para o namespace curto (`core`, `clientes`) e remover `apps/`

Funcionaria e seria valida, mas coloca oito apps de dominio na raiz junto com
`config/`, `docs/`, `scripts/` e `ops/` - piora exatamente a poluicao de raiz
que motivou esta ADR. O prefixo `apps.` tambem torna imediato distinguir
codigo do projeto de biblioteca de terceiro na leitura de um import.

### 3. Um app Django separado por sistema externo (`apps/ixc/`, `apps/google/`)

Descartada: espalha cinco apps sem models pelo mesmo nivel dos apps de
dominio, sem ganho sobre o subpacote. O agrupamento em `apps/integracoes/`
comunica melhor que aquilo e uma fronteira, nao um dominio.

### 4. Integration Hub generico (Manager + Registry)

Ja descartada no item 10 da ADR-006 e reconfirmada com o usuario em
2026-07-29. Ver `docs/diagrams/integration-hub-conceitual.html` para o
desenho exploratorio do que foi descartado.

## Impacto nas features ja registradas

Nenhuma feature precisa ser descontinuada - todas as POs de arquitetura
abertas convergem para este alvo:

- **PO-026** (`ixc_client.py` para dentro de um app, aguardando QA): passo
  intermediario valido. O destino final passa a ser
  `apps/integracoes/ixc/client.py` em vez de `apps/core/ixc_client.py`;
- **PO-029** (mover `clientes/` para `apps/`): continua valida, e parte
  desta estrutura;
- **PO-030** (limpar a raiz): continua valida, com o acrescimo de que
  `backup_manual.py` e `setup_speed.py` tem destino definido (`ops/`);
- **PO-024** (concluida, moveu os 8 modulos do Backoffice): alinhada; o
  refinamento futuro e virar `services/` consumindo `apps/integracoes/ixc/`;
- **PO-032** (quebrou 3 dos 5 ciclos de importacao): os 2 ciclos restantes e a
  divergencia de ownership de auditoria viram a **PO-036**, conforme item 8
  desta ADR;
- **ADR-006**: o Modulo 2 permanece em `apps/modulo2/<setor>/`, agora sob o
  namespace unico e o padrao interno de app desta ADR.

## Pendencias

- ~~confirmacao da ordem de camada do item 7~~ — confirmada pelo usuario em
  2026-07-29; correcao em andamento na PO-032;
- ordem, risco e momento de cada migracao (decisao do usuario, quando quiser
  sair do desenho para a execucao);
- se e quando migrar as rotinas agendadas para management commands - exige
  coordenacao com DevOps por causa do `docker-compose.yml`;
- nenhuma feature de execucao foi criada em `docs/BACKLOG.md` por esta ADR,
  deliberadamente.
