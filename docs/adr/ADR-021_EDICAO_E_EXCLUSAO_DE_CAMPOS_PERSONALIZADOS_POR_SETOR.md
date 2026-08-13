# ADR-021 - Edicao e exclusao de Campos personalizados por Setor

## Status

`Aprovado`

## Contexto

ADR-019/RN-031 criaram a tela "Campos" (Administracao) permitindo,
deliberadamente, somente listar e criar — "editar/excluir `Campo` (fase 2)"
ficou registrado como pendencia.

O usuario agora pediu as rotas de editar e excluir para essa tela.
Perguntado sobre o comportamento da exclusao quando o Campo ja tem
`CampoValor` gravados (PO-058), confirmou exigir confirmacao explicita
informando os valores que serao perdidos e excluir em cascata. Perguntado
sobre a edicao do tipo do Campo (ex.: texto -> lista) com valores ja
gravados, confirmou permitir livremente, sem bloqueio nem limpeza
automatica dos valores existentes.

## Decisao

Adicionar rotas de edicao e exclusao para `Campo`, em `apps.core_admin`,
resolvendo a pendencia "fase 2" da ADR-019.

## Decisao detalhada

- `GET/POST /campos/<int:pk>/editar/` (`campo_editar`): reaproveita o
  mesmo form de criacao (RN-031) — nome, tipo, setor_nome e opcoes (quando
  tipo="lista");
- troca de tipo e permitida mesmo havendo `CampoValor` gravados para aquele
  Campo; nenhuma limpeza ou validacao automatica e feita sobre os valores
  ja existentes — valor que ficar incompativel com o novo tipo passa a
  aparecer como esta gravado, sem conversao;
- `POST /campos/<int:pk>/excluir/` (`campo_excluir`): exige confirmacao
  explicita do usuario, informando quantos `CampoValor` serao perdidos;
- confirmada a exclusao, `Campo` e apagado; `CampoValor.campo` ja e
  `on_delete=models.CASCADE` (`apps/escolas/models.py`), entao os valores
  vinculados sao removidos junto, sem exigir migracao nova;
- mesma permissao das demais operacoes da tela (`grupo_Administrador_required`,
  RN-031).

## Consequencias positivas

- fecha a pendencia "fase 2" da ADR-019 sem exigir migracao nova — o
  `CASCADE` ja existia no model `CampoValor`;
- comportamento de exclusao consistente com o resto da tela (mesma
  confirmacao explicita usada em outras exclusoes destrutivas do sistema,
  ex.: ADR-020).

## Consequencias negativas / riscos

- excluir um Campo muito usado apaga todo o historico de valores
  preenchidos (`CampoValor`) sem opcao de recuperacao — mitigado pela
  confirmacao explicita informando a quantidade afetada;
- trocar o tipo de um Campo com valores gravados pode deixar valores
  visualmente incoerentes com o novo tipo (ex.: um valor de lista antigo
  que nao esta mais entre as opcoes atuais) — aceito pelo usuario como
  responsabilidade de quem edita, sem tratamento automatico nesta versao.

## Alternativas consideradas

### Bloquear exclusao de Campo com CampoValor em uso

Rejeitada. Usuario confirmou preferir excluir em cascata (com confirmacao
explicita) em vez de bloquear ou exigir remover os valores manualmente
antes.

### Bloquear troca de tipo quando ja existem CampoValor gravados

Rejeitada. Usuario confirmou permitir a troca livremente, sem bloqueio nem
limpeza automatica dos valores existentes.

## Pendencias

- nenhuma decisao futura conhecida para este escopo (Setor e Processo
  seguem com pendencias proprias, registradas na ADR-014/ADR-020).

## Gatilho de regeneracao

Nenhum diagrama documenta esta tela ainda.
