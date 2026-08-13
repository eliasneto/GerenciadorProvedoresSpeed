# API Externa — Guia de Integração

> Documento para entregar ao time/sistema que vai **consumir** o banco do
> EACE Jira Dashboard. Detalhes de arquitetura e schema completo do banco
> estão em `ARQUITETURA_BANCO_DE_DADOS.md` §7 — este arquivo é o resumo
> prático para quem só precisa integrar, não manter o dashboard.

## 1. Onde bate

| Ambiente | Base URL |
|---|---|
| Local (docker compose, sem nginx) | `http://localhost:8000/api/v1` |
| Via nginx (compose completo) | `http://<host>/api/v1` (porta 80) |
| Servidor EACE | **a confirmar** — hoje o app só está acessível na rede interna (IP privado, nginx sem HTTPS). Se o sistema consumidor está fora dessa rede, é preciso VPN ou abrir/expor com TLS antes — isso ainda não está feito. |

⚠️ **Não há HTTPS configurado ainda.** Se a chamada vai sair da rede local/VPN,
resolver isso antes de mandar a API key de verdade por aí — hoje ela viaja
em texto puro.

## 2. Autenticação

Toda rota exige o header:

```
X-API-Key: <chave>
```

- A chave é única e fixa (sem múltiplos clientes/revogação individual nesta
  versão), configurada via variável de ambiente `EXTERNAL_API_KEY` no
  servidor que roda o dashboard.
- **Sem header ou header errado → `401`.** Se `EXTERNAL_API_KEY` não estiver
  configurada no servidor → `503` (API desligada), independente da chave
  enviada.
- Gere uma chave forte antes de entregar (nunca reaproveite o placeholder de
  dev):
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- **O que entregar ao outro dev**: só a chave em si (fora deste canal —
  Slack/1Password/etc., não em texto plano num chat/ticket) + o nome do
  header (`X-API-Key`). Nenhuma outra credencial é necessária.

## 3. Documentação viva (fonte da verdade)

- Swagger: `<base>/../docs` (ex.: `http://localhost:8000/docs`)
- ReDoc: `<base>/../redoc`
- OpenAPI JSON: `<base>/../openapi.json`

Essas páginas **não exigem** `X-API-Key` para exibir o schema (só as
chamadas de dado exigem) — pode mandar o link direto pro outro dev, sempre
vai estar sincronizado com o código (schemas Pydantic geram o schema
automaticamente, não é mantido à mão).

## 4. Endpoints

### 4.1 Escolas (somente leitura)

```
GET /escolas                       # lista; filtros opcionais: ?uf=SP&status_escola=Conectado
GET /escolas/{jira_key}            # ex.: /escolas/EACE-123 -> 404 se não existir
```

Cada item traz status de conexão, localização, técnico (kit wifi, solução,
velocidade) e financeiro já calculado (faturamento, custo RE/RI, valor de
kit) — é a mesma visão de `/dashboard`/`/mapa`. Ver `EscolaOut` no
`/docs` para a lista completa de campos.

### 4.2 Financeiro (leitura + escrita)

3 recursos, mesmo padrão CRUD:

```
GET  /financeiro/custo-rede-externa
GET  /financeiro/custo-rede-externa/{inep_code}
POST /financeiro/custo-rede-externa          # cria; 409 se o INEP já existe
PUT  /financeiro/custo-rede-externa/{inep_code}   # cria OU substitui (idempotente)

GET/POST/PUT  /financeiro/custo-rede-interna[/{inep_code}]
GET/POST/PUT  /financeiro/valor-kit[/{descricao}]
```

Exemplo `PUT /financeiro/custo-rede-externa/12345678`:
```json
{
  "valor_assinatura_mensal": 350.00,
  "custo_instalacao": 1200.00,
  "fibra_km": 3.5
}
```
`POST /financeiro/custo-rede-externa` é igual, mas o body inclui `inep_code`.

`custo-rede-interna` usa `valor_equipamentos`, `valor_servicos`,
`valor_manutencao_mensal`. `valor-kit` usa `categoria` (`"RE"`/`"RI"`),
`valor_servicos`, `valor_equipamentos`, chaveado por `descricao` (texto livre,
ex.: `"Kit Cobertura Wi-Fi - 2 Access Points"` — precisa URL-encode nos
requests com espaço).

**Importante**: só estas 3 tabelas aceitam escrita. Não existe rota de
escrita para escolas/issues (domínio sincronizado do Jira a cada 30min —
qualquer alteração deve ser feita no Jira, não aqui) nem para
sprints/métricas (recalculadas do zero a cada ciclo).

### 4.3 Sprints e métricas (somente leitura)

```
GET /sprints
GET /sprints/active
GET /sprints/{id}
GET /sprints/{id}/cards
GET /metricas/lead-time
GET /metricas/cycle-time
GET /metricas/time-in-status
GET /metricas/velocity?sprint_id=123      # sprint_id opcional
GET /metricas/burndown?sprint_id=123      # sprint_id opcional
```

## 5. Erros

Todo erro vem como `{"detail": "..."}` (ou lista de erros de validação no
formato padrão do FastAPI/Pydantic para `422`).

| Status | Significado |
|---|---|
| `401` | `X-API-Key` ausente ou incorreta |
| `503` | API desligada no servidor (`EXTERNAL_API_KEY` não configurada) |
| `404` | recurso não encontrado (ex.: INEP, jira_key ou sprint inexistente) |
| `409` | `POST` tentando criar uma chave que já existe — usar `PUT` |
| `422` | corpo da requisição inválido (campo faltando, valor negativo, tipo errado) |

## 6. O que NÃO existe (por enquanto)

- Rate limiting / throttling.
- Múltiplas chaves / clientes com revogação individual.
- HTTPS.
- Paginação nas rotas de listagem (`/escolas`, `/financeiro/*`, `/metricas/*`
  retornam tudo de uma vez — volumes atuais são baixos, mas se crescer muito
  isso precisa ser revisto).
- Webhooks/push — é só request/response, o consumidor tem que fazer polling
  se precisar saber de mudanças.
