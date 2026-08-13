# ADR-008 - Desativacao temporaria da sincronizacao de Cliente/Endereco com o IXC

## Status

`Aprovado`

> **Emenda (2026-08-07):** a pendencia original desta ADR ("mecanismo de
> importacao manual de enderecos nao foi definido") foi resolvida pelo
> usuario no mesmo dia: em vez de importacao manual, os enderecos vao ser
> recebidos via API de um novo sistema externo, o DashboardEACE. Ver
> `docs/adr/ADR-009_INTEGRACAO_DASHBOARD_EACE_ESTRUTURA_PREPARATORIA.md`.
> O restante desta ADR (desativacao das 4 rotinas do IXC) continua valido
> e inalterado.

## Contexto

Hoje todo o dominio `Cliente`/`Endereco` (app `clientes`) e populado e mantido
por quatro rotinas agendadas que conversam com o IXC (ver
`docs/ARCHITECTURE.md`, secao "Catalogo de automacoes e rotinas"):

- `ixc_carga_total` — carga completa diaria (23h) de cliente/login;
- `ixc_sincronizacao_incremental` — sincronizacao incremental a cada 4h;
- `ixc_os_comercial_lastmile` — atualizacao diaria (03h) do setor/O.S. atual
  de cada login no setor Comercial | Lastmile;
- `ixc_faxina` — faxina diaria (22h) de dados do IXC (marca `ClienteExcluido`
  e limpeza correlata).

O usuario decidiu que, para o uso atual deste projeto, os enderecos vao ser
importados manualmente em vez de sincronizados automaticamente do IXC. A
integracao pode voltar a ser usada no futuro, entao o codigo nao deve ser
apagado — apenas desativado (comentado).

Levantamento feito antes da decisao: `ixc_os_comercial_lastmile` alimenta
campos (`em_os_comercial_lastmile`, `os_atual_aberta`, `ticket_os_atual_ixc`,
`setor_os_atual_nome`) consumidos pelo fluxo de cotacao em `apps/leads` e
`apps/partners` (RN-017/RN-018). Apresentada a opcao de manter so essa rotina
ativa (por já não criar endereço novo, apenas enriquecer os existentes), o
usuario confirmou desligar as quatro rotinas mesmo assim.

## Decisao

Desativar as quatro rotinas de sincronizacao de Cliente/Endereco com o IXC
(`ixc_carga_total`, `ixc_sincronizacao_incremental`,
`ixc_os_comercial_lastmile`, `ixc_faxina`), comentando os pontos de disparo,
sem apagar nenhum código. O cadastro de `Cliente`/`Endereco` passa a ser
manual (fora do escopo desta ADR — nao inclui construir uma nova tela de
importacao).

## Decisao detalhada

### O que comentar (Dev)

Pontos de disparo, não a lógica interna dos comandos:

1. `docker-compose.yml`, servico `speed_sincronizador`: comentar os 4 blocos
   `if` que chamam `ixc_sincronizacao_incremental`, `ixc_carga_total`,
   `ixc_os_comercial_lastmile` e `ixc_faxina` dentro do loop `while true`.
   Deixar uma linha de comentário explicando que estão desativados por esta
   ADR e como reativar.
2. `apps/clientes/admin.py` e `apps/auditoria/admin.py` (botões duplicados,
   ver `docs/ARCHITECTURE.md` "Ressalvas conhecidas"): comentar os `path(...)`
   e os métodos `btn_rodar_carga_total`, `btn_rodar_incremental`,
   `btn_rodar_faxina`, `btn_rodar_os_comercial_lastmile` (e
   `btn_parar_os_comercial_lastmile`, que só faz sentido com a rotina ativa).
   Não remover os botões não relacionados
   (`btn_rodar_backup`, `btn_rodar_respostas_email_cotacao`).

### O que NÃO muda

- os management commands (`apps/clientes/management/commands/ixc_*.py`) e os
  scripts equivalentes em `scripts/integracoes/` permanecem intactos e
  executáveis manualmente via `python manage.py <comando>`, para quem
  precisar rodar uma sincronização pontual durante a transição;
- os dados já sincronizados (`Cliente`/`Endereco` existentes) não são
  apagados nem alterados por esta ADR;
- as automações de escrita no IXC (Backoffice: resolução de O.S.,
  desativação de atendimento, cadastro de cliente, edição de login/
  atendimento etc.) não são afetadas — elas conversam com o IXC em tempo
  real, não dependem da sincronização de `Endereco` e continuam ativas;
- `sincronizar_respostas_email_cotacao.py` (IMAP) e `backup_manual.py` não
  são rotinas do IXC e não são afetadas.

### Documentação a atualizar (Orquestrador, junto desta ADR)

- `docs/ARCHITECTURE.md`: marcar as 4 rotinas como desativadas na tabela de
  "Catalogo de automacoes e rotinas", com ponteiro para esta ADR;
- `docs/business_rules.md`, RN-017: o critério "endereço vem do IXC pelas
  rotinas de sincronização" deixa de ser verdade enquanto esta ADR estiver
  em vigor — critério atualizado para refletir a importação manual.

## Consequências positivas

- Reversível: reativar é descomentar os mesmos pontos, sem precisar
  reescrever nada;
- Nenhum dado existente é perdido;
- Reduz chamadas automáticas ao IXC durante o período em que os endereços
  passam a ser mantidos manualmente.

## Consequências negativas / riscos

- `apps/leads` e `apps/partners` deixam de receber atualização automática de
  qual login está em "Comercial | Lastmile" e se tem O.S. aberta
  (`em_os_comercial_lastmile`, `os_atual_aberta`) — essa informação passa a
  refletir o último estado sincronizado antes da desativação, podendo ficar
  desatualizada. Risco aceito explicitamente pelo usuário ao confirmar
  desligar as 4 rotinas.
- Novos clientes/endereços não aparecem mais automaticamente no sistema;
  dependem inteiramente da importação manual (mecanismo de importação não
  definido nesta ADR).
- `ClienteExcluido` (faxina) para de ser atualizado — clientes removidos do
  IXC não serão mais detectados automaticamente.

## Alternativas consideradas

### Desativar só as rotinas que criam Cliente/Endereco novo (carga_total e incremental), mantendo lastmile e faxina

Apresentada ao usuário como opção recomendada, para preservar o dado usado
pelo fluxo de cotação. Não escolhida — usuário confirmou desligar as 4
mesmo sabendo do impacto em `apps/leads`/`apps/partners`.

### Remover o código das rotinas em vez de comentar

Rejeitada. Usuário indicou explicitamente que a integração pode ser reativada
no futuro; remover exigiria recuperar do histórico do Git e reconstruir o
ponto de disparo.

## Pendências

- ~~Mecanismo de importação manual de endereços (planilha, admin padrão do
  Django, ou outro) não foi definido nesta ADR~~ — **resolvida em
  2026-08-07**: não será importação manual, e sim integração via API com o
  DashboardEACE. Ver emenda no topo desta ADR e `ADR-009`.
- Nenhum teste automatizado cobre hoje "rotina desativada continua
  executável manualmente" — Dev deve confirmar que `python manage.py
  ixc_carga_total` (etc.) ainda funciona após comentar somente o disparo
  agendado/admin. (Confirmado manualmente pelo Dev na entrega de PO-044,
  via `--help` nos 4 comandos; sem teste automatizado dedicado.)

## Gatilho de regeneração

Nenhum diagrama documenta esta ADR diretamente hoje. Se o diagrama
`07 · Processos de automacoes e rotinas` for regenerado, marcar estas 4
rotinas como desativadas.
