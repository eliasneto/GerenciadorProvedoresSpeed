# ADR-009 - Integracao com DashboardEACE para Cliente/Endereco (estrutura preparatoria)

## Status

`Aprovado` — **somente para o escopo de scaffolding descrito abaixo**. A
integracao real (endpoint, autenticacao, mapeamento de campos, sincronizacao)
depende do contrato da API que o usuario ainda vai enviar; esta ADR nao
autoriza implementar isso ainda. Ver secao "Pendencias".

> **Emenda (2026-08-07):** o destino dos dados descrito nesta ADR
> ("traduzir a resposta da API externa para os models
> `apps.clientes.Cliente`/`Endereco`") foi superado por decisao do usuario:
> os dados de `/escolas` vao para um model novo e dedicado
> (`apps.escolas.Escola`), sem mapear para `Cliente`/`Endereco`. Ver
> `docs/adr/ADR-010_MODELO_ESCOLA_DEDICADO_DASHBOARD_EACE.md`. O restante
> desta ADR (client HTTP, autenticacao via `X-API-Key`, variaveis de
> ambiente) continua valido e inalterado.

## Contexto

A ADR-008 (2026-08-07) desativou a sincronizacao de `Cliente`/`Endereco` com
o IXC, deixando como pendencia explicita o mecanismo pelo qual o endereco
passaria a entrar no sistema ("importacao manual... mecanismo nao definido
nesta ADR").

Antes de qualquer importacao manual acontecer, o usuario decidiu a fonte
definitiva: um sistema externo chamado **DashboardEACE** vai fornecer os
enderecos/logins via API. O SGP atua como **cliente** dessa API (consome,
nao expoe) — mesmo papel que o SGP já tem hoje em relação ao IXC. O usuário
ainda não enviou os dados técnicos do contrato (endpoint, autenticação,
formato de resposta); pediu para a arquitetura/estrutura ficar pronta desde
já, para que a implementação real seja rápida quando os dados chegarem.

O nome "EACE" já aparece no projeto em dois pontos anteriores a esta ADR:
RN-019 (tarefas de workflow "Realizar Implantação EACE" no IXC) e no
levantamento de 2026-08-07 das escolas do INEP/Conectados — indicando que
este projeto já opera dentro de um programa de conectividade EACE mais
amplo, do qual o DashboardEACE parece ser a peça central de gestão.

## Decisao

Seguir o mesmo padrão arquitetural já estabelecido para integrações
externas (Hub de Integração, ADR-005/ADR-007): criar
`apps/integracoes/dashboard_eace/`, com um gateway HTTP dedicado
(`DashboardEACEClient`, no mesmo espírito do `IXCClient`) e uma camada de
serviços que, futuramente, vai traduzir a resposta da API externa para os
models `apps.clientes.Cliente`/`Endereco`.

## Decisao detalhada

### Autorizado agora (scaffolding)

1. `apps/integracoes/dashboard_eace/__init__.py` e
   `apps/integracoes/dashboard_eace/client.py`, com uma classe
   `DashboardEACEClient` que:
   - lê `base_url` e `token` de variáveis de ambiente
     (`DASHBOARD_EACE_URL`, `DASHBOARD_EACE_TOKEN`) — nomes provisórios,
     ajustáveis sem nova ADR quando o contrato real chegar;
   - expõe `timeout` e `verify_ssl` configuráveis (mesmo padrão do
     `IXCClient`), com um valor padrão razoável (30s, `verify_ssl=True` —
     ao contrário do IXC, que usa `False` por uma razão histórica própria
     já registrada; DashboardEACE não tem esse histórico, então começa
     seguro por padrão);
   - expõe um método genérico de leitura (ex.: `get`/`listar`) usando
     `requests`, com tratamento de timeout/erro de conexão no mesmo
     padrão do `IXCClient.post` — **sem endpoint real chumbado**, porque
     ainda não existe;
   - **não** herda a convenção de query do IXC (`qtype`/`query`/`oper`,
     tudo via POST com header `ixcsoft`) — isso é peculiaridade do IXC,
     documentada como tal; o DashboardEACE é uma API diferente e não deve
     copiar essa forma sem confirmação de que funciona assim.
2. `apps/integracoes/dashboard_eace/services/__init__.py` — pasta pronta
   para receber a função de sincronização quando o contrato chegar; sem
   lógica de negócio ainda.
3. Placeholders de variável de ambiente em `.env.example` e
   `docker-compose.yml` (serviços `speed_web` e `speed_sincronizador`):
   `DASHBOARD_EACE_URL=` e `DASHBOARD_EACE_TOKEN=`, vazios, com comentário
   indicando que são preenchidos quando o contrato da API for definido.
4. Testes que validam apenas a **estrutura** do client (client inicializa
   com variáveis de ambiente, falha de forma clara se `DASHBOARD_EACE_TOKEN`
   não estiver definido, monta headers de autenticação corretamente) — sem
   depender de um endpoint real, no mesmo espírito dos testes existentes
   para módulos de integração.
5. Atualizar `docs/ARCHITECTURE.md` (seção de Integrações e o resumo do
   Hub de Integração) e a pendência da ADR-008, apontando para esta ADR.

### Explicitamente FORA de escopo agora

- endpoint(s) reais e método HTTP a chamar;
- forma real de autenticação (pode não ser Bearer token simples — token
  fixo é só o palpite mais comum para começar, ajustável sem nova ADR);
- mapeamento de campos da resposta da API para `Cliente`/`Endereco`;
- lógica de sincronização (criação, atualização, exclusão) e sua
  disparo (agendado, manual, ou webhook — este último exigiria endpoint
  de entrada no SGP, decisão arquitetural própria se vier a ser o caso);
- qualquer escrita em `Cliente`/`Endereco` baseada em dado desta API.

Nenhum desses pontos deve ser adivinhado. Quando o usuário enviar o
contrato real da API, o Dev implementa com base nele — não antes.

## Consequências positivas

- Quando o contrato real chegar, a implementação é só "encaixar" o
  endpoint e o mapeamento de campos na estrutura já pronta, sem decisão
  arquitetural nova;
- Consistente com o padrão já usado para IXC e Google — reduz a chance de
  inventar um padrão novo por integração.

## Consequências negativas / riscos

- Trabalho de scaffolding pode exigir ajuste quando o contrato real
  chegar (nomes de variável, forma de autenticação, paginação, etc.) —
  aceitável, são decisões técnicas reversíveis;
- Enquanto a integração real não estiver pronta, o projeto continua sem
  fonte automática de `Cliente`/`Endereco` (a pendência da ADR-008
  permanece aberta, agora com destino definido).

## Alternativas consideradas

### Esperar o contrato da API antes de criar qualquer estrutura

Rejeitada. O usuário pediu explicitamente para a estrutura ficar pronta
antes dos dados chegarem, para acelerar a implementação real depois.

### Reaproveitar o `IXCClient` genérico para o DashboardEACE

Rejeitada. `IXCClient` está acoplado à convenção proprietária do IXC
(`qtype`/`query`/`oper`, autenticação Basic com token, SSL desabilitado por
padrão). Misturar duas APIs diferentes na mesma classe aumentaria o risco
de um dos dois usar a convenção errada da outra — o padrão do projeto
(Hub de Integração) já prevê um client por sistema justamente por isso.

## Pendencias

- ~~Usuário vai enviar os dados reais da API do DashboardEACE (endpoint(s),
  autenticação, formato de resposta)~~ — **parcialmente resolvida em
  2026-08-07**: usuário entregou `API_EXTERNA.md` (raiz do projeto), com
  endpoint (`/escolas[/{jira_key}]`), autenticação (`X-API-Key`) e formato
  de erro confirmados; Dev já corrigiu o client e implementou os wrappers
  de leitura. Ainda faltam credenciais reais (`DASHBOARD_EACE_URL`/
  `DASHBOARD_EACE_TOKEN`) para testar contra a API de verdade, e o schema
  completo de `EscolaOut` (ver ADR-010).
- Atualizar a pendência da ADR-008 ("mecanismo de importação manual não
  definido") para referenciar esta ADR como o destino decidido. — feito.
- ~~Quando o mapeamento de campos for definido, avaliar se `RN-017`
  precisa de outro ajuste~~ — **superada**: não há mapeamento de campos
  para `Cliente`/`Endereco` (ver emenda no topo e ADR-010); `RN-017`
  permanece como está até nova decisão.

## Gatilho de regeneracao

Nenhum diagrama documenta esta ADR ainda. Se/quando a integração real for
implementada e o diagrama `07 · Processos de automações e rotinas` for
regenerado, incluir o DashboardEACE como novo processo.
