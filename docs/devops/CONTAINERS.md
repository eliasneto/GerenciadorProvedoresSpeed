# Containers - GerenciadorProvedoresSpeed
_Ultima atualizacao: 2026-07-09_

## Stack identificada (Dockerfile / docker-compose.yml existentes)

- Linguagem: Python 3.12 (`python:3.12-slim`)
- Framework: Django 6.0.2 + Django REST Framework 3.16.1
- Banco de dados: MySQL 8.0
- Servidor de aplicacao: Gunicorn 23.0.0
- Autenticacao: LDAP (django-auth-ldap) opcional via `USE_AD_AUTH`
- Dependencias extras usadas pelas automacoes de integracao: pandas, openpyxl, xlsxwriter, requests, selenium, tqdm

Esta stack foi extraida diretamente do `Dockerfile` e `docker-compose.yml` ja existentes no projeto, que ja estao em uso (nao e um projeto greenfield). `docs/architecture.md` (mantido pelo Orquestrador) documenta apenas a decisao da API publica v1, nao a infraestrutura geral.

## Servicos do docker-compose.yml

| Servico | Papel |
|---|---|
| `speed_db` | MySQL 8.0, dados persistidos em volume `speed_db_data` |
| `speed_web` | Aplicacao Django servida por Gunicorn, porta local `8091:8000` |
| `speed_sincronizador` | Loop continuo que dispara os scripts de integracao IXC em horarios fixos (`ixc_api_incremental.py`, `ixc_api.py`, `ixc_os_comercial_lastmile.py`, `ixc_faxina.py`, `sincronizar_respostas_email_cotacao.py`) |
| `speed_backup` | Roda `backup_manual.py` diariamente as 00h (perfil `backup`, opcional) |

## Testando localmente uma mudanca de codigo

O `Dockerfile` copia o codigo para dentro da imagem (`COPY . /app/`) e o
`docker-compose.yml` so monta `./media`. Ou seja, por padrao, qualquer
mudanca em `.py` ou em templates exige rebuild da imagem:

```bash
docker compose build speed_web
docker compose up -d speed_web
```

Para testar iterativamente sem rebuildar a cada alteracao (por exemplo, a
nova automacao "Resolucao de O.S. do Atendimento" em
`apps/core_admin/views.py` e `scripts/integracoes/backoffice/resolver_os_atendimento_ixc.py`),
foi criado `docker-compose.local.yml`, que monta o codigo do projeto no
container e liga o `--reload` do Gunicorn:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build speed_web
```

Esse arquivo so tem efeito quando chamado explicitamente com `-f` — ele nao
e carregado sozinho, para nao afetar nenhum outro ambiente que use o mesmo
`docker-compose.yml`. Para voltar ao comportamento padrao, basta rodar o
compose sem essa flag.

Apos subir o container, a nova automacao fica em `/ferramentas/importar/`
(link "Automacoes" no menu, secao "Administracao"), card "Resolucao de O.S.
do Atendimento".

## Riscos identificados (nao corrigidos aqui, apenas registrados)

- `requirements.txt` esta salvo em UTF-16 (com BOM), nao UTF-8. O `pip`
  moderno consegue decodificar isso automaticamente, mas e um formato
  fragil: qualquer edicao feita com uma ferramenta que nao preserve o BOM/UTF-16
  (ex.: `>>` no bash, alguns editores) pode corromper o arquivo e quebrar o
  build. Recomendo salvar esse arquivo como UTF-8 na proxima edicao.
- Token de acesso a API do IXC com valor padrao gravado no codigo (ja
  registrado tambem em `docs/BACKLOG.md`, PO-013): `scripts/integracoes/ixc_client.py`,
  `ixc_os_comercial_lastmile.py`, `ixc_faxina.py`, `ixc_primeira_os.py` e
  `scripts/integracoes/backoffice/cria_atendimento_ixc.py` usam
  `os.getenv("IXC_TOKEN", "76:54f35af...")` — se a variavel de ambiente nao
  estiver setada, a aplicacao usa um token real hardcoded como fallback.
  Isso viola a regra de seguranca do projeto (CLAUDE.md, secao 6). Nao
  corrigi porque alterar codigo de aplicacao esta fora do escopo do DevOps;
  fica registrado como risco para o Dev tratar.
- `.env` existe na raiz do projeto e ja esta corretamente listado no
  `.gitignore` (nao versionado). Nao existe `.env.example` no repositorio —
  isso dificulta a configuracao de um ambiente novo do zero, mas nao foi
  criado agora por nao ter sido pedido; posso gerar se for util.

## Fora do escopo desta atualizacao

Nao existe pipeline de CI/CD (`.github/workflows/`) nem script de deploy
(`scripts/deploy_homolog.sh`) neste projeto — o padrao descrito no agente
`devops.md` (GitHub Actions + SSH) nao esta implementado aqui. Esta
atualizacao cobriu somente o ambiente Docker local, conforme solicitado.
Se quiser esse pipeline, e uma decisao separada (arquivo `.github/workflows/homolog.yml`
+ `scripts/deploy_homolog.sh` + secrets no GitHub) e prefiro confirmar com
voce antes de criar, ja que envolve acesso SSH a um servidor real.
