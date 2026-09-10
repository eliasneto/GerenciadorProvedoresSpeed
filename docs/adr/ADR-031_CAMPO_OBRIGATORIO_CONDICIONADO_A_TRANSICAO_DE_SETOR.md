# ADR-031 - Campo obrigatorio condicionado a transicao de Setor (origem -> destino)

## Status

`Aprovado`

> Esta ADR desenha a decisao de arquitetura. Nao autoriza inicio de execucao —
> a PO-079 (`docs/BACKLOG.md`) so comeca quando o usuario mandar `iniciar
> PO-079`.

## Contexto

Usuario pediu, em 2026-08-14: "Na criação de campos eu queria uma opção de
deixar um campo obrigatorio antes de enviar para X setor, ou seja, estou em
cotação e para ir para supliemntos, um cmapo X precisa ser preenchido antes,
mas se eu quiser mandar para compras esse campo não é obrigatorio, se compras
quiser enviar para suprimentos também não é obrigatorio, ou seja, eu
amarraria o setor de origin, o campo e o setor final."

O mecanismo de Campos personalizados por Setor ja existe (`Campo`/
`CampoValor`, RN-031/032, ADR-019) e ja tem precedente de extensao
condicional: a ADR-024 acrescentou um Campo so aparecer para um Status
especifico (`status_condicionante_nome`). Este pedido e parecido, mas a
condicao amarra tres pontas — Setor de origem, Campo e Setor de destino — em
vez de um unico Status; e o mesmo Campo pode ter comportamento diferente
dependendo do Setor de destino (obrigatorio para "Suprimentos", nao
obrigatorio para "Compras"), o que a ADR-024 nao precisou resolver (um Campo
tinha no maximo um Status condicionante).

Perguntado, o usuario confirmou tres pontos:

- o Campo exigido tem que pertencer sempre ao Setor de origem — o mesmo
  Setor dono que ja e o unico a poder editar aquele Campo (RN-032). Nao ha
  caso de exigir, para sair de um Setor, o preenchimento de um Campo que
  esse mesmo Setor nao consegue editar;
- quando a condicao nao e atendida, a troca de Setor deve ser bloqueada por
  completo — nada e salvo, o formulario mostra erro indicando o Campo
  faltante;
- o cadastro das regras reaproveita a tela "Campos" ja existente
  (RN-031/036), em vez de criar uma tela nova — mesmo precedente ja adotado
  pela ADR-024 de estender o mecanismo existente em vez de duplicar.

## Decisao

Criar um model novo relacionando `Campo` a um Setor de destino (por nome,
RN-025), permitindo que um mesmo Campo tenha varias regras — uma por Setor
de destino. Ao salvar uma troca de Setor de RE/RI/MapaCalor (RN-026) cujo par
(Setor atual, Setor de destino) bata com alguma regra cadastrada, a view
valida que o `CampoValor` daquele Campo esta preenchido antes de permitir a
troca; se nao estiver, bloqueia o salvamento com erro. O cadastro das regras
entra na propria tela "Campos" (`apps.core_admin`), no cadastro/edicao de
cada Campo.

## Decisao detalhada

### Por que um model novo, e nao um atributo simples em `Campo` (como o Status condicionante da ADR-024)

O Status condicionante da ADR-024 e um valor unico por Campo — um Campo so
aparece para **um** Status. Aqui o proprio pedido do usuario ja descreve dois
destinos diferentes para o mesmo Campo, com obrigatoriedade oposta
("Suprimentos" obrigatorio, "Compras" nao) — um atributo unico nao comporta
mais de uma regra por Campo. A relacao precisa ser 1:N (um Campo, varias
regras de destino), na mesma forma ja usada por `Setor`→`SetorStatus`
(RN-025): uma tabela propria, com FK para `Campo` e o nome do Setor de
destino.

### Setor de origem e sempre `Campo.setor_nome`, sem campo redundante

O usuario confirmou que o Campo exigido tem que ser sempre do Setor de
origem. Como `Campo.setor_nome` ja determina quem edita aquele Campo
(RN-032), o Setor de origem da regra fica implicito — nao existe um caso de
uso onde a regra precise de um Setor de origem diferente do dono do proprio
Campo. Por isso a nova tabela guarda somente o Setor de **destino**; a
origem e lida do Campo relacionado, evitando um campo que so serviria para
repetir (ou, pior, divergir de) `Campo.setor_nome`.

### Bloqueio total, nao aviso

Confirmado pelo usuario. Consistente com o padrao de validacao ja usado no
restante do mecanismo de Campo (RN-032: "validado conforme o tipo do
Campo... na view/form, nao so na UI") — a troca de Setor e uma unica
operacao atomica (Setor, Status e demais Campos do mesmo formulario), entao
o bloqueio precisa impedir o salvamento inteiro, nao só ocultar/sinalizar
depois.

### Reaproveita a tela "Campos"

Confirmado pelo usuario. Segue o mesmo raciocinio ja registrado na ADR-024
("Por que estender Campo, em vez de criar um model novo"): qualquer
capacidade nova que se encaixe no ciclo de vida do Campo (dono por Setor,
mesma tela de cadastro) entra ali, evitando duplicar telas/permissoes para
um conceito paralelo. Aqui a capacidade e um model relacionado, nao um
atributo — mas a tela de cadastro/edicao do Campo continua sendo o unico
lugar onde a regra e criada, editada e removida.

### Regra so vale para transicao real (Setor atual ja definido)

Uma subatividade (RE/RI/MapaCalor) recem-criada, sem Setor anterior, esta
recebendo seu primeiro Setor — nao "saindo" de lugar nenhum. Aplicar a regra
nesse momento obrigaria preencher um Campo de um Setor que a subatividade
talvez nunca tenha visitado, sem necessidade comprovada pelo pedido original
(que fala em "enviar para outro setor", pressupondo uma origem).

### Campo tipo Calculado nao pode ser usado numa regra

Um Campo Calculado (ADR-024) nunca e preenchido manualmente — o valor e
sempre derivado do Campo base. Se pudesse ser exigido numa regra de
obrigatoriedade, a condicao nunca teria como ser satisfeita atraves do
proprio Campo (so indiretamente, preenchendo o Campo base), tornando a
transicao permanentemente bloqueada por engano de configuracao. Bloquear
essa combinacao na propria tela de cadastro evita esse erro.

## Consequencias positivas

- reaproveita 100% a estrutura existente (`Campo`, tela "Campos", validacao
  na view de troca de Setor) — sem tela nova, sem duplicar permissao;
- generico: qualquer Setor pode cadastrar suas proprias regras de
  obrigatoriedade por destino, sem codigo novo;
- Setor de origem implicito (`Campo.setor_nome`) evita um campo redundante
  que pudesse divergir do dono real do Campo.

## Consequencias negativas / riscos

- mais uma tabela relacionada a Campo, aumentando a superficie de N+1 ao
  montar a validacao de troca de Setor (precisa checar todas as regras do
  Setor atual a cada tentativa de troca) — mitigado com
  `select_related`/`prefetch_related` dedicado, mesma atencao ja registrada
  na ADR-019/ADR-024;
- excluir um Campo referenciado numa regra remove a regra junto (mesmo
  padrao de cascata ja usado por `CampoValor`, ADR-021) — perda silenciosa
  de uma regra de obrigatoriedade se ninguem perceber a exclusao do Campo;
  mitigado por ser o mesmo tipo de aviso explicito ja exigido na exclusao de
  Campo (RN-036/ADR-021);
- bloqueio total pode surpreender quem esta no meio de uma troca de Setor
  sem perceber de imediato qual Campo falta — mitigado pela mensagem de erro
  apontando o Campo e o Setor de destino especificos.

## Alternativas consideradas

### Atributo unico em `Campo` (`setor_destino_obrigatorio_nome`), igual ao `status_condicionante_nome` da ADR-024

Rejeitada. O proprio pedido do usuario ja descreve dois destinos diferentes
(Suprimentos obrigatorio, Compras nao) para o mesmo Campo — um atributo
unico nao comporta mais de um destino por Campo.

### Permitir salvar com aviso, sem bloquear

Rejeitada. Usuario confirmou preferir bloqueio explicito, sem salvar a troca
enquanto o Campo estiver vazio.

### Tela nova dedicada para as regras de transicao

Rejeitada. Usuario confirmou reaproveitar a tela "Campos" ja existente,
seguindo o mesmo precedente da ADR-024.

### Setor de origem como campo independente do dono do Campo

Rejeitada. Usuario confirmou que o Campo exigido tem que ser sempre do Setor
de origem — a origem ja esta implicita em `Campo.setor_nome`, sem
necessidade de um campo redundante que pudesse divergir dele.

## Pendencias

- o que fazer ao excluir um Campo referenciado em alguma regra de
  obrigatoriedade — a decisao natural e cascata (mesmo padrao de
  `CampoValor`, ADR-021), mas o aviso explicito de exclusao (RN-036) precisa
  passar a informar tambem quantas regras de obrigatoriedade serao
  perdidas, nao somente `CampoValor`; a confirmar/implementar;
- Setor continua sem exclusao hoje (RN-025/ADR-014) — se um dia passar a ser
  excluivel, decidir o que ocorre com regras que o referenciam como destino;
- nenhum diagrama documenta este mecanismo ainda.

## Gatilho de regeneracao

Nenhum diagrama documenta esta tela ainda.
