# Architecture

## Objetivo

Consolidar as decisoes arquiteturais principais da camada publica de API do projeto.

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
