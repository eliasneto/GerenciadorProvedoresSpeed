# ADR-019 - Campos personalizados por Setor, em RE e RI

## Status

`Aprovado`

## Contexto

O usuario apontou que o grid de Enderecos Lastmile esta ficando com muita
informacao direto na linha (Setor, Parceiro, Status, Velocidade ofertada).
Pediu um botao que abra um modal com "mais campos", editaveis de acordo
com o Setor dono de cada campo — exemplo dado: o Setor Lastmile tem varios
campos proprios, o Setor Suprimentos tem outros; um Setor pode **ver** os
campos de outro, mas so pode **editar** os proprios. Pediu tambem uma tela
nova, "Campos", na aba Administracao, para cadastrar cada campo (nome,
tipo e Setor dono); quando o tipo for Lista, o cadastro tambem pede as
opcoes validas, digitadas.

Perguntado, o usuario confirmou:

- os valores pertencem a RE e a RI separadamente (mesmo padrao ja usado
  por Setor/Status/Parceiro, RN-023/RN-026/RN-030) — nao a Escola;
- a edicao usa a mesma regra ja aplicada ao Parceiro (RN-030): editavel
  quando a pessoa esta na tela do Setor dono do campo (`setor_atual`),
  sem criar vinculo usuario-Setor (que nao existe hoje, ADR-016);
- no modal, o grupo de campos do Setor da tela atual vem expandido; os
  grupos dos demais Setores vem recolhidos, abrindo so se a pessoa clicar;
- tipos de campo no MVP: Texto curto, Numero, Data, Sim/Nao e Lista (com
  opcoes digitadas no cadastro).

## Decisao

1. Novo model `Campo` (`apps.escolas`, mesmo app de `Processo`/`Setor`/
   `SetorStatus`): `nome`, `tipo` (`texto`, `numero`, `data`, `sim_nao`,
   `lista`), `setor_nome` (dono do campo) e `opcoes` (lista de textos,
   usada somente quando `tipo="lista"`).
2. Novo model `CampoValor`: guarda o valor de um `Campo` para uma
   instancia especifica de `RedeExterna` ou `RedeInterna`, via
   `GenericForeignKey` (mesmo padrao ja usado por `RegistroHistorico`,
   `apps.core.models`) — evita duplicar o model de valor por tipo (RE/RI).
3. Tela nova "Campos" em `apps.core_admin`, secao Administracao, mesmo
   padrao inicial da PO-050 (Processos): nesta primeira versao, so listar
   e criar.
4. No grid de Enderecos Lastmile, a linha expandida de RE/RI ganha um
   botao que abre um modal com os `Campo` cadastrados, agrupados por
   `setor_nome`: o grupo do Setor da tela atual (`setor_atual`) vem
   expandido; os demais, recolhidos. Dentro de cada grupo, so os campos
   cujo `setor_nome` bate com `setor_atual` ficam editaveis — os demais
   sao somente leitura.

## Decisao detalhada

### `Campo.setor_nome` e texto (nome), nao FK para uma linha de `Setor`

`Setor` e cadastrado por Processo (RN-025) — hoje existem duas linhas de
`Setor` chamadas "Suprimentos" (uma do Processo de RE, outra do de RI),
deliberadamente espelhadas para que RE e RI compartilhem o mesmo
vocabulario (ADR-016). Se `Campo` apontasse para uma linha especifica de
`Setor`, seria preciso cadastrar o mesmo campo duas vezes (uma por
Processo) para ele valer nos dois — contrariando a suposicao ja registrada
na ADR-016 de que "Suprimentos" e o mesmo lugar de trabalho independente
do Processo. Por isso `Campo.setor_nome` e um `CharField` (mesmo
vocabulario de `Setor.nome`), comparado diretamente com `setor_atual` —
igual ao que ja acontece na condicao de edicao do Parceiro (RN-030).

### Armazenamento do valor

`CampoValor.valor` e um `JSONField` (guarda o valor ja no tipo nativo
esperado — string, numero, booleano ou data em ISO), no mesmo espirito de
`RedeExterna.dados_adicionais`/`Escola.dados_api` (uso ja aceito no
projeto para dado de formato variavel). A validacao de que o valor bate
com `Campo.tipo` (e, para `lista`, que o valor esta entre `Campo.opcoes`)
e feita na view/form, nao so na UI.

### Nao migra Setor/Status/Parceiro para o modal

Setor, Status (RN-026) e Parceiro (RN-030) continuam exibidos e editaveis
direto na linha do grid, como hoje — nao entram no modal novo. O modal e
para os campos adicionais cadastrados em "Campos" (RN-031). Decisao
tecnica reversivel: se o usuario quiser migrar os campos ja existentes
para dentro do modal tambem, e ajuste aditivo, nao coberto por esta ADR.

### O que NAO muda

- permissao de acesso ao grid inteiro continua `grupo_LastMile_required`
  (ADR-011); a tela "Campos" fica restrita ao grupo `Administrador`, mesmo
  padrao de Processos (PO-050);
- nao ha vinculo usuario-Setor — quem decide o que e editavel continua
  sendo a tela atual (`setor_atual`), nao quem esta logado.

## Consequencias positivas

- grid principal fica mais enxuto — Setor/Status/Parceiro continuam
  visiveis direto, o resto vai para o modal, sob demanda;
- extensivel sem alterar codigo a cada campo novo que um Setor precisar —
  cadastra em "Campos" e aparece no modal;
- reaproveita o padrao ja existente (`setor_atual`) sem exigir vinculo
  usuario-Setor novo.

## Consequencias negativas / riscos

- mais uma tabela generica de valores (`CampoValor`) — carregar todos os
  campos de uma Escola exige cuidado com N+1 (`select_related`/
  `prefetch_related` no `Campo` ao consultar `CampoValor`);
- `JSONField` para o valor exige validacao explicita por tipo na view —
  nao fica garantida so pelo banco;
- duas regras de "por Setor" convivendo no projeto (Setor/Status por
  "pertence ao setor atual", ADR-015; Parceiro e Campo por "tela atual
  bate com o setor dono", ADR-018/esta ADR) — mitigado por documentacao,
  ja que a logica de comparacao e a mesma (`setor_atual`).

## Alternativas consideradas

### `Campo` como FK direto a uma linha de `Setor` (por Processo)

Rejeitada — duplicaria o cadastro do mesmo campo por Processo (RE e RI),
contrariando o agrupamento por nome ja usado na RN-027/ADR-016.

### Editabilidade por Setor do usuario logado (vinculo usuario-Setor)

Rejeitada nesta entrega. O usuario confirmou usar a mesma regra de tela
atual do Parceiro (RN-030), sem criar o vinculo usuario-Setor — que nao
existe hoje e ja aparece como pendencia futura na ADR-016.

### Migrar Setor/Status/Parceiro para dentro do modal novo

Nao foi pedido. Mantidos como estao, para nao misturar esta entrega com o
que ja esta em producao (RN-026/RN-030).

## Pendencias

- ~~editar/excluir `Campo` (fase 2 — nesta versao so lista e cria, mesmo
  padrao inicial da PO-050)~~ — resolvida pela ADR-021 (2026-08-10);
- vinculo usuario-Setor, caso o usuario decida no futuro trocar a regra de
  permissao de "tela atual" para "setor do usuario";
- nenhum diagrama documenta esta tela ainda.

## Gatilho de regeneracao

Nenhum diagrama documenta esta tela ainda.
