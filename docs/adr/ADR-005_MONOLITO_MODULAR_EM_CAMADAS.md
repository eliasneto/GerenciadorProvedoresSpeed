# ADR-005 - Evolucao para monolito modular em camadas

## Status

`Aprovado` — detalhada pela `ADR-007` (2026-07-29), que define a estrutura
alvo de pastas, o namespace unico `apps.*`, o padrao interno de cada app e a
fronteira entre `apps/`, `scripts/` e `ops/`. As decisoes desta ADR
permanecem validas; a ADR-007 diz onde cada coisa mora.

## Contexto

O sistema cresceu alem do que a documentacao arquitetural registra. Hoje o
`docs/ARCHITECTURE.md` descreve apenas tres recortes de infraestrutura (API
publica JWT, menu dinamico e integracao IXC) e nao descreve o dominio nem o
banco de dados, que sao o verdadeiro centro do sistema. Isso fez o primeiro
diagrama de arquitetura parecer um conjunto de ilhas desconexas.

O dominio real, apurado no codigo, e:

- `partners`: `Partner`, `PartnerPlan`, `Proposal` (proposta/cotacao e a entidade
  central), `ProposalMotivoInviavel`;
- `leads`: `LeadEmpresa`, `LeadEndereco`, `Lead` (prospeccao e estruturacao por IA);
- `core`: `User` custom, `RegistroHistorico` (historico generico via ContentType),
  `IntegrationAudit`/`IntegrationAuditItem`, sincronizacao de e-mail de cotacao;
- `core_admin`: modelos de configuracao (`AutomacaoMenu`, `AcessoBancoDados`,
  `ConfiguracaoEmailEnvio`, `TesteConexaoIXC`);
- `auditoria`: modelos proxy de leitura sobre auditoria e historico;
- `backoffice` e `integracoes_api`: sem models, apenas orquestracao (views IXC) e
  API REST.

O que conecta tudo e o banco MySQL (`speed_prod`), a autenticacao/`User` e a
camada de auditoria.

Ao mapear o codigo surgiram problemas estruturais que vao encarecer manutencao e
dificultar o crescimento:

1. logica de integracao vive fora dos apps Django, espalhada em ~25 arquivos em
   `scripts/integracoes/`, misturando codigo de producao com ferramentas
   operacionais (`ixc_explorador.py`, `ixc_faxina.py`, `debug_*`);
2. o acesso ao IXC tem mais de uma implementacao: `ixc_client.py` (`IXCClient`,
   cliente HTTP compartilhado) convive com `ixc_api.py` e `ixc_api_incremental.py`,
   dois scripts de sincronizacao quase identicos que reimplementam o HTTP e
   repetem ~250 linhas de normalizacao;
3. as views concentram HTTP, validacao, regra de negocio, chamada externa,
   geracao de planilha e auditoria (ex.: `apps/backoffice/views.py`), sem uma
   camada de servico/dominio;
4. multiplas integracoes externas (IXC, Active Directory, e-mail de cotacao,
   Google/lastmile, Busca Parceiro, IA) sem um padrao unico de fronteira.

## Decisao

Evoluir o projeto para um `monolito modular em camadas`, mantendo um unico
projeto Django e o banco MySQL, sem adotar microservicos, API Gateway dedicado
ou message broker nesta fase.

A organizacao passa a ser explicitamente em tres camadas, com a auditoria como
barramento transversal de escrita externa:

```
Entrada (views finas + API REST integracoes_api)
        |
Camada de Servicos / Dominio  (regra de negocio; services por app)
        |
   +----+-----------------------------+
 ORM/Banco (dominio)        Camada de Integracao
 Partner/Proposal/Lead      1 adaptador por sistema externo
                            IXCGateway, ADGateway, EmailGateway, GoogleGateway
        |
Auditoria transversal (IntegrationAudit): toda escrita externa e registrada
```

## Decisao detalhada

- toda regra de negocio deve viver na camada de servicos, nao em views, admin ou
  scripts; views e serializers ficam finos (apenas entrada/saida);
- toda comunicacao com um sistema externo deve passar por um unico adaptador
  ("gateway") daquele sistema, com timeout, tratamento de erro, log e registro de
  auditoria padronizados;
- o `IXCClient` e o unico cliente HTTP para o IXC; nenhum outro modulo deve
  reimplementar a comunicacao HTTP com o IXC;
- codigo de integracao de producao deve residir dentro dos apps Django; `scripts/`
  fica reservado a ferramentas operacionais e management commands;
- a auditoria (`IntegrationAudit`/`IntegrationAuditItem`) e o ponto unico de
  registro de escrita externa e nao deve ser contornada;
- a evolucao e incremental e reversivel: aplicada app por app, sem interromper o
  desenvolvimento de features.

O primeiro passo aprovado e a unificacao do acesso ao IXC (ver PO-022).

## Consequencias positivas

- documentacao passa a refletir o dominio e o banco reais;
- ponto unico de entrada por sistema externo reduz risco de divergencia e facilita
  troca de credencial, retry e observabilidade;
- regra de negocio testavel isoladamente das views e da rede;
- reducao de duplicacao (ex.: ~250 linhas repetidas entre os dois sync IXC);
- base preparada para crescer sem exigir reescrita ou nova infraestrutura.

## Consequencias negativas

- exige refatoracao gradual de codigo existente (risco controlado por fazer app a
  app, com QA);
- introduz a convencao de camada de servico, que o time precisa seguir de forma
  consistente;
- a curto prazo convivem o padrao antigo e o novo ate a migracao concluir.

## Alternativas consideradas

### 1. Manter a estrutura atual e apenas documentar

Corrigiria o diagrama, mas nao resolve a duplicacao IXC, o acoplamento nas views
nem a dispersao em `scripts/`. Descartada porque o problema e estrutural, nao
apenas documental.

### 2. Extrair modulos em servicos independentes (rumo a microservicos)

Fronteiras rigidas entre modulos e servicos separaveis no futuro. Descartada
nesta fase por custo desproporcional ao estagio atual (equipe e volume), podendo
ser reavaliada se o crescimento e a divisao de times justificarem.

### 3. Introduzir API Gateway / message broker dedicado

Descartada como over-engineering para um monolito Django/MySQL neste momento; o
"gateway" necessario e uma fronteira de integracao em codigo, nao um componente
de infraestrutura novo.
