# Troubleshooting - GerenciadorProvedoresSpeed
_Ultima atualizacao: 2026-08-13_

## Erro 500 apos deploy: migration pendente (RECORRENTE)

### Ocorrencia confirmada em 2026-08-13 (PO-076) — segunda vez em 2 dias

Relato do usuario: sistema com erro 500 logo depois de uma implementacao
nova (PO-076 — campos de Velocidade Minima/Kit Inicial/TARGET EACE em
`Escola`). O Dev investigou e reproduziu a causa antes de corrigir (sem
habilitar `DEBUG=True`):

```
django.db.utils.OperationalError: (1054, "Unknown column
'escolas_escola.velocidade_dl_minima' in 'field list'")
```

O codigo estava correto; as migrations `escolas.0020` e `escolas.0021`
simplesmente nao tinham sido aplicadas no banco real (`speed_mysql`) usado
pelo container `speed_sistema`. Corrigido rodando `python manage.py migrate
escolas` direto no container — sem alteracao de codigo.

Isso e a **mesma causa raiz** registrada um dia antes na PO-072
(2026-08-12, `docs/BACKLOG.md`): "Migracao aplicada no `speed_sistema`/
`speed_mysql` apos confirmacao do usuario (que reportou erro 500 causado
pela migracao pendente)". Duas ocorrencias em 48h caracterizam padrao, nao
incidente isolado.

### Por que a migration fica pendente mesmo existindo uma salvaguarda

O entrypoint do container (`ops/setup_speed.py`, chamado pelo `command:` do
servico `speed_web` no `docker-compose.yml`) ja faz duas coisas a cada
start do container: valida se existe model sem migration gerada
(`validar_repositorio_e_migrations`) e roda `call_command("migrate")`
automaticamente, antes do Gunicorn subir. Ou seja, **se o deploy sempre
passar por rebuild da imagem + reinicio do container via
`docker compose up -d --build speed_web`, a migration pendente nao deveria
acontecer.**

O repositorio tinha (ja removidos, ver `git status`) os scripts
`ops/.tmp_prod_apply.sh` e `ops/.tmp_prod_fastvalidate.sh`, que usavam
`docker cp` + `docker exec` para aplicar arquivo `.py` isolado direto no
container **em execucao**, sem rebuild e sem reiniciar o container — esse
caminho **pula completamente** o `ops/setup_speed.py` e, portanto, o
`migrate` automatico. Esse padrao de hot-patch e o suspeito mais provavel
para as duas recorrencias, mas nao foi confirmado ao vivo no servidor
(sem acesso SSH nesta sessao).

### Decisao do usuario (2026-08-13) — regra manual obrigatoria, sem CI/CD por agora

Registrada na PO-077 (`docs/BACKLOG.md`) como abordagem (a): sem
automacao/pipeline por agora. Regra obrigatoria de deploy documentada em
`deploy_servidor` (arquivo local, nao versionado): toda atualizacao via
`git pull` no servidor deve ser seguida de rebuild + recreate do container
(`docker compose build speed_web && docker compose up -d speed_web`) e,
como segunda camada de seguranca, de um `docker exec speed_sistema python
manage.py migrate` explicito antes de considerar o deploy concluido.

Automatizar isso de fato num pipeline de CI/CD (ex.: `manage.py migrate
--check` bloqueando o deploy) continua sem existir neste projeto e exige
acesso SSH a um servidor real — segue como abordagem (b)/(c) da PO-077,
disponivel se o usuario decidir priorizar no futuro.

## Disco cheio no servidor 202 (192.168.90.202)

### Confirmado no servidor em 2026-08-10

Nao tenho acesso SSH direto ao servidor neste ambiente; o diagnostico foi
feito a partir do codigo/config e depois confirmado ao vivo com comandos
somente-leitura rodados pelo usuario (`df -h`, `du -sh`, `docker images`,
`docker ps -a`, `docker system df`):

- disco em **95% de uso (5,0 GB livres)** antes da limpeza;
- `media/backups/` sozinho tinha **44 GB** — zero limpeza desde sempre,
  confirmando a causa raiz abaixo;
- `docker ps -a --filter status=exited` veio **vazio** — os 31 containers
  do host sao todos ativos, nao ha container parado acumulado;
- os 19,71 GB "reclaimable" do `docker system df` sao de **outros projetos**
  que rodam no mesmo host compartilhado (`tvti-*`, `omada-*`, `phpipam`,
  `nginx-proxy-manager`, `sitesdominios-monitor-sites`,
  `salasdereuniao-painel-salas`, `redes-noc-dashboard`, `orquestrador-*`,
  etc.) — nao pertence ao GerenciadorProvedoresSpeed, entao nao mexi
  nisso; e decisao de quem administra esse host, nao deste projeto.
- apos apagar os ZIPs de `media/backups/` com mais de 10 dias (mesma janela
  de `BACKUP_RETENTION_DAYS`), disco caiu para **48% de uso (49 GB
  livres)**.

Ou seja: **a causa era 100% o nosso sistema** (backup diario sem retencao
local), nao as outras aplicacoes do host.

### Causa raiz identificada: backup diario sem limpeza local

`speed_backup` (perfil `backup` do `docker-compose.yml`) roda
`ops/backup_manual.py` todo dia as 00h. Esse script:

1. gera um dump completo do MySQL;
2. compacta o dump + todo o conteudo de `media/` (exceto
   `backups/`, `temp_google/`, `importacoes_leads/`) num ZIP;
3. grava esse ZIP em `media/backups/backup_speed_<data>.zip`;
4. **so entao**, se `BACKUP_WINDOWS_SUBDIR` estiver configurado e o
   compartilhamento CIFS montado, copia esse ZIP para `/mnt/windows/` e
   aplica retencao (`BACKUP_RETENTION_DAYS`, padrao 10 dias) — **apenas no
   destino Windows**.

A copia local em `media/backups/` nunca tinha limpeza. Como `media/` e um
bind mount (`./media:/app/media`) direto no disco do host, cada execucao
diaria deixava um ZIP novo (banco completo + media completo) parado ali
para sempre. Esse e o candidato mais provavel para o disco cheio — cresce
de forma garantida e sem limite, um arquivo grande por dia, agravado pelos
anexos que RE/RI passaram a permitir (PO-054/RN-029).

**Corrigido**: `ops/backup_manual.py` agora aplica a mesma retencao
(`BACKUP_RETENTION_DAYS`, padrao 10 dias) tambem na copia local de
`media/backups/`, reaproveitando a logica que ja existia para o destino
Windows (funcao `_remover_backups_expirados`, usada nos dois lugares).

### Causa contribuinte: logs de container sem limite

Nenhum servico do `docker-compose.yml` tinha limite de log configurado. O
driver padrao do Docker (`json-file`) nao tem teto de tamanho a menos que
seja configurado explicitamente, e o `speed_web` roda o Gunicorn com
`--log-level debug --access-logfile -` (log de toda requisicao, nivel
verboso) com `restart: always` — rodando 24/7 por tempo indefinido, o
arquivo de log do container (`/var/lib/docker/containers/<id>/*-json.log`)
tende a crescer bastante ao longo de semanas/meses.

**Corrigido**: todos os 4 servicos (`speed_db`, `speed_web`,
`speed_sincronizador`, `speed_backup`) ganharam:
```yaml
logging:
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
```
Limite de ~30 MB de log por container (3 arquivos de 10 MB, rotacionado
automaticamente pelo proprio Docker).

### Nao corrigido agora — decisao de quem opera o servidor

- `--log-level debug` no Gunicorn (`docker-compose.yml`, servico
  `speed_web`) deixa o log bem mais verboso que `info`. Nao troquei porque
  pode ter sido ligado de proposito para investigar algo em producao — se
  quiser, e uma troca de uma palavra no `command:` do `speed_web`.
- os 19,71 GB de imagens Docker de outros projetos no mesmo host — fora do
  escopo deste projeto, ver acima.

### Pendente — levar a correcao para o servidor

A correcao de `ops/backup_manual.py` (retencao local) esta neste
repositorio, mas **ainda nao foi implantada no servidor 202**. Sem o
deploy (`git pull` + rebuild da imagem usada por `speed_backup`/
`speed_web`, ja que `ops/` entra na imagem via `COPY . .` do `Dockerfile`),
o backup automatico de hoje as 00h volta a gravar sem limpeza e o
`media/backups/` comeca a crescer de novo (mais devagar, mas sem teto).

### Comandos usados na confirmacao (referencia)

```bash
df -h /
du -sh <PROJECT_DIR>/media/backups
ls -lh <PROJECT_DIR>/media/backups | tail -30
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.CreatedSince}}\t{{.Size}}" | sort -k4 -h -r | head -20
docker ps -a --filter status=exited --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
docker system df
```

Limpeza aplicada (retencao de 10 dias, mesma janela de
`BACKUP_RETENTION_DAYS`):
```bash
find <PROJECT_DIR>/media/backups -name "backup_speed_*.zip" -mtime +10 -delete
```

## Historico
| Data | Ocorrencia | Causa | Correcao |
|---|---|---|---|
| 2026-08-10 | Disco cheio no servidor 202: 95% uso (5,0 GB livres) | Backup diario sem limpeza da copia local (`media/backups/`, 44 GB acumulados); logs de container sem limite | ZIPs com mais de 10 dias apagados no servidor (disco caiu para 48%, 49 GB livres); retencao automatica adicionada em `ops/backup_manual.py`; `logging.max-size`/`max-file` em todos os servicos (`docker-compose.yml`) — **correcao de codigo ainda pendente de deploy no servidor** |
| 2026-08-12 | Erro 500 pos-deploy da PO-072 (campos de endereco em `Escola`) | Migration pendente no `speed_sistema`/`speed_mysql` | `manage.py migrate` aplicado manualmente pelo Dev |
| 2026-08-13 | Erro 500 pos-deploy da PO-076 (Velocidade Minima/Kit Inicial/TARGET EACE em `Escola`) — mesma causa da linha anterior, 2a vez em 48h | Migrations `escolas.0020`/`0021` pendentes; suspeita de deploy via hot-patch (`docker cp`/`docker exec`) que pula o `migrate` automatico do `ops/setup_speed.py` | `manage.py migrate escolas` aplicado manualmente pelo Dev; **gate automatizado ainda nao existe** — ver secao acima |
