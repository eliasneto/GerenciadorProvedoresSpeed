# ADR-020 - Exclusao de Status do catalogo de Processos, por Setor

## Status

`Aprovado`

## Contexto

ADR-014/RN-025 criaram o catalogo hierarquico Processo -> Setor -> Status
(`apps.escolas`), com a tela de gestao em `apps.core_admin` permitindo,
deliberadamente, somente visualizar e criar — "decisao futura: permitir
editar/excluir Setor, Status e Processo" ficou registrada como pendencia.

O usuario agora pediu uma rota para excluir Status dentro de um Setor.
Perguntado sobre o comportamento quando o Status excluido estiver em uso
por algum `RedeExterna`/`RedeInterna`, confirmou permitir a exclusao e
deixar o campo em branco nesses registros — aproveitando que
`RedeExterna.status`/`RedeInterna.status` ja sao `ForeignKey` para
`SetorStatus` com `on_delete=SET_NULL` (ADR-015/RN-026, desenhado desde
entao para suportar exclusao sem quebrar referencias).

## Decisao

Adicionar rota de exclusao para `SetorStatus`, individual e aninhada em
Processo/Setor, em `apps.core_admin`. Setor e Processo permanecem sem
exclusao nesta versao — a pendencia da ADR-014 e resolvida somente para o
nivel de Status.

## Decisao detalhada

- `POST /ferramentas/processos/<processo_pk>/setores/<setor_pk>/status/<status_pk>/excluir/`,
  redireciona de volta ao detalhe do Processo;
- exige confirmacao explicita do usuario antes de excluir (mesma
  convencao de outras exclusoes destrutivas do sistema);
- exclusao nao requer migracao: `RedeExterna.status`/`RedeInterna.status`
  ja sao `SET_NULL` (ADR-015). RE/RI que apontavam para o Status excluido
  ficam com o campo em branco; nenhum RE/RI e apagado;
- mesma permissao da tela de Processos (`grupo_Administrador_required`);
- exclusao de Status nao gera novo `RegistroHistorico` (RN-029) nos RE/RI
  atingidos — e limpeza de catalogo, nao edicao feita pela tela de RE/RI.

## Consequencias positivas

- resolve, para o nivel de Status, a pendencia de exclusao deixada pela
  ADR-014, sem exigir nova migracao (o `SET_NULL` ja existia);
- Setor e Processo continuam com superficie de CRUD reduzida, mantendo o
  risco baixo nesta entrega.

## Consequencias negativas / riscos

- exclusao de um Status em uso limpa o campo `status` de RE/RI vinculados
  sem informar previamente quantos registros seriam afetados — usuario
  avisado, aceitou o risco para esta versao;
- Setor e Processo continuam sem exclusao — erro de cadastro nesses dois
  niveis ainda so se corrige recriando.

## Alternativas consideradas

### Bloquear exclusao quando o Status estiver em uso

Rejeitada. Usuario confirmou preferir permitir a exclusao e deixar o
campo em branco, aproveitando o `SET_NULL` ja existente, em vez de
adicionar uma verificacao de uso e uma tela de bloqueio.

### Estender a exclusao tambem a Setor e Processo nesta mesma entrega

Rejeitada por nao ter sido pedida. O usuario pediu especificamente
exclusao de Status "por setor" — Setor e Processo continuam como
pendencia em aberto da ADR-014.

## Pendencias

- decisao futura: permitir excluir Setor e Processo (pendencia
  remanescente da ADR-014);
- decisao futura: avisar o usuario, antes de confirmar a exclusao,
  quantos RE/RI seriam afetados pela limpeza do Status.

## Gatilho de regeneracao

Nenhum diagrama documenta esta arquitetura ainda.
