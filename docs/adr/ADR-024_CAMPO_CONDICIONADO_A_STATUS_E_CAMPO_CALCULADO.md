# ADR-024 - Campo condicionado a Status e Campo calculado, no cadastro de Campos por Setor

## Status

`Aprovado`

> Esta ADR desenha a decisao de arquitetura. Nao autoriza inicio de execucao —
> a PO-063 (`docs/BACKLOG.md`) so comeca quando o usuario mandar `iniciar
> PO-063`.

## Contexto

Usuario pediu, em 2026-08-11: no Setor "Implantacao" (ja existe no catalogo
de Processos, RN-025, semeado desde a PO-050), ao definir o Status
"Agendando Parceiro" em um RE/RI, deve aparecer um campo "Inicio
Implantacao" para registrar a data combinada com o parceiro; o sistema deve
calcular automaticamente, 72 horas depois, um campo "Data Final
Implantacao", somente visual e nao editavel.

O mecanismo de Campos personalizados por Setor ja existe (`Campo`/
`CampoValor`, RN-031/032/036, ADR-019/021) e ja resolve "campo dono de um
Setor, exibido num modal no grid de RE/RI". Faltam duas capacidades: um
campo so aparecer para um Status especifico do RE/RI, e um campo cujo valor
e derivado automaticamente de outro campo (nao digitado).

Perguntado se esse recurso deveria ser generico (reutilizavel por outros
Setores/Status no futuro, direto pela tela "Campos") ou especifico so para
este caso, o usuario confirmou o mecanismo generico. Perguntado sobre a
precisao do campo "Inicio Implantacao", confirmou somente data (dia) — as
72 horas viram 3 dias corridos a partir do dia informado, sem necessidade de
horario.

## Decisao

Estender o model `Campo` (`apps.escolas`) com duas capacidades aditivas,
sem alterar o comportamento de nenhum Campo ja cadastrado:

1. **Status condicionante** (`status_condicionante_nome`, `CharField`
   opcional, mesmo vocabulario de `SetorStatus.nome`, RN-025): quando
   preenchido, o Campo so aparece no modal de Campos (RN-032) enquanto o
   Status atual do RE/RI exibido tiver esse mesmo nome. Vazio mantem o
   comportamento atual (sempre aparece, conforme a regra de `setor_atual`
   ja existente).
2. **Tipo "Calculado"**, novo valor de `Campo.tipo`, com dois atributos
   usados somente por esse tipo: `campo_base` (FK para outro `Campo` do
   mesmo `setor_nome`, obrigatoriamente tipo Data) e `horas_prazo`
   (`IntegerField` positivo). O valor de um Campo calculado nunca e gravado
   em `CampoValor` — e derivado em tempo de exibicao, somando ao valor atual
   do Campo base a quantidade de dias corridos equivalente a `horas_prazo`
   (arredondado para cima quando nao for multiplo exato de 24). Campo
   calculado e sempre somente leitura, em qualquer Setor e qualquer tela.

## Decisao detalhada

### Por que estender `Campo`, em vez de criar um model novo

Repete o precedente da propria RN-031/032: qualquer capacidade nova de
"campo dinamico" que se encaixe no mesmo ciclo de vida (dono por Setor,
exibido no mesmo modal, mesma tela de cadastro) entra como atributo
adicional de `Campo`, evitando duplicar a logica de agrupamento por Setor e
de renderizacao do modal (RN-032) para um conceito paralelo.

### Por que o valor calculado nao e persistido em `CampoValor`

Um Campo calculado depende sempre do valor atual do Campo base. Persistir o
resultado em `CampoValor` exigiria recalcular e sobrescrever a cada vez que
o Campo base mudasse (signal ou lógica extra no salvar), com risco de ficar
desatualizado se o valor do Campo base for alterado por outro caminho (ex.:
Django Admin). Calcular sob demanda, no momento de montar o modal, elimina
esse risco de dessincronia — e reversivel: se um dia for preciso auditar
historicamente o valor calculado num instante especifico, persistir passa a
ser necessario, mas isso e uma decisao nova, nao coberta aqui.

### Exemplo concreto desta entrega (configuracao, nao codigo)

Depois do Dev entregar as duas capacidades acima, a configuracao do caso
pedido e feita pelas telas ja existentes, sem trabalho de codigo adicional:

- criar o Status "Agendando Parceiro" nos Processos de Rede Externa e de
  Rede Interna, dentro do Setor "Implantacao" — tela ja existente
  (`processo_setor_status_criar`, RN-034);
- cadastrar, pela tela "Campos" (RN-031/036), o Campo "Inicio Implantacao"
  (Setor "Implantacao", tipo Data, Status condicionante = "Agendando
  Parceiro") e o Campo "Data Final Implantacao" (Setor "Implantacao", tipo
  Calculado, Campo base = "Inicio Implantacao", Horas de prazo = 72).

### O que NAO muda

- Campos ja cadastrados sem Status condicionante continuam se comportando
  exatamente como a RN-032 ja descreve;
- a regra de editabilidade por `setor_atual` (RN-030/032) nao muda — o
  Status condicionante e um filtro adicional de **visibilidade**, aplicado
  antes dessa regra; Campo calculado nunca fica editavel, independente de
  `setor_atual`.

## Consequencias positivas

- reaproveita 100% a estrutura existente (`Campo`/`CampoValor`, modal
  RN-032, tela "Campos" RN-031/036) — sem tela nova, sem model novo;
- generico: qualquer Setor pode, no futuro, repetir o padrao "campo que so
  aparece num Status + prazo automatico a partir dele" apenas cadastrando,
  sem codigo novo;
- calculo sob demanda evita mais uma tabela/sincronizacao de valor
  derivado.

## Consequencias negativas / riscos

- mais uma combinacao de regras dentro do mecanismo de Campo, ja denso
  (tipo, Setor dono, agora tambem Status condicionante e tipo Calculado com
  dependencia de outro Campo) — mitigado documentando aqui e limitando o
  MVP a horas convertidas em dias corridos, sem hora exata;
- Campo calculado depende de outro Campo do mesmo Setor — excluir o Campo
  base enquanto outro Campo o referencia como base precisa de uma regra
  (bloquear exclusao ou remover a dependencia); registrado como pendencia,
  a decidir antes/durante a implementacao;
- carregar o modal (RN-032) passa a exigir, para cada Campo calculado,
  localizar o valor do respectivo Campo base — atencao a N+1 ao montar o
  modal com varios Campos calculados.

## Alternativas consideradas

### Implementacao especifica, hardcoded para Setor "Implantacao"/Status "Agendando Parceiro"

Rejeitada. Usuario confirmou preferir o mecanismo generico, reutilizavel
pela propria tela "Campos" sem exigir codigo novo em pedidos futuros
parecidos.

### Persistir o valor calculado em `CampoValor`, recalculando via signal

Rejeitada por ora — adiciona sincronizacao sem necessidade comprovada, dado
que a exibicao sempre pode derivar o valor ao vivo. Pode ser revisitada se
surgir a necessidade de auditar o valor calculado num instante especifico
(ex.: histórico, RN-029).

### Campo base e Campo calculado com precisao de data e hora

Rejeitada nesta entrega — usuario confirmou que data (dia) e suficiente;
as 72 horas viram 3 dias corridos. Precisao de hora exigiria um tipo novo
"Data e hora" em `Campo`, nao pedido agora.

## Pendencias

- o que fazer ao excluir um Campo que e Campo base de um Campo calculado
  (bloquear a exclusao vs. excluir o calculado em cascata) — decidir
  antes/durante a implementacao;
- nenhum diagrama documenta esta tela ainda.

## Gatilho de regeneracao

Nenhum diagrama documenta esta tela ainda.
