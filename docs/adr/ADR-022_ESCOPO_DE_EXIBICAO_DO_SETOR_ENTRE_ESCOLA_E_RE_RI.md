# ADR-022 - Escopo de exibicao do Setor entre Escola e RE/RI

## Status

`Substituida por ADR-023`

> **Correcao (2026-08-10):** esta ADR partiu de um entendimento errado do
> pedido do usuario (Setor reaproveitando o catalogo de Processos, escopo
> exclusivo Escola OU RE/RI, valor por instancia via `CampoValor`). Depois
> de ver a tela construida, o usuario corrigiu: Setor informativo
> independente do catalogo de Processos, escopo nao exclusivo (Escola, RE
> e RI podem ser marcados juntos), valor fixo (nao por escola) e sempre
> somente leitura. Ver ADR-023 para o desenho correto; esta ADR fica
> mantida so para historico de como o requisito foi mal interpretado
> inicialmente.

> Esta ADR desenha a decisao de arquitetura. Nao autoriza inicio de execucao —
> a PO-062 (`docs/BACKLOG.md`) so comeca quando o usuario mandar `iniciar
> PO-062`.

## Contexto

RN-031/RN-032 (ADR-019) criaram `Campo`/`CampoValor`: campos dinamicos
cadastrados na tela "Campos" (Administracao), donos por Setor (pelo nome,
RN-025), com valor sempre vinculado a uma instancia de `RedeExterna` ou
`RedeInterna` (RE/RI). O usuario apontou que parte da informacao cadastrada
por Setor nao pertence ao processo interno (RE/RI) — vem direto do cliente
(a propria Escola).

Perguntado, o usuario confirmou:

- quer uma tela nova "Setor" na Administracao, separada de "Processos" e
  "Campos" (nao um campo a mais dentro da tela Campos existente);
- o Setor dessa tela e o mesmo Setor ja cadastrado (RN-025) — nao uma
  entidade nova e independente;
- o objetivo do controle e ter "um setor global onde as informacoes
  aparecem no sistema de acordo com onde eu escolher que devem aparecer" —
  ou seja, o escopo decide o destino de exibicao/edicao do que ja e
  cadastrado por aquele Setor;
- a escolha e entre Atividade principal (Escola) OU Sub-atividades (RE/RI);
  quando Sub-atividades, uma segunda escolha define RE, RI, ou as duas;
- Campos ja cadastrados hoje (RN-031) recebem escopo padrao "Sub-atividades:
  RE e RI", preservando o comportamento atual sem exigir edicao manual.

## Decisao

Adicionar um atributo de escopo ao Setor (RN-025), gerenciado por uma tela
nova "Setor" em `apps.core_admin`, e usar esse escopo para decidir, por
Setor, se os `Campo` daquele Setor (RN-031) aparecem vinculados a `Escola`
ou a `RedeExterna`/`RedeInterna` (RE/RI, podendo escolher uma ou as duas).

## Decisao detalhada

### Onde vive o escopo: por nome de Setor, nao por linha de Processo

`Setor` (RN-025) e cadastrado por Processo — hoje existem linhas
duplicadas do mesmo nome (ex.: "Suprimentos" no Processo de RE e
"Suprimentos" no Processo de RI), deliberadamente espelhadas (ADR-016).
`Campo.setor_nome` ja e texto (nao FK para uma linha especifica de Setor)
exatamente para evitar esse problema (ADR-019). O escopo desta ADR segue o
mesmo precedente: fica associado ao **nome** do Setor, nao a uma linha de
Processo especifica — senao a mesma pessoa poderia configurar escopos
diferentes para "Suprimentos" dependendo de qual Processo ela abriu,
contrariando a suposicao ja registrada (RN-027/031) de que o nome do Setor
e um unico lugar de trabalho.

Novo model `SetorEscopo` (`apps.escolas`): `setor_nome` (`CharField`,
unico, mesmo vocabulario de `Setor.nome`), `atividade` (`CharField`,
choices `escola`/`sub_atividades`), `aplica_re` (`BooleanField`, default
`True`) e `aplica_ri` (`BooleanField`, default `True`) — os dois ultimos
so tem efeito quando `atividade="sub_atividades"`. Um registro por nome de
Setor.

### Tela "Setor" (`apps.core_admin`, secao Administracao)

Terceira tela da secao, ao lado de "Processos" (RN-025) e "Campos"
(RN-031):

- lista os nomes de Setor ja existentes no catalogo (RN-025) e o escopo
  atual de cada um (ou "nao configurado", se ainda nao tiver
  `SetorEscopo`);
- formulario para definir/editar o escopo de um Setor: Atividade principal
  (Escola) ou Sub-atividades (RE/RI); quando Sub-atividades, checkboxes de
  RE e RI (pelo menos um marcado);
- mesma permissao das demais telas da Administracao
  (`grupo_Administrador_required`).

### Efeito do escopo sobre `Campo`/`CampoValor`

- quando `SetorEscopo.atividade="sub_atividades"` (ou nao houver
  `SetorEscopo` para aquele nome — ver migracao de dados abaixo), os
  `Campo` daquele Setor continuam funcionando exatamente como hoje
  (RN-032): botao/modal na linha expandida de RE e/ou RI (conforme
  `aplica_re`/`aplica_ri`), `CampoValor` vinculado a instancia de
  `RedeExterna`/`RedeInterna`;
- quando `SetorEscopo.atividade="escola"`, os `Campo` daquele Setor passam
  a aparecer vinculados a `Escola`: mesmo padrao de botao/modal ja
  aprovado para RE/RI (RN-032), agora na linha da Escola (grid de
  Enderecos Lastmile) — decisao tecnica reversivel, por ser a extensao
  direta de um padrao de interface ja validado pelo usuario, sem inventar
  mecanismo novo;
- `CampoValor.content_object` (`GenericForeignKey`) passa a aceitar
  `Escola` como terceiro tipo possivel, alem de `RedeExterna`/
  `RedeInterna` — sem alterar o model em si (jah e generico).

### Migracao dos Campos existentes

Migration `RunPython` cria um `SetorEscopo` (`atividade="sub_atividades"`,
`aplica_re=True`, `aplica_ri=True`) para cada nome de Setor distinto ja
usado em `Campo.setor_nome` hoje — preserva o comportamento atual sem
exigir configuracao manual antes do deploy.

## Consequencias positivas

- resolve o pedido do usuario sem duplicar o conceito de Setor nem criar
  uma segunda hierarquia paralela;
- reaproveita integralmente o padrao de interface ja aprovado (botao +
  modal por Setor, RN-032), so trocando o alvo quando o escopo for Escola;
- migracao automatica evita quebrar os Campos ja em producao.

## Consequencias negativas / riscos

- um Setor com escopo "Escola" deixa de aparecer no modal de RE/RI mesmo
  que o RE/RI daquele nome de Setor continue existindo — mudanca de
  escopo depois de ja ter `CampoValor` gravados em RE/RI nao migra nem
  apaga esses valores automaticamente (ficam orfaos, so leitura via banco);
  registrado como pendencia, nao tratado nesta versao;
- `CampoValor` generico com 3 tipos possiveis de alvo (`Escola`,
  `RedeExterna`, `RedeInterna`) exige atencao a N+1 ao carregar valores por
  Setor, igual ao risco ja registrado na ADR-019.

## Alternativas consideradas

### Escopo como campo direto em `Setor` (por linha de Processo)

Rejeitada. Duplicaria a configuracao por Processo (RE e RI), podendo gerar
escopos diferentes para o mesmo nome de Setor — contraria o precedente ja
aceito de `Campo.setor_nome` (ADR-019) e a leitura por nome ja usada em
RN-027.

### Entidade nova e independente, sem vinculo com Setor (RN-025)

Rejeitada. Usuario confirmou explicitamente que e o mesmo Setor ja
cadastrado, nao um conceito novo.

## Pendencias

- comportamento de `CampoValor` ja gravados quando o escopo de um Setor
  muda depois de ja ter uso (hoje: ficam orfaos, sem limpeza automatica);
- validacao cruzada entre o escopo do Setor e o Processo que RE/RI usa
  (ex.: Setor com escopo "Escola" ainda pode ser escolhido na cascata
  Processo->Setor->Status de RN-026) nao e bloqueada por esta ADR.

## Gatilho de regeneracao

Nenhum diagrama documenta esta tela ainda.
