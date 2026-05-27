# Sprint 002 - Autenticacao da API com JWT e contas tecnicas

## Objetivo da sprint

Proteger a API publica v1 com JWT e impedir acesso anonimo aos endpoints de negocio.

## Origem arquitetural

- [ARCHITECTURE.md](../ARCHITECTURE.md)
- [adr/ADR-001_AUTENTICACAO_API_PUBLICA_JWT_CONTAS_TECNICAS.md](../adr/ADR-001_AUTENTICACAO_API_PUBLICA_JWT_CONTAS_TECNICAS.md)

## Time principal

- `backend_django`

## Apoio recomendado

- `qa_tests`

## Dependencia proposta

Nome:
- `djangorestframework-simplejwt`

Motivo:
- emissao e refresh de JWT com suporte maduro para DRF.

## Itens da sprint

### SP2-001 - Configurar JWT no projeto

Tipo:
infraestrutura de autenticacao

Resultado esperado:
- backend preparado para emitir e validar JWT.

Criterios de aceite:
- dependencia adicionada com justificativa;
- configuracao de JWT criada no settings;
- ambiente local e de testes funcionando.

### SP2-002 - Criar grupo de autorizacao tecnica

Tipo:
seguranca

Resultado esperado:
- grupo `api_integracao_publica` definido como criterio de acesso.

Criterios de aceite:
- validacao de pertencimento ao grupo aplicada na autenticacao/consumo;
- conta fora do grupo nao recebe acesso a API publica.

### SP2-003 - Expor rotas de token

Tipo:
endpoint

Rotas esperadas:
- `POST /api/v1/auth/token/`
- `POST /api/v1/auth/token/refresh/`

Resultado esperado:
- sistema integrador consegue autenticar com conta tecnica.

Criterios de aceite:
- credencial valida retorna token;
- credencial invalida retorna erro padronizado;
- usuario sem grupo tecnico nao recebe token.

### SP2-004 - Proteger endpoints de negocio

Tipo:
endpoint

Escopo:
- `/api/v1/`
- `/api/v1/clientes/`
- `/api/v1/clientes/<id>/`
- `/api/v1/clientes/<cliente_pk>/enderecos/`
- `/api/v1/parceiros/`
- `/api/v1/propostas/`
- `/api/v1/propostas/<id>/`

Criterios de aceite:
- acesso anonimo retorna `401` ou `403`, conforme implementacao padrao adotada;
- acesso com JWT valido retorna sucesso;
- acesso com JWT invalido ou expirado retorna erro padronizado.

### SP2-005 - Restringir Swagger e schema

Tipo:
seguranca/documentacao

Escopo:
- `/api/v1/schema/`
- `/api/v1/swagger/`

Criterios de aceite:
- nao ficam publicos em producao;
- em dev/hml exigem autenticacao interna ou configuracao explicita.

### SP2-006 - Documentar Bearer token no Swagger

Tipo:
documentacao tecnica

Resultado esperado:
- Swagger informa claramente como autenticar usando JWT.

Criterios de aceite:
- esquema de seguranca Bearer aparece no OpenAPI;
- endpoints protegidos refletem exigencia de autenticacao.

### SP2-007 - Criar testes de autenticacao e autorizacao

Tipo:
qualidade

Resultado esperado:
- cenarios de acesso anonimo, autenticado e nao autorizado cobertos por teste.

Criterios de aceite:
- teste para token valido;
- teste para token invalido;
- teste para usuario fora do grupo tecnico;
- teste para endpoint protegido sem token.

## Regras de implementacao

- nao reutilizar sessao web como autenticacao principal da API publica;
- nao permitir emissao de token para qualquer usuario ativo do sistema;
- nao deixar Swagger publico em producao;
- nao alterar regra de negocio dos recursos nesta sprint.

## Modelo operacional de contas tecnicas

Padrao recomendado:

- `svc_<nome_sistema>`
- senha forte
- criacao manual inicial pelo admin
- sem uso humano cotidiano

Exemplos:

- `svc_erp`
- `svc_crm`
- `svc_parceiro_x`

## Configuracao recomendada de tempo de vida

- access token: `30 minutos`
- refresh token: `7 dias`

## Fora de escopo da sprint

- portal de autoatendimento de credenciais;
- permissao por parceiro/tenant;
- escrita de dados na API;
- OAuth2 client credentials;
- rate limiting por consumidor.

## Definition of Done da sprint

- rotas de token entregues;
- endpoints de negocio protegidos;
- Swagger/schema restritos conforme ambiente;
- testes automatizados passando;
- documentacao atualizada.
