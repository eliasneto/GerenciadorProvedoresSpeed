# ADR-014 - Catalogo de Processos (Setor/Status) para RE e RI

## Status

`Aprovado`

> **Emenda (2026-08-07):** a pendencia "se/quando `RedeExterna.setor`/
> `status` passam a ser `ForeignKey`" foi resolvida pela ADR-015 — os dois
> campos passam a ser FK para `Setor`/`SetorStatus`, editaveis direto no
> grid de Enderecos Lastmile.

> **Emenda (2026-08-10):** a pendencia "permitir editar/excluir Setor,
> Status e Processo" foi parcialmente resolvida pela ADR-020 — Status
> agora pode ser excluido, por Setor. Setor e Processo continuam sem
> exclusao/edicao.

## Contexto

ADR-012/RN-023 criaram `RedeExterna`/`RedeInterna` com `setor` e `status`
como texto livre, deliberadamente sem vocabulario fixo ("Vocabulario de
setor e status ainda nao e uma lista fixa — quando o usuario definir,
migrar de texto livre para `choices=`"). O usuario agora pediu uma tela
nova, "Processos", onde ele mesmo cadastra: um Processo (com nome), quais
Setores fazem parte dele, e quais Status fazem parte de cada Setor. A tela
fica na aba "Administracao" (secao real do sidebar, visivel so para o
grupo `Administrador` — hoje contem Automacoes, Teste SMTP e Restaurar
Backup, todas em `apps.core_admin`). Confirmado: nesse primeiro momento, so
visualizar e criar — sem editar nem excluir.

Perguntado se o Processo precisa de um campo `tipo` (RE ou RI), o usuario
respondeu que nao: o Processo e generico; **cada atividade de RE e RI
deve ser vinculada ao processo**, e pediu que essa integracao entre
`RedeExterna`/`RedeInterna` e o novo catalogo fosse feita diretamente por
quem implementa, ja que a distincao RE/RI ja existe na estrutura (dois
models separados, ADR-012). Tambem pediu para semear, so para teste, os
Setores "Lastmile, Suprimentos, Implantacao, Pos venda, Suporte" em dois
Processos (um para RE, um para RI), com Status genericos.

## Decisao

Criar um catalogo hierarquico `Processo` → `Setor` → `SetorStatus` em
`apps.escolas` (mesmo app de `Escola`/`RedeExterna`/`RedeInterna`), e
adicionar um vinculo (`ForeignKey` opcional) de `RedeExterna` e
`RedeInterna` para `Processo`. Tela de gestao (listar + criar, sem editar
nem excluir) em `apps.core_admin`, na secao "Administracao" do sidebar.

## Decisao detalhada

### Hierarquia do catalogo

- `Processo`: `nome` (`CharField`, unico). Sem campo `tipo` — decisao
  explicita do usuario: o mesmo Processo nao se marca como RE ou RI: quem
  determina isso e o model que aponta para ele (`RedeExterna` ou
  `RedeInterna`);
- `Setor`: `nome` (`CharField`), `processo` (`ForeignKey` para `Processo`,
  `on_delete=CASCADE`, `related_name="setores"`), unico por
  `(processo, nome)`;
- `SetorStatus`: `nome` (`CharField`), `setor` (`ForeignKey` para `Setor`,
  `on_delete=CASCADE`, `related_name="status_opcoes"`), unico por
  `(setor, nome)`.

Nomes em portugues (`Processo`/`Setor`/`SetorStatus`), consistente com os
demais models deste mesmo arquivo (`Escola`, `RedeExterna`,
`RedeInterna`) — introduzir nomes em ingles so para estes 3 quebraria a
convencao ja em uso no proprio arquivo.

### Vinculo com RedeExterna/RedeInterna

`RedeExterna.processo` e `RedeInterna.processo`:
`ForeignKey("escolas.Processo", null=True, blank=True,
on_delete=models.SET_NULL)`. Opcional (`null=True`) porque `RedeExterna`/
`RedeInterna` ja existem hoje sem processo definido, e a criacao de um RE/
RI nao deve ficar bloqueada esperando um Processo cadastrado.

**Fora de escopo desta ADR**: `RedeExterna.setor`/`RedeExterna.status`
(hoje `CharField` livre, ADR-012) **nao** se tornam `ForeignKey` para
`Setor`/`SetorStatus` agora. Vincular a *instancia* de RE/RI ao Processo
(catalogo) e um passo; fazer o texto livre de setor/status respeitar
exatamente as opcoes daquele Processo e outro — nao foi pedido e mudaria
o formato de dado ja em uso. Registrado como pendencia.

### Tela (`apps.core_admin`, secao Administracao)

Somente listar e criar (usuario confirmou nao precisar editar/excluir por
agora):

- `GET/POST /ferramentas/processos/` — lista todos os Processos (nome,
  quantidade de setores) e formulario de criacao (so nome);
- `GET/POST /ferramentas/processos/<id>/` — detalhe: setores do processo,
  status de cada setor, formulario para adicionar um novo setor (so
  nome);
- `POST /ferramentas/processos/<id>/setores/<setor_id>/status/` —
  adiciona um novo status aquele setor (so nome), redireciona de volta
  para o detalhe;
- acesso restrito ao grupo `Administrador` (`grupo_Administrador_required`,
  mesmo padrao de "Teste SMTP"/"Restaurar Backup");
- novo item no sidebar, dentro da secao "Administracao" existente.

### Dados de teste (semeados por migration)

A pedido do usuario, semear via `migrations.RunPython` (nao management
command — e parte do rollout desta feature, nao uma rotina recorrente):

- 2 Processos: "Rede Externa (RE)" e "Rede Interna (RI)";
- em cada um, os mesmos 5 Setores: Lastmile, Suprimentos, Implantacao,
  Pos venda, Suporte;
- em cada Setor, os mesmos 3 Status genericos: A fazer, Em andamento,
  Concluido.

Dado explicitamente marcado pelo usuario como "so pra gente testar" — nao
e vocabulario definitivo, pode ser ajustado/expandido depois pela propria
tela (criar mais Setores/Status) sem nova ADR.

## Consequencias positivas

- Resolve a pendencia de vocabulario de setor/status deixada em ADR-012,
  sem inventar uma lista fixa via `choices=` — o proprio usuario cadastra
  e evolui o catalogo pela tela;
- RE e RI continuam independentes (cada um com seu proprio `Processo`
  vinculado, podendo ser o mesmo ou diferente);
- escopo de CRUD reduzido (sem editar/excluir) diminui superficie de teste
  nesta primeira entrega.

## Consequencias negativas / riscos

- sem editar/excluir, um erro de digitacao no nome de um Setor/Status so
  se corrige recriando ou, futuramente, com uma feature de edicao — usuario
  avisado, aceitou o risco para esta primeira versao;
- `RedeExterna.setor`/`status` (texto livre) ainda podem divergir do que
  esta cadastrado no `Processo` vinculado, pois nao ha validacao cruzada
  nesta ADR — registrado como pendencia, nao bug.

## Alternativas consideradas

### Processo com campo tipo (RE/RI)

Rejeitada. Usuario decidiu explicitamente que o Processo e generico e que
a distincao fica a cargo do vinculo (`RedeExterna`/`RedeInterna` apontando
pra ele), nao de um campo no proprio Processo.

### Setor/Status como catalogo global (compartilhado entre Processos, N:N)

Rejeitada. O pedido foi "quais setores vao fazer parte **desse** processo"
e "quais status faz parte de **cada** setor" — leitura mais direta e cada
Processo ter sua propria lista de Setores, e cada Setor sua propria lista
de Status, sem compartilhamento entre Processos diferentes.

## Pendencias

- Decisao futura: se/quando `RedeExterna.setor`/`status` passam a ser
  `ForeignKey` para `Setor`/`SetorStatus` do `Processo` vinculado (em vez
  de texto livre);
- decisao futura: permitir editar/excluir Setor, Status e Processo;
- vocabulario semeado (Lastmile/Suprimentos/Implantacao/Pos
  venda/Suporte + A fazer/Em andamento/Concluido) e apenas para teste —
  usuario pode ajustar livremente pela propria tela.

## Gatilho de regeneracao

Nenhum diagrama documenta esta arquitetura ainda.
